import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowUp,
  AudioLines,
  ChevronDown,

  CornerDownLeft,
  Paperclip,
  Square,
  Wrench,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '@/state/AppContext';
import { AI_MODES, MODE_BY_ID, TOOLS } from '@/data/mock';
import { cx, rgba, useModLabel } from '@/lib/utils';

interface CommandBarProps {
  className?: string;
  autoFocus?: boolean;
  placeholder?: string;
}

export function CommandBar({
  className,
  autoFocus = false,
  placeholder = 'Ask anything, or describe what you want to build…',
}: CommandBarProps) {
  const {
    mode,
    setMode,
    sendMessage,
    stopResponse,
    isStreaming,
    aiState,
    setVoiceActive,
    settings,
  } = useApp();

  const mod = useModLabel();
  const active = MODE_BY_ID[mode];
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const [modeOpen, setModeOpen] = useState(false);
  const [toolOpen, setToolOpen] = useState(false);
  const [enabledTools, setEnabledTools] = useState<string[]>(
    TOOLS.filter((t) => t.connected).slice(0, 3).map((t) => t.id),
  );

  const canSend = value.trim().length > 0 && !isStreaming;
  const listening = aiState === 'listening';

  /* Auto-grow the textarea to a cinematic maximum */
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  const submit = useCallback(() => {
    if (!value.trim() || isStreaming) return;
    sendMessage(value);
    setValue('');
    inputRef.current?.focus();
  }, [isStreaming, sendMessage, value]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        submit();
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'm') {
        e.preventDefault();
        setVoiceActive(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [submit, setVoiceActive]);

  const attachedCount = enabledTools.length;
  const expanded = focused || value.length > 0;

  return (
    <div className={cx('relative', className)}>
      {/* Ambient under-glow, the "energy" beneath the bar */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -inset-x-8 -bottom-12 top-6 rounded-[40px] blur-[46px]"
        animate={{
          opacity: expanded ? 0.95 : 0.42,
          scale: expanded ? 1 : 0.94,
        }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        style={{
          background: `radial-gradient(60% 100% at 50% 100%, ${rgba(
            active.aura,
            0.22,
          )}, transparent 74%)`,
        }}
      />

      <motion.div
        animate={{
          y: expanded ? -2 : 0,
          scale: expanded ? 1.006 : 1,
        }}
        transition={{ type: 'spring', stiffness: 320, damping: 30 }}
        className={cx(
          'relative overflow-hidden rounded-[22px] border',
          'bg-obsidian-900/78 backdrop-blur-2xl',
        )}
        style={{
          borderColor: focused ? rgba(active.aura, 0.34) : 'rgba(255,255,255,0.075)',
          boxShadow: focused
            ? `0 34px 90px -34px rgba(0,0,0,0.95), 0 0 60px -20px ${rgba(
                active.aura,
                0.6,
              )}, inset 0 1px 0 0 rgba(255,255,255,0.07)`
            : '0 28px 70px -30px rgba(0,0,0,0.9), inset 0 1px 0 0 rgba(255,255,255,0.05)',
          transition:
            'border-color 500ms cubic-bezier(0.16,1,0.3,1), box-shadow 500ms cubic-bezier(0.16,1,0.3,1)',
        }}
      >
        {/* Top edge illumination */}
        <motion.span
          aria-hidden
          className="absolute inset-x-6 top-0 h-px"
          animate={{ opacity: focused ? 1 : 0.35 }}
          style={{
            background: `linear-gradient(90deg, transparent, ${rgba(
              active.aura,
              0.85,
            )}, transparent)`,
          }}
        />

        {/* Mode identity strip */}
        <div className="flex items-center gap-2 border-b border-white/[0.05] px-4 py-2.5">
          <ModeChip
            open={modeOpen}
            onToggle={() => {
              setModeOpen((o) => !o);
              setToolOpen(false);
            }}
            aura={active.aura}
            glyph={active.glyph}
            label={active.label}
          />

          <span className="h-3 w-px bg-white/10" />

          <ToolChip
            open={toolOpen}
            onToggle={() => {
              setToolOpen((o) => !o);
              setModeOpen(false);
            }}
            aura={active.aura}
            count={attachedCount}
          />

          <div className="ml-auto flex items-center gap-2">
            <span className="hidden font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55 sm:block">
              {settings.memory ? 'Memory engaged' : 'Memory off'}
            </span>
          </div>
        </div>

        {/* Mode / tool popovers */}
        <AnimatePresence>
          {modeOpen && (
            <Popover onDismiss={() => setModeOpen(false)}>
              <div className="grid gap-1 p-2 sm:grid-cols-2">
                {AI_MODES.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      setMode(m.id);
                      setModeOpen(false);
                    }}
                    className={cx(
                      'flex items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors duration-300',
                      m.id === mode ? 'bg-white/[0.06]' : 'hover:bg-white/[0.04]',
                    )}
                  >
                    <span className="mt-0.5 text-[1rem]" style={{ color: rgba(m.aura, 0.9) }}>
                      {m.glyph}
                    </span>
                    <span className="min-w-0">
                      <span className="block font-mono text-[10px] uppercase tracking-widest2 text-platinum">
                        {m.label}
                      </span>
                      <span className="mt-1 block text-[11.5px] leading-snug text-platinum-dim">
                        {m.caption}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </Popover>
          )}

          {toolOpen && (
            <Popover onDismiss={() => setToolOpen(false)}>
              <div className="p-2">
                <div className="px-2 py-1.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
                  Active toolset
                </div>
                {TOOLS.map((t) => {
                  const on = enabledTools.includes(t.id);
                  return (
                    <button
                      key={t.id}
                      type="button"
                      disabled={!t.connected}
                      onClick={() =>
                        setEnabledTools((prev) =>
                          prev.includes(t.id)
                            ? prev.filter((x) => x !== t.id)
                            : [...prev, t.id],
                        )
                      }
                      className={cx(
                        'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-300',
                        t.connected ? 'hover:bg-white/[0.04]' : 'opacity-35',
                      )}
                    >
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{
                          background: on ? rgba(active.aura, 0.95) : 'rgba(255,255,255,0.18)',
                          boxShadow: on ? `0 0 8px ${rgba(active.aura, 0.7)}` : 'none',
                        }}
                      />
                      <span className="flex-1 text-[12.5px] text-platinum-soft/88">
                        {t.name}
                      </span>
                      <span className="font-mono text-3xs uppercase tracking-wider text-platinum-dim/60">
                        {t.connected ? t.permission : 'offline'}
                      </span>
                    </button>
                  );
                })}
              </div>
            </Popover>
          )}
        </AnimatePresence>

        {/* Input row */}
        <div className="flex items-end gap-2 px-4 py-3.5">
          <label htmlFor="command-input" className="sr-only">
            Message AURELIS
          </label>
          <textarea
            id="command-input"
            ref={inputRef}
            value={value}
            rows={1}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={placeholder}
            className="max-h-[168px] min-h-[42px] flex-1 resize-none bg-transparent py-2.5 text-[14.5px] font-[350] leading-relaxed text-platinum placeholder:text-platinum-dim/45 focus:outline-none"
          />

          <div className="flex shrink-0 items-center gap-1.5">
            <IconButton
              label="Attach file"
              aura={active.aura}
              onClick={() => {
                setValue((v) => v || 'Analyse the attached document and summarise the key risks.');
              }}
            >
              <Paperclip className="h-4 w-4" />
            </IconButton>

            <IconButton
              label="Voice input"
              aura={active.aura}
              highlight={listening}
              onClick={() => setVoiceActive(true)}
            >
              <AudioLines className="h-4 w-4" />
            </IconButton>

            {isStreaming ? (
              <button
                type="button"
                onClick={stopResponse}
                className="flex h-9 items-center gap-2 rounded-full border border-white/[0.12] bg-white/[0.06] px-3.5 font-mono text-3xs uppercase tracking-widest2 text-platinum transition-colors hover:bg-white/[0.1]"
                aria-label="Stop response"
              >
                <Square className="h-3 w-3 fill-current" />
                Stop
              </button>
            ) : (
              <motion.button
                type="button"
                onClick={submit}
                disabled={!canSend}
                whileTap={{ scale: 0.94 }}
                className={cx(
                  'flex h-9 items-center gap-2 rounded-full border px-3.5 transition-all duration-400 ease-silk',
                  canSend
                    ? 'border-transparent text-obsidian-950'
                    : 'border-white/[0.08] bg-white/[0.04] text-platinum-dim',
                )}
                style={
                  canSend
                    ? {
                        background: `linear-gradient(135deg, rgba(255,255,255,0.96), ${rgba(
                          active.aura,
                          0.92,
                        )})`,
                        boxShadow: `0 0 28px -6px ${rgba(active.aura, 0.85)}`,
                      }
                    : undefined
                }
                aria-label="Send message"
              >
                <span className="font-mono text-3xs uppercase tracking-widest2">
                  {canSend ? 'Send' : 'Idle'}
                </span>
                <ArrowUp className="h-3.5 w-3.5" />
              </motion.button>
            )}
          </div>
        </div>

        {/* Shortcut rail */}
        <div className="flex items-center gap-4 border-t border-white/[0.045] px-4 py-2">
          <ShortcutHint
            keys={[mod, 'Enter']}
            label="Send"
            aura={active.aura}
            active={canSend}
          />
          <ShortcutHint keys={[mod, 'K']} label="Command" aura={active.aura} />
          <ShortcutHint keys={[mod, 'M']} label="Voice" aura={active.aura} />
          <span className="ml-auto hidden font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/45 sm:block">
            <CornerDownLeft className="mr-1.5 inline h-3 w-3" />
            Shift + Enter for a new line
          </span>
        </div>
      </motion.div>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────── */

function ModeChip({
  open,
  onToggle,
  aura,
  glyph,
  label,
}: {
  open: boolean;
  onToggle: () => void;
  aura: string;
  glyph: string;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-haspopup="listbox"
      className="flex items-center gap-2 rounded-full border px-3 py-1.5 transition-colors duration-400 hover:brightness-125"
      style={{
        borderColor: rgba(aura, 0.28),
        background: rgba(aura, 0.08),
      }}
    >
      <span className="text-[0.8rem] leading-none" style={{ color: rgba(aura, 0.95) }}>
        {glyph}
      </span>
      <span
        className="font-mono text-3xs uppercase tracking-widest2"
        style={{ color: rgba(aura, 0.95) }}
      >
        {label}
      </span>
      <ChevronDown
        className={cx(
          'h-3 w-3 transition-transform duration-400',
          open && 'rotate-180',
        )}
        style={{ color: rgba(aura, 0.7) }}
      />
    </button>
  );
}

function ToolChip({
  open,
  onToggle,
  aura,
  count,
}: {
  open: boolean;
  onToggle: () => void;
  aura: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.025] px-3 py-1.5 transition-colors duration-400 hover:border-white/[0.14] hover:bg-white/[0.05]"
    >
      <Wrench className="h-3 w-3 text-platinum-dim" />
      <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
        {count} tools
      </span>
      <ChevronDown
        className={cx('h-3 w-3 text-platinum-dim transition-transform duration-400', open && 'rotate-180')}
      />
      <span
        className="ml-0.5 h-1 w-1 rounded-full"
        style={{
          background: count > 0 ? rgba(aura, 0.9) : 'rgba(255,255,255,0.2)',
          boxShadow: count > 0 ? `0 0 6px ${rgba(aura, 0.8)}` : 'none',
        }}
      />
    </button>
  );
}

function Popover({
  children,
  onDismiss,
}: {
  children: React.ReactNode;
  onDismiss: () => void;
}) {
  return (
    <>
      <div className="fixed inset-0 z-20" onClick={onDismiss} aria-hidden />
      <motion.div
        initial={{ opacity: 0, y: -8, filter: 'blur(8px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        exit={{ opacity: 0, y: -8, filter: 'blur(8px)' }}
        transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
        className="glass-deep absolute left-3 right-3 z-30 mt-1 overflow-hidden rounded-2xl shadow-glass-lg sm:left-4 sm:right-auto sm:w-[420px]"
        style={{ top: '100%' }}
        role="dialog"
      >
        {children}
      </motion.div>
    </>
  );
}

function IconButton({
  children,
  label,
  aura,
  onClick,
  highlight = false,
}: {
  children: React.ReactNode;
  label: string;
  aura: string;
  onClick?: () => void;
  highlight?: boolean;
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={label}
      whileTap={{ scale: 0.92 }}
      className={cx(
        'relative flex h-9 w-9 items-center justify-center rounded-full border transition-colors duration-400',
        highlight
          ? 'text-platinum'
          : 'border-white/[0.07] bg-white/[0.025] text-platinum-dim hover:border-white/[0.15] hover:bg-white/[0.06] hover:text-platinum',
      )}
      style={
        highlight
          ? { borderColor: rgba(aura, 0.45), background: rgba(aura, 0.14) }
          : undefined
      }
    >
      {children}
      {highlight && (
        <motion.span
          className="absolute inset-0 rounded-full"
          style={{ border: `1px solid ${rgba(aura, 0.5)}` }}
          animate={{ scale: [1, 1.35], opacity: [0.7, 0] }}
          transition={{ duration: 1.9, repeat: Infinity, ease: 'easeOut' }}
        />
      )}
    </motion.button>
  );
}

function ShortcutHint({
  keys,
  label,
  aura,
  active = false,
}: {
  keys: string[];
  label: string;
  aura: string;
  active?: boolean;
}) {
  return (
    <span className="hidden items-center gap-2 sm:flex">
      <span className="flex items-center gap-1">
        {keys.map((k) => (
          <kbd
            key={k}
            className="rounded border px-1.5 py-0.5 font-mono text-[9px] transition-colors duration-400"
            style={{
              borderColor: active ? rgba(aura, 0.35) : 'rgba(255,255,255,0.09)',
              background: active ? rgba(aura, 0.1) : 'rgba(255,255,255,0.03)',
              color: active ? rgba(aura, 0.95) : 'rgba(143,149,163,0.85)',
            }}
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

/** Small helper used by the conversation header. */
export function useEnabledTools() {
  return useMemo(() => TOOLS.filter((t) => t.connected), []);
}