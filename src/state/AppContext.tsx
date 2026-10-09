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
import type {
  AIModeId,
  AIState,
  Conversation,
  ContentBlock,
  Message,
  ToolTrace,
  ViewId,
} from '@/types';
import { MODE_BY_ID, SEED_MESSAGES } from '@/data/mock';
import { seededTranscript } from '@/lib/engine';
import {
  conversationApi,
  type ConversationWire,
  type MessageWire,
} from '@/lib/conversations';
import { errorMessage } from '@/lib/api';
import {
  chatApi,
  newIdempotencyKey,
  streamChatMessage,
  type AICapabilities,
  type ChatMessageWire,
} from '@/lib/chat';
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
  conversationsLoading: boolean;
  conversationsError: string | null;
  activeConversationId: string | null;
  messages: Message[];
  openConversation: (id: string) => void;
  newConversation: () => void;
  sendMessage: (text: string) => void;
  retryMessage: (messageId: string) => void;
  stopResponse: () => void;
  isStreaming: boolean;

  /** Whether the deployment's AI provider is usable, from the server. */
  aiCapabilities: AICapabilities | null;

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

/* Convert the server's message shape into the UI's `Message`. The block
   vocabulary is shared, so only the provenance fields need mapping; every
   token/latency field is passed through as `null` when the provider did not
   report it, so the UI can omit it rather than show a misleading zero. */
function toMessage(wire: MessageWire | ChatMessageWire): Message {
  const blocks = (wire.blocks ?? []) as ContentBlock[];
  return {
    id: wire.id,
    role: wire.role,
    createdAt: wire.createdAt,
    mode: wire.mode as AIModeId,
    blocks,
    voice: wire.voice,
    reasoning: wire.reasoning ?? undefined,
    traces: (wire.traces as ToolTrace[] | null) ?? undefined,
    tokens: wire.tokens ?? undefined,
    status: wire.status,
    model: wire.model ?? null,
    provider: wire.provider ?? null,
    inputTokens: wire.inputTokens ?? null,
    outputTokens: wire.outputTokens ?? null,
    totalTokens: wire.totalTokens ?? null,
    latencyMs: wire.latencyMs ?? null,
    errorCode: wire.errorCode ?? null,
  };
}

function toConversation(wire: ConversationWire): Conversation {
  return {
    id: wire.id,
    title: wire.title,
    preview: wire.preview,
    updatedAt: wire.updatedAt,
    mode: wire.mode as AIModeId,
    project: wire.project ?? undefined,
    pinned: wire.pinned,
    messageCount: wire.messageCount,
  };
}

/** Accumulate streamed text into a single text block. */
function withStreamedText(message: Message, text: string): Message {
  return {
    ...message,
    blocks: [{ kind: 'text', body: text }],
  };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setViewRaw] = useState<ViewId>('home');
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window === 'undefined' || window.innerWidth >= 1024,
  );
  const [mode, setModeRaw] = useState<AIModeId>('general');
  const [aiState, setAiState] = useState<AIState>('idle');

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [conversationsError, setConversationsError] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [aiCapabilities, setAiCapabilities] = useState<AICapabilities | null>(null);

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
  /* The live assistant turn. Held in a ref, not state, so streamed deltas
     accumulate without re-creating the send callback on every token. */
  const streamRef = useRef<{ conversationId: string; messageId: string; text: string } | null>(
    null,
  );
  const modeRef = useRef(mode);
  modeRef.current = mode;

  const notify = useCallback((text: string) => {
    const id = uid('toast');
    setToasts((prev) => [...prev, { id, text }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 2800);
  }, []);

  /* ── Server-backed conversations ──────────────────────────────────
     The sidebar is populated from the API, not from mock data. The seed
     conversations remain as a demo transcript for the mock-driven views that
     were not part of STEP 6, but the live chat reads and writes real rows. */
  const loadConversations = useCallback(async () => {
    try {
      const page = await conversationApi.list({ limit: 50 });
      setConversations(page.items.map(toConversation));
      setConversationsError(null);
    } catch (error) {
      setConversationsError(errorMessage(error));
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    let cancelled = false;
    void chatApi
      .capabilities()
      .then((caps) => {
        if (!cancelled) setAiCapabilities(caps);
      })
      .catch(() => {
        /* capabilities are advisory; a failure just hides the streaming hint */
      });
    return () => {
      cancelled = true;
    };
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
    /* Mark the local placeholder cancelled immediately. The server records the
       same terminal state when it observes the disconnect, so a reload agrees
       with what the user just saw. */
    const live = streamRef.current;
    if (live) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === live.messageId
            ? { ...m, status: 'cancelled' as const, errorCode: 'stream_interrupted' }
            : m,
        ),
      );
      streamRef.current = null;
    }
  }, []);

  const openConversation = useCallback(
    (id: string) => {
      abortRef.current?.abort();
      abortRef.current = null;
      streamRef.current = null;
      setIsStreaming(false);
      setActiveConversationId(id);
      resetTelemetry();
      setAiState('idle');
      setViewRaw('conversation');
      setVoiceActive(false);

      const known = conversations.find((c) => c.id === id);
      if (known) setModeRaw(known.mode);

      void (async () => {
        try {
          const page = await conversationApi.messages(id, { limit: 200 });
          setMessages(page.items.map(toMessage));
        } catch {
          /* A mock/demo thread (from the STEP 1 seed data) has no server row.
             Fall back to the seeded transcript so the presentational views that
             reference mock ids keep working unchanged. */
          const seeded = seededTranscript(id);
          setMessages(seeded.length ? seeded : id === 'c-orbital' ? SEED_MESSAGES : []);
        }
      })();
    },
    [conversations, resetTelemetry],
  );

  const newConversation = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    streamRef.current = null;
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
      const optimisticUserId = uid('msg');
      const optimisticAssistantId = uid('msg');
      const now = Date.now();

      /* Optimistic pair: the user turn appears instantly and the assistant
         placeholder shows the streaming state until the first delta lands. */
      setMessages((prev) => [
        ...prev,
        {
          id: optimisticUserId,
          role: 'user',
          createdAt: now,
          mode: activeMode,
          blocks: [{ kind: 'text', body: trimmed }],
        },
        {
          id: optimisticAssistantId,
          role: 'assistant',
          createdAt: now,
          mode: activeMode,
          blocks: [],
          status: 'streaming',
          failedPrompt: trimmed,
        },
      ]);
      resetTelemetry();
      setIsStreaming(true);
      setAiState('thinking');
      setViewRaw('conversation');
      setVoiceActive(false);

      const idempotencyKey = newIdempotencyKey();
      const replaceAssistant = (patch: Partial<Message>) =>
        setMessages((prev) =>
          prev.map((m) => (m.id === optimisticAssistantId ? { ...m, ...patch } : m)),
        );

      const cleanup = () => {
        abortRef.current = null;
        streamRef.current = null;
        setIsStreaming(false);
        setAiState('idle');
      };

      void (async () => {
        let conversationId = activeConversationId;

        // A brand-new thread is created lazily on its first message, so
        // abandoning the composer never leaves an empty conversation behind.
        if (!conversationId) {
          try {
            const created = await conversationApi.create({ mode: activeMode });
            conversationId = created.id;
            setActiveConversationId(created.id);
            setConversations((prev) => [toConversation(created), ...prev]);
          } catch (error) {
            replaceAssistant({
              status: 'failed',
              errorCode: 'provider_unavailable',
            });
            notify(errorMessage(error));
            cleanup();
            return;
          }
        }

        let buffer = '';
        streamRef.current = {
          conversationId,
          messageId: optimisticAssistantId,
          text: '',
        };

        /* When the deployment reports streaming disabled, use the documented
           non-streaming endpoint instead. Both paths persist identically; only
           the transport differs, so the UI contract is unchanged. */
        if (aiCapabilities && !aiCapabilities.streamingEnabled) {
          try {
            const turn = await conversationApi.send(conversationId, {
              body: trimmed,
              mode: activeMode,
              idempotencyKey,
            });
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id === optimisticUserId) return toMessage(turn.userMessage);
                if (m.id === optimisticAssistantId) return toMessage(turn.assistantMessage);
                return m;
              }),
            );
            const next = toConversation(turn.conversation);
            setConversations((prev) => [next, ...prev.filter((c) => c.id !== next.id)]);
          } catch (error) {
            replaceAssistant({ status: 'failed', errorCode: 'provider_unavailable' });
            notify(errorMessage(error));
          }
          cleanup();
          return;
        }

        try {
          await streamChatMessage(
            {
              conversationId,
              body: trimmed,
              mode: activeMode,
              idempotencyKey,
              signal: controller.signal,
            },
            {
              onMeta: (meta) => {
                // Swap the optimistic ids for the persisted ones so a later
                // reload and this session refer to the same rows.
                setMessages((prev) =>
                  prev.map((m) => {
                    if (m.id === optimisticUserId) return toMessage(meta.userMessage);
                    if (m.id === optimisticAssistantId) {
                      return {
                        ...toMessage(meta.assistantMessage),
                        status: 'streaming',
                        failedPrompt: trimmed,
                      };
                    }
                    return m;
                  }),
                );
                streamRef.current = {
                  conversationId,
                  messageId: meta.assistantMessage.id,
                  text: '',
                };
              },
              onDelta: (delta) => {
                buffer += delta;
                setAiState('responding');
                setLiveTokens(Math.round(buffer.length / 4));
                const live = streamRef.current;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === (live?.messageId ?? optimisticAssistantId)
                      ? withStreamedText(m, buffer)
                      : m,
                  ),
                );
              },
              onDone: (message, conversation) => {
                const finalMessage = toMessage(message);
                setMessages((prev) =>
                  prev.map((m) => (m.id === message.id ? finalMessage : m)),
                );
                setConversations((prev) => {
                  const next = toConversation(conversation);
                  const without = prev.filter((c) => c.id !== next.id);
                  return [next, ...without];
                });
                cleanup();
              },
              onError: (error) => {
                replaceAssistant({
                  status: 'failed',
                  errorCode: error.code,
                  failedPrompt: trimmed,
                  reasoning: undefined,
                });
                setAiState('idle');
                notify(error.message);
                cleanup();
              },
            },
          );
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') {
            // User-initiated stop: the message is already marked cancelled.
            cleanup();
            return;
          }
          replaceAssistant({ status: 'failed', errorCode: 'provider_unavailable' });
          notify(errorMessage(error));
          cleanup();
        }
      })();
    },
    [activeConversationId, aiCapabilities, notify, resetTelemetry],
  );

  /** Re-run a failed generation, reusing the prompt that produced it. */
  const retryMessage = useCallback(
    (messageId: string) => {
      const index = messages.findIndex((m) => m.id === messageId);
      const target = index === -1 ? undefined : messages[index];
      if (!target || target.status !== 'failed' || !target.failedPrompt) return;

      // Remove the failed assistant turn and, when present, the user message
      // that prompted it, so the retry does not duplicate the prompt.
      const start = index > 0 && messages[index - 1].role === 'user' ? index - 1 : index;
      setMessages((prev) => prev.filter((_, i) => i < start || i > index));
      sendMessage(target.failedPrompt);
    },
    [messages, sendMessage],
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
      conversationsLoading,
      conversationsError,
      activeConversationId,
      messages,
      openConversation,
      newConversation,
      sendMessage,
      retryMessage,
      stopResponse,
      isStreaming,
      aiCapabilities,
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
      conversationsLoading,
      conversationsError,
      activeConversationId,
      messages,
      openConversation,
      newConversation,
      sendMessage,
      retryMessage,
      stopResponse,
      isStreaming,
      aiCapabilities,
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