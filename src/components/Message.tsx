import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, ChevronDown, Cpu, Quote, RotateCcw, Volume2, Wrench } from 'lucide-react';
import { useState } from 'react';
import type { Message as MessageType, ToolTrace } from '@/types';
import { MODE_BY_ID } from '@/data/mock';
import { cx, formatRelative, rgba } from '@/lib/utils';
import { BlockRenderer, ThinkingIndicator } from '@/components/MessageBlocks';

interface MessageProps {
  message: MessageType;
  showTrace?: boolean;
  reasoning?: string;
  traces?: ToolTrace[];
  onSuggestion?: (text: string) => void;
  onRetry?: (messageId: string) => void;
  isLast?: boolean;
}

export function Message({
  message,
  showTrace = false,
  reasoning,
  traces,
  onSuggestion,
  onRetry,
}: MessageProps) {
  const mode = MODE_BY_ID[message.mode];
  const isUser = message.role === 'user';

  if (isUser) return <UserMessage message={message} />;

  const streaming = message.status === 'streaming';
  const failed = message.status === 'failed' || message.status === 'cancelled';

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      className="group/msg relative"
      aria-label="AURELIS response"
    >
      <div className="flex gap-4 lg:gap-6">
        {/* AI identity marker */}
        <div className="relative shrink-0">
          <IdentityMark aura={mode.aura} />
          <span
            aria-hidden
            className="absolute left-1/2 top-11 bottom-0 w-px -translate-x-1/2 bg-gradient-to-b from-white/10 to-transparent"
          />
        </div>

        {/* Response body */}
        <div className="min-w-0 flex-1 pt-1">
          <header className="mb-5 flex flex-wrap items-center gap-x-3.5 gap-y-2">
            <span className="text-[12px] font-normal tracking-[0.22em] text-platinum">
              AURELIS
            </span>
            <span
              className="rounded-full border px-2.5 py-0.5 font-mono text-3xs uppercase tracking-widest2"
              style={{
                borderColor: rgba(mode.aura, 0.26),
                background: rgba(mode.aura, 0.07),
                color: rgba(mode.aura, 0.92),
              }}
            >
              {mode.label}
            </span>
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
              {formatRelative(message.createdAt)}
            </span>
            {message.tokens ? (
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/45">
                {message.tokens} tok
              </span>
            ) : null}
            {message.model ? (
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/40">
                {message.model}
              </span>
            ) : null}
            {message.latencyMs ? (
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/40">
                {(message.latencyMs / 1000).toFixed(1)}s
              </span>
            ) : null}
            {streaming && (
              <span
                className="flex items-center gap-1.5 font-mono text-3xs uppercase tracking-widest2"
                style={{ color: rgba(mode.aura, 0.85) }}
              >
                <motion.span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: rgba(mode.aura, 0.9) }}
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1.2, repeat: Infinity }}
                />
                Streaming
              </span>
            )}
            {message.voice && (
              <span className="flex items-center gap-1.5 font-mono text-3xs uppercase tracking-widest2 text-champagne/70">
                <Volume2 className="h-3 w-3" />
                spoken
              </span>
            )}
          </header>

          {/* Reasoning + tool trace */}
          {(reasoning || (traces && traces.length > 0)) && (
            <TracePanel reasoning={reasoning} traces={traces} aura={mode.aura} />
          )}

          {showTrace && (!message.blocks || message.blocks.length === 0) && (
            <ThinkingIndicator aura={mode.aura} label="Reasoning" />
          )}

          {/* Content */}
          <div className="space-y-6">
            {message.blocks.map((block, i) => (
              <BlockRenderer
                key={`${message.id}-${i}`}
                block={block}
                aura={mode.aura}
                index={i}
                onSuggestion={onSuggestion}
              />
            ))}
            {streaming && message.blocks.length > 0 && (
              <span
                aria-hidden
                className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[2px] animate-pulse rounded-full"
                style={{ background: rgba(mode.aura, 0.9) }}
              />
            )}
          </div>

          {/* A failed or cancelled generation is stated plainly and offered a
              retry, rather than leaving a truncated answer looking final. */}
          {failed && (
            <div
              role="status"
              className="mt-5 flex flex-wrap items-center gap-3 rounded-xl border px-3.5 py-2.5"
              style={{
                borderColor: rgba('226 132 132', 0.28),
                background: rgba('226 132 132', 0.05),
              }}
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" style={{ color: rgba('226 132 132', 0.9) }} />
              <span className="flex-1 text-[12.5px] text-platinum-soft/80">
                {message.status === 'cancelled'
                  ? 'Generation stopped.'
                  : 'This response did not finish.'}
              </span>
              {onRetry && message.failedPrompt && (
                <button
                  type="button"
                  onClick={() => onRetry(message.id)}
                  className="flex items-center gap-1.5 rounded-lg border border-white/[0.1] px-2.5 py-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors hover:bg-white/[0.05] hover:text-platinum"
                >
                  <RotateCcw className="h-3 w-3" />
                  Retry
                </button>
              )}
            </div>
          )}

          {/* Response footer actions */}
          {message.blocks.length > 0 && !streaming && !failed && (
            <div className="mt-6 flex items-center gap-1 opacity-0 transition-opacity duration-500 group-hover/msg:opacity-100 focus-within:opacity-100">
              <FooterAction label="Copy" icon={Quote} />
              <FooterAction label="Speak" icon={Volume2} />
              <FooterAction label="Trace" icon={Cpu} />
            </div>
          )}
        </div>
      </div>
    </motion.article>
  );
}

function FooterAction({
  label,
  icon: Icon,
}: {
  label: string;
  icon: typeof Quote;
}) {
  return (
    <button
      type="button"
      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70 transition-colors duration-400 hover:bg-white/[0.05] hover:text-platinum"
    >
      <Icon className="h-3 w-3" />
      {label}
    </button>
  );
}

/** The layered glass + light identity mark that opens every response. */
function IdentityMark({ aura }: { aura: string }) {
  return (
    <span className="relative flex h-9 w-9 items-center justify-center">
      <motion.span
        aria-hidden
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, ${rgba(aura, 0.28)}, transparent 68%)`,
        }}
        animate={{ opacity: [0.6, 1, 0.6], scale: [1, 1.14, 1] }}
        transition={{ duration: 4.6, repeat: Infinity, ease: 'easeInOut' }}
      />
      <span
        className="absolute inset-0 rounded-full border"
        style={{ borderColor: rgba(aura, 0.28) }}
      />
      <span
        className="absolute inset-[7px] rounded-full"
        style={{
          background: `radial-gradient(circle at 38% 32%, #fff 0%, ${rgba(
            aura,
            0.9,
          )} 38%, ${rgba(aura, 0.22)} 76%, transparent 92%)`,
        }}
      />
    </span>
  );
}

/* ─ Collapsible reasoning + tool execution ────────────────────── */

function TracePanel({
  reasoning,
  traces,
  aura,
}: {
  reasoning?: string;
  traces?: ToolTrace[];
  aura: string;
}) {
  const [open, setOpen] = useState(false);
  const anyRunning = (traces ?? []).some((t) => t.state === 'running');
  const count = traces?.length ?? 0;

  return (
    <div className="mb-5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cx(
          'flex w-full items-center gap-3 rounded-xl border px-3.5 py-2.5 text-left transition-colors duration-400',
          open
            ? 'border-white/[0.11] bg-white/[0.035]'
            : 'border-white/[0.06] bg-white/[0.015] hover:border-white/[0.11] hover:bg-white/[0.03]',
        )}
      >
        <span className="relative flex h-5 w-5 shrink-0 items-center justify-center">
          {anyRunning ? (
            <motion.span
              className="absolute inset-0 rounded-full border-t border-r"
              style={{ borderColor: rgba(aura, 0.9) }}
              animate={{ rotate: 360 }}
              transition={{ duration: 1.4, repeat: Infinity, ease: 'linear' }}
            />
          ) : (
            <span
              className="absolute inset-0 rounded-full border"
              style={{ borderColor: rgba(aura, 0.3) }}
            />
          )}
          <Wrench className="h-2.5 w-2.5" style={{ color: rgba(aura, 0.9) }} />
        </span>

        <span className="flex-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
          {anyRunning
            ? 'Working'
            : count > 0
              ? `${count} ${count === 1 ? 'operation' : 'operations'} completed`
              : 'Reasoning trace'}
        </span>

        {/* Operation pips */}
        <span className="hidden items-center gap-1 sm:flex">
          {(traces ?? []).map((t) => (
            <motion.span
              key={t.id}
              className="h-1.5 w-1.5 rounded-full"
              style={{
                background:
                  t.state === 'running' ? rgba('216 195 154', 0.95) : rgba(aura, 0.75),
              }}
              animate={t.state === 'running' ? { opacity: [0.35, 1, 0.35] } : undefined}
              transition={{ duration: 1.2, repeat: Infinity }}
            />
          ))}
        </span>

        <ChevronDown
          className={cx(
            'h-3.5 w-3.5 shrink-0 text-platinum-dim transition-transform duration-500 ease-cinematic',
            open && 'rotate-180',
          )}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-3 rounded-xl border border-white/[0.06] bg-white/[0.012] p-4">
              {reasoning && (
                <div>
                  <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
                    Approach
                  </div>
                  <p className="mt-2 text-[12.5px] leading-relaxed text-platinum-soft/75">
                    {reasoning}
                  </p>
                </div>
              )}

              {traces && traces.length > 0 && (
                <div className="space-y-2 pt-1">
                  <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
                    Tool execution
                  </div>
                  <ul className="space-y-1.5">
                    {traces.map((t) => (
                      <li
                        key={t.id}
                        className="flex items-center gap-3 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2"
                      >
                        <motion.span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{
                            background:
                              t.state === 'running'
                                ? rgba('216 195 154', 1)
                                : rgba(aura, 0.8),
                          }}
                          animate={
                            t.state === 'running' ? { opacity: [0.3, 1, 0.3] } : undefined
                          }
                          transition={{ duration: 1.1, repeat: Infinity }}
                        />
                        <span className="text-[12.5px] text-platinum-soft/85">{t.name}</span>
                        <span className="min-w-0 flex-1 truncate font-mono text-3xs uppercase tracking-wider text-platinum-dim/60">
                          {t.detail}
                        </span>
                        <span className="shrink-0 font-mono text-3xs tabular-nums text-platinum-dim/70">
                          {t.state === 'running'
                            ? '…'
                            : t.durationMs
                              ? `${(t.durationMs / 1000).toFixed(2)}s`
                              : 'done'}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── User message ────────────────────────────────────────────── */

function UserMessage({ message }: { message: MessageType }) {
  const body = message.blocks
    .filter((b): b is Extract<typeof b, { kind: 'text' }> => b.kind === 'text')
    .map((b) => b.body)
    .join('\n\n');

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      className="flex justify-end"
    >
      <div className="group/user relative max-w-[76ch]">
        <div className="mb-2.5 flex items-center justify-end gap-3">
          <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
            {formatRelative(message.createdAt)}
          </span>
          <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
            You
          </span>
        </div>
        <div
          className={cx(
            'relative overflow-hidden rounded-2xl rounded-tr-md border border-white/[0.08] px-5 py-4',
            'bg-gradient-to-br from-white/[0.075] to-white/[0.025]',
          )}
        >
          <span
            aria-hidden
            className="absolute inset-y-4 right-0 w-px bg-gradient-to-b from-transparent via-champagne/45 to-transparent"
          />
          <p className="whitespace-pre-wrap text-[14.5px] font-[350] leading-[1.72] text-platinum/95">
            {body}
          </p>
        </div>
      </div>
    </motion.div>
  );
}