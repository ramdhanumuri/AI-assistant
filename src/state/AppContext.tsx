import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { AIModeId, AIState, Conversation, ContentBlock, Message, ToolTrace, ViewId } from '@/types';
import { CONVERSATIONS, MODE_BY_ID, SEED_MESSAGES } from '@/data/mock';
import { runAssistantTurn, seededTranscript } from '@/lib/engine';
import { uid } from '@/lib/utils';

export interface Settings {
  ambientLight: boolean;
  particles: boolean;
  reduceMotion: boolean;
  streaming: boolean;
  memory: boolean;
  citations: boolean;
  soundscape: boolean;
  density: 'comfortable' | 'compact';
}

const DEFAULT_SETTINGS: Settings = {
  ambientLight: true,
  particles: true,
  reduceMotion: false,
  streaming: true,
  memory: true,
  citations: true,
  soundscape: false,
  density: 'comfortable',
};

interface AppState {
  view: ViewId;
  setView: (v: ViewId) => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;

  mode: AIModeId;
  setMode: (m: AIModeId) => void;
  aiState: AIState;

  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Message[];
  openConversation: (id: string) => void;
  newConversation: () => void;
  sendMessage: (text: string) => void;
  stopResponse: () => void;
  isStreaming: boolean;

  reasoning: string;
  traces: ToolTrace[];
  liveTokens: number;

  voiceActive: boolean;
  setVoiceActive: (v: boolean) => void;

  commandOpen: boolean;
  setCommandOpen: (v: boolean) => void;
  settingsOpen: boolean;
  setSettingsOpen: (v: boolean) => void;

  settings: Settings;
  updateSettings: (patch: Partial<Settings>) => void;

  toasts: { id: string; text: string }[];
  notify: (text: string) => void;
}

const Ctx = createContext<AppState | null>(null);

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>');
  return ctx;
}

function firstText(blocks: ContentBlock[], fallback = 'Rich response'): string {
  const text = blocks.find((b) => b.kind === 'text');
  if (text && text.kind === 'text') {
    return text.body.length > 118 ? `${text.body.slice(0, 118)}…` : text.body;
  }
  return fallback;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setViewRaw] = useState<ViewId>('home');
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window === 'undefined' || window.innerWidth >= 1024,
  );
  const [mode, setModeRaw] = useState<AIModeId>('general');
  const [aiState, setAiState] = useState<AIState>('idle');

  const [conversations, setConversations] = useState<Conversation[]>(CONVERSATIONS);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const [reasoning, setReasoning] = useState('');
  const [traces, setTraces] = useState<ToolTrace[]>([]);
  const [liveTokens, setLiveTokens] = useState(0);
  const [isStreaming, setIsStreaming] = useState(false);

  const [voiceActive, setVoiceActive] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [toasts, setToasts] = useState<{ id: string; text: string }[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  const notify = useCallback((text: string) => {
    const id = uid('toast');
    setToasts((prev) => [...prev, { id, text }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 2800);
  }, []);

  const setView = useCallback((v: ViewId) => {
    setViewRaw(v);
    setVoiceActive(v === 'voice');
  }, []);

  const setMode = useCallback(
    (m: AIModeId) => {
      setModeRaw(m);
      notify(`${MODE_BY_ID[m].label} mode engaged`);
    },
    [notify],
  );

  const toggleSidebar = useCallback(() => setSidebarOpen((s) => !s), []);

  const updateSettings = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  }, []);

  const resetTelemetry = useCallback(() => {
    setReasoning('');
    setTraces([]);
    setLiveTokens(0);
  }, []);

  const stopResponse = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setAiState('idle');
  }, []);

  const openConversation = useCallback(
    (id: string) => {
      abortRef.current?.abort();
      abortRef.current = null;
      setIsStreaming(false);
      setActiveConversationId(id);
      const existing = CONVERSATIONS.find((c) => c.id === id);
      const seeded = seededTranscript(id);
      setMessages(seeded.length ? seeded : id === 'c-orbital' ? SEED_MESSAGES : []);
      setModeRaw(existing?.mode ?? 'general');
      resetTelemetry();
      setAiState('idle');
      setViewRaw('conversation');
      setVoiceActive(false);
    },
    [resetTelemetry],
  );

  const newConversation = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setActiveConversationId(null);
    setMessages([]);
    resetTelemetry();
    setAiState('idle');
    setViewRaw('conversation');
    setVoiceActive(false);
    notify('New private thread opened');
  }, [notify, resetTelemetry]);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || abortRef.current) return;

      const controller = new AbortController();
      abortRef.current = controller;
      const activeMode = modeRef.current;

      setMessages((prev) => [
        ...prev,
        {
          id: uid('msg'),
          role: 'user',
          createdAt: Date.now(),
          mode: activeMode,
          blocks: [{ kind: 'text', body: trimmed }],
        },
      ]);
      resetTelemetry();
      setIsStreaming(true);
      setAiState('thinking');
      setViewRaw('conversation');
      setVoiceActive(false);

      const draftId = uid('msg');
      let hasDraft = false;
      const localTraces: ToolTrace[] = [];

      const cleanup = () => {
        abortRef.current = null;
        setIsStreaming(false);
        setAiState('idle');
      };

      void (async () => {
        let response: Message;
        try {
          response = await runAssistantTurn(
            trimmed,
            activeMode,
            {
              onReasoning: setReasoning,
              onTrace: (t) => {
                localTraces.push(t);
                setTraces([...localTraces]);
              },
              onTraceDone: (id, durationMs) => {
                const found = localTraces.find((x) => x.id === id);
                if (found) {
                  found.state = 'done';
                  found.durationMs = durationMs;
                }
                setTraces([...localTraces]);
              },
              onBlocks: (blocks) => {
                setAiState('responding');
                hasDraft = true;
                const draft: Message = {
                  id: draftId,
                  role: 'assistant',
                  createdAt: Date.now(),
                  mode: activeMode,
                  blocks,
                  traces: [...localTraces],
                };
                setMessages((prev) => [...prev.filter((m) => m.id !== draftId), draft]);
              },
              onToken: setLiveTokens,
            },
            controller.signal,
          );
        } catch {
          cleanup();
          return;
        }

        if (controller.signal.aborted) {
          cleanup();
          return;
        }

        const finalMessage: Message = { ...response, traces: localTraces };
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== draftId),
          finalMessage,
        ]);
        void hasDraft;
        cleanup();

        setActiveConversationId((currentId) => {
          const preview = firstText(finalMessage.blocks);
          if (currentId) {
            setConversations((prev) =>
              prev.map((c) =>
                c.id === currentId
                  ? {
                      ...c,
                      preview,
                      updatedAt: Date.now(),
                      messageCount: c.messageCount + 2,
                      mode: finalMessage.mode,
                    }
                  : c,
              ),
            );
            return currentId;
          }
          const createdId = uid('c');
          setConversations((prev) => [
            {
              id: createdId,
              title: trimmed.length > 46 ? `${trimmed.slice(0, 46)}…` : trimmed,
              preview,
              updatedAt: Date.now(),
              mode: finalMessage.mode,
              messageCount: 2,
            },
            ...prev,
          ]);
          return createdId;
        });
      })();
    },
    [resetTelemetry],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const key = e.key.toLowerCase();

      if (mod && key === 'k') {
        e.preventDefault();
        setCommandOpen((v) => !v);
        return;
      }
      if (mod && key === 'b') {
        e.preventDefault();
        setSidebarOpen((s) => !s);
        return;
      }
      if (mod && key === 'n') {
        e.preventDefault();
        newConversation();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [newConversation]);

  /* Escape unwinds overlays in priority order, then exits voice. */
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (commandOpen) {
        setCommandOpen(false);
        return;
      }
      if (settingsOpen) {
        setSettingsOpen(false);
        return;
      }
      if (voiceActive && !abortRef.current) setVoiceActive(false);
    };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [commandOpen, settingsOpen, voiceActive]);

  const value = useMemo<AppState>(
    () => ({
      view,
      setView,
      sidebarOpen,
      toggleSidebar,
      mode,
      setMode,
      aiState,
      conversations,
      activeConversationId,
      messages,
      openConversation,
      newConversation,
      sendMessage,
      stopResponse,
      isStreaming,
      reasoning,
      traces,
      liveTokens,
      voiceActive,
      setVoiceActive,
      commandOpen,
      setCommandOpen,
      settingsOpen,
      setSettingsOpen,
      settings,
      updateSettings,
      toasts,
      notify,
    }),
    [
      view,
      setView,
      sidebarOpen,
      toggleSidebar,
      mode,
      setMode,
      aiState,
      conversations,
      activeConversationId,
      messages,
      openConversation,
      newConversation,
      sendMessage,
      stopResponse,
      isStreaming,
      reasoning,
      traces,
      liveTokens,
      voiceActive,
      commandOpen,
      settingsOpen,
      settings,
      updateSettings,
      toasts,
      notify,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}