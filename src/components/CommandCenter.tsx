import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowRight,
  AudioWaveform,
  Brain,
  FolderKanban,
  Home,
  Library,
  MessageSquare,
  MessagesSquare,
  Mic,
  PanelLeft,
  Plug,
  Plus,
  Search,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '@/state/AppContext';
import { AI_MODES, COMMANDS } from '@/data/mock';
import type { AIModeId, CommandAction, ViewId } from '@/types';
import { cx, rgba, useModLabel } from '@/lib/utils';

const ICONS: Record<string, LucideIcon> = {
  Home,
  MessagesSquare,
  AudioWaveform,
  Activity,
  Library,
  Plug,
  Brain,
  FolderKanban,
  Plus,
  Mic,
  PanelLeft,
  Sparkles,
  MessageSquare,
};

const GROUP_ORDER: CommandAction['group'][] = [
  'Navigate',
  'Modes',
  'System',
  'Conversations',
  'Projects',
  'Tools',
];

/**
 * The operating-system control layer. Search, keyboard navigation,
 * grouped commands, and a dimensional glass presentation.
 */
export function CommandCenter() {
  const {
    commandOpen,
    setCommandOpen,
    setView,
    setMode,
    openConversation,
    newConversation,
    setVoiceActive,
    toggleSidebar,
    setSettingsOpen,
    mode,
  } = useApp();

  const mod = useModLabel();
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const listRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? COMMANDS.filter(
          (c) =>
            c.label.toLowerCase().includes(q) ||
            c.hint.toLowerCase().includes(q) ||
            c.group.toLowerCase().includes(q) ||
            (c.keywords ?? '').toLowerCase().includes(q),
        )
      : COMMANDS;

    return GROUP_ORDER.flatMap((group) =>
      filtered.filter((c) => c.group === group),
    );
  }, [query]);

  useEffect(() => {
    if (commandOpen) {
      setQuery('');
      setCursor(0);
      window.setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [commandOpen]);

  useEffect(() => setCursor(0), [query]);

  const run = useCallback(
    (action: CommandAction) => {
      const id = action.id;
      if (id.startsWith('mode-')) setMode(id.replace('mode-', '') as AIModeId);
      else if (id.startsWith('conv-')) openConversation(id.replace('conv-', ''));
      else if (id.startsWith('proj-')) setView('projects');
      else if (id.startsWith('tool-')) setView('tools');
      switch (id) {
        case 'nav-home':
          setView('home');
          break;
        case 'nav-chat':
          setView('conversation');
          break;
        case 'nav-voice':
          setView('voice');
          break;
        case 'nav-dash':
          setView('dashboard');
          break;
        case 'nav-knowledge':
          setView('knowledge');
          break;
        case 'nav-tools':
          setView('tools');
          break;
        case 'nav-memory':
          setView('memory');
          break;
        case 'nav-projects':
          setView('projects');
          break;
        case 'act-new':
          newConversation();
          break;
        case 'act-voice':
          setVoiceActive(true);
          setView('voice');
          break;
        case 'act-sidebar':
          toggleSidebar();
          break;
        default:
          break;
      }
      setCommandOpen(false);
    },
    [
      newConversation,
      openConversation,
      setCommandOpen,
      setMode,
      setView,
      setVoiceActive,
      toggleSidebar,
    ],
  );

  useEffect(() => {
    if (!commandOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setCursor((c) => Math.min(c + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setCursor((c) => Math.max(c - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const action = results[cursor];
        if (action) run(action);
      } else if (e.key === 'Tab') {
        e.preventDefault();
        setCursor((c) => (e.shiftKey ? Math.max(c - 1, 0) : Math.min(c + 1, results.length - 1)));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [commandOpen, results, cursor, run]);

  /* Keep the active row visible */
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${cursor}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [cursor]);

  const activeMode = AI_MODES.find((m) => m.id === mode) ?? AI_MODES[0];

  return (
    <AnimatePresence>
      {commandOpen && (
        <motion.div
          className="fixed inset-0 z-[80] flex items-start justify-center px-4 pt-[8vh] sm:pt-[12vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.28 }}
        >
          {/* Scrim */}
          <motion.div
            className="absolute inset-0 bg-obsidian-950/80 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setCommandOpen(false)}
            aria-hidden
          />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command center"
            initial={{ opacity: 0, y: -22, scale: 0.97, filter: 'blur(14px)' }}
            animate={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: -16, scale: 0.98, filter: 'blur(10px)' }}
            transition={{ duration: 0.42, ease: [0.16, 1, 0.3, 1] }}
            className="glass-deep relative w-full max-w-[680px] overflow-hidden rounded-[22px] shadow-glass-lg"
          >
            {/* Top illumination */}
            <span
              aria-hidden
              className="absolute inset-x-10 top-0 h-px"
              style={{
                background: `linear-gradient(90deg, transparent, ${rgba(
                  activeMode.aura,
                  0.85,
                )}, transparent)`,
              }}
            />

            {/* Search */}
            <div className="flex items-center gap-4 border-b border-white/[0.055] px-5 py-4">
              <Search className="h-4 w-4 shrink-0 text-platinum-dim" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search conversations, modes, projects, tools…"
                className="flex-1 bg-transparent text-[15px] font-[350] text-platinum placeholder:text-platinum-dim/45 focus:outline-none"
                aria-label="Search commands"
              />
              <kbd className="rounded border border-white/[0.09] bg-white/[0.03] px-2 py-1 font-mono text-3xs uppercase tracking-wider text-platinum-dim">
                esc
              </kbd>
            </div>

            {/* Context strip */}
            <div className="flex items-center gap-4 border-b border-white/[0.04] px-5 py-2.5">
              <span className="flex items-center gap-2">
                <span
                  className="text-[0.75rem]"
                  style={{ color: rgba(activeMode.aura, 0.9) }}
                >
                  {activeMode.glyph}
                </span>
                <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                  {activeMode.label}
                </span>
              </span>
              <span className="h-3 w-px bg-white/10" />
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                {results.length} results
              </span>
              <span className="ml-auto flex items-center gap-3">
                <NavHint keys={['↑', '↓']} label="Navigate" />
                <NavHint keys={['↵']} label="Run" />
              </span>
            </div>

            {/* Results */}
            <div
              ref={listRef}
              className="max-h-[52vh] overflow-y-auto overscroll-contain px-2.5 py-3"
              role="listbox"
            >
              {results.length === 0 ? (
                <div className="flex flex-col items-center px-6 py-14 text-center">
                  <span
                    className="flex h-12 w-12 items-center justify-center rounded-full border"
                    style={{ borderColor: rgba(activeMode.aura, 0.25) }}
                  >
                    <Search className="h-4 w-4 text-platinum-dim" />
                  </span>
                  <p className="mt-5 text-[13.5px] text-platinum-soft/80">
                    No commands match “{query}”.
                  </p>
                  <p className="mt-2 text-[12px] text-platinum-dim/60">
                    Try a mode name, a project, or a conversation title.
                  </p>
                </div>
              ) : (
                GROUP_ORDER.map((group) => {
                  const rows = results.filter((r) => r.group === group);
                  if (rows.length === 0) return null;
                  return (
                    <div key={group} className="mb-2 last:mb-0">
                      <div className="px-3 py-2 font-mono text-3xs uppercase tracking-widest3 text-platinum-dim/60">
                        {group}
                      </div>
                      <ul>
                        {rows.map((action) => {
                          const idx = results.indexOf(action);
                          const isCursor = idx === cursor;
                          const Icon = ICONS[action.icon] ?? Sparkles;
                          return (
                            <li key={action.id}>
                              <button
                                type="button"
                                data-idx={idx}
                                role="option"
                                aria-selected={isCursor}
                                onMouseEnter={() => setCursor(idx)}
                                onClick={() => run(action)}
                                className={cx(
                                  'group relative flex w-full items-center gap-3.5 rounded-xl px-3 py-2.5 text-left transition-colors duration-200',
                                  isCursor ? 'bg-white/[0.06]' : 'hover:bg-white/[0.03]',
                                )}
                              >
                                {isCursor && (
                                  <motion.span
                                    layoutId="command-cursor"
                                    transition={{ type: 'spring', stiffness: 460, damping: 38 }}
                                    className="absolute inset-0 rounded-xl border"
                                    style={{
                                      borderColor: rgba(activeMode.aura, 0.28),
                                      background: rgba(activeMode.aura, 0.06),
                                    }}
                                  />
                                )}
                                <span
                                  className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border"
                                  style={{
                                    borderColor: isCursor
                                      ? rgba(activeMode.aura, 0.3)
                                      : 'rgba(255,255,255,0.07)',
                                    background: isCursor
                                      ? rgba(activeMode.aura, 0.1)
                                      : 'rgba(255,255,255,0.02)',
                                  }}
                                >
                                  <Icon
                                    className="h-3.5 w-3.5"
                                    style={{
                                      color: isCursor
                                        ? rgba(activeMode.aura, 0.95)
                                        : 'rgba(143,149,163,0.9)',
                                    }}
                                  />
                                </span>
                                <span className="relative z-10 min-w-0 flex-1">
                                  <span
                                    className={cx(
                                      'block truncate text-[13.5px]',
                                      isCursor ? 'text-platinum' : 'text-platinum-soft/85',
                                    )}
                                  >
                                    {action.label}
                                  </span>
                                  <span className="mt-0.5 block truncate font-mono text-3xs uppercase tracking-wider text-platinum-dim/55">
                                    {action.hint}
                                  </span>
                                </span>
                                {action.shortcut ? (
                                  <kbd className="relative z-10 shrink-0 rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[9px] text-platinum-dim">
                                    {action.shortcut}
                                  </kbd>
                                ) : (
                                  <ArrowRight
                                    className={cx(
                                      'relative z-10 h-3.5 w-3.5 shrink-0 transition-all duration-300',
                                      isCursor
                                        ? 'translate-x-0 opacity-100'
                                        : '-translate-x-1 opacity-0',
                                    )}
                                    style={{ color: rgba(activeMode.aura, 0.9) }}
                                  />
                                )}
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.05] px-5 py-3">
              <div className="flex items-center gap-4">
                <NavHint keys={[mod, 'K']} label="Toggle" />
                <NavHint keys={[mod, 'B']} label="Sidebar" />
                <NavHint keys={[mod, 'N']} label="New" />
              </div>
              <button
                type="button"
                onClick={() => {
                  setCommandOpen(false);
                  setSettingsOpen(true);
                }}
                className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60 transition-colors hover:text-platinum"
              >
                Preferences
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function NavHint({ keys, label }: { keys: string[]; label: string }) {
  return (
    <span className="flex items-center gap-2">
      <span className="flex items-center gap-1">
        {keys.map((k) => (
          <kbd
            key={k}
            className="rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[9px] text-platinum-dim"
          >
            {k}
          </kbd>
        ))}
      </span>
      <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
        {label}
      </span>
    </span>
  );
}

/** Shared view registry used by the router. */
export const VIEW_IDS: ViewId[] = [
  'home',
  'conversation',
  'voice',
  'dashboard',
  'knowledge',
  'tools',
  'memory',
  'projects',
];