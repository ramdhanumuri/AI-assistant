import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDown, GitBranch, Layers, Pin } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '@/state/AppContext';
import { MODE_BY_ID, PROMPT_SUGGESTIONS } from '@/data/mock';
import { rgba } from '@/lib/utils';
import { Message } from '@/components/Message';
import { CommandBar } from '@/components/CommandBar';
import { ModeSelector } from '@/components/ModeSelector';
import { AIOrb } from '@/components/AIOrb';
import { ParticleField } from '@/components/AmbientBackground';
import { SectionLabel, StatusPill } from '@/components/Primitives';

export function ChatInterface() {
  const {
    messages,
    mode,
    aiState,
    reasoning,
    traces,
    isStreaming,
    sendMessage,
    retryMessage,
    aiCapabilities,
    activeConversationId,
    conversations,
    settings,
    setView,
  } = useApp();

  const active = MODE_BY_ID[mode];
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [pinned, setPinned] = useState(true);
  const [showJump, setShowJump] = useState(false);

  const conversation = useMemo(
    () => conversations.find((c) => c.id === activeConversationId) ?? null,
    [conversations, activeConversationId],
  );

  const scrollToEnd = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  }, []);

  useEffect(() => {
    if (pinned) scrollToEnd(isStreaming ? 'auto' : 'smooth');
  }, [messages, reasoning, traces, pinned, isStreaming, scrollToEnd]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distance < 96;
    setPinned(atBottom);
    setShowJump(!atBottom && messages.length > 2);
  };

  const isEmpty = messages.length === 0 && !isStreaming;
  // A provider that is selected but not configured is surfaced before the user
  // types, rather than letting the first send fail at the model.
  const unconfigured = aiCapabilities != null && !aiCapabilities.configured;

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      {settings.particles && <ParticleField aura={active.aura} count={26} />}

      {unconfigured && (
        <div className="relative z-10 mx-5 mt-2 rounded-xl border border-amber-300/20 bg-amber-300/[0.04] px-4 py-2.5 lg:mx-10">
          <p className="text-[12.5px] text-platinum-soft/80">
            The AI provider ({aiCapabilities?.provider}) is not configured on this
            deployment. An administrator must set its API key before messages can be
            answered.
          </p>
        </div>
      )}

      {/* Thread header */}
      <div className="relative z-10 shrink-0 px-5 pt-1 pb-4 lg:px-10">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2.5">
              <h2 className="truncate text-[1.05rem] font-light tracking-[0.02em] text-platinum">
                {conversation?.title ?? 'New private thread'}
              </h2>
              {conversation?.pinned && (
                <Pin className="h-3 w-3 shrink-0 text-champagne/70" />
              )}
            </div>
            <div className="mt-1.5 flex items-center gap-2.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/65">
              {conversation?.project && (
                <>
                  <span className="text-champagne/70">{conversation.project}</span>
                  <span className="opacity-40">·</span>
                </>
              )}
              <span>{messages.length} messages</span>
              <span className="opacity-40">·</span>
              <span>{active.label} mode</span>
            </div>
          </div>

          <StatusPill
            label={aiState === 'idle' ? 'In sync' : aiState}
            aura={active.aura}
            pulse={aiState !== 'idle'}
          />
        </div>

        <div className="mt-4">
          <ModeSelector className="mask-fade-edges" />
        </div>
      </div>

      <div className="hairline relative z-10 mx-5 shrink-0 lg:mx-10" />

      {/* Transcript */}
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-8 lg:px-10"
        role="log"
        aria-live="polite"
        aria-label="Conversation transcript"
      >
        <div className="mx-auto w-full max-w-[860px]">
          <AnimatePresence mode="wait">
            {isEmpty ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0, y: 20, filter: 'blur(10px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -12, filter: 'blur(10px)' }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col items-center pt-6 text-center lg:pt-14"
              >
                <AIOrb
                  state="idle"
                  aura={active.aura}
                  size={208}
                  particles={settings.particles}
                />
                <h3 className="mt-10 text-[1.75rem] font-extralight tracking-[-0.01em] text-platinum sm:text-[2.1rem]">
                  Your intelligence layer is ready.
                </h3>
                <p className="mt-4 max-w-[52ch] text-[14px] leading-relaxed text-platinum-soft/65">
                  {active.description}
                </p>

                <div className="mt-9 grid w-full gap-2.5 sm:grid-cols-2">
                  {PROMPT_SUGGESTIONS.map((s, i) => (
                    <motion.button
                      key={s.id}
                      type="button"
                      initial={{ opacity: 0, y: 14 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.6, delay: 0.25 + i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                      onClick={() => sendMessage(s.prompt)}
                      className="group relative overflow-hidden rounded-xl border border-white/[0.065] bg-white/[0.018] p-4 text-left transition-all duration-500 ease-cinematic hover:-translate-y-0.5 hover:border-white/[0.15] hover:bg-white/[0.04]"
                    >
                      <span
                        aria-hidden
                        className="pointer-events-none absolute inset-x-5 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                        style={{
                          background: `linear-gradient(90deg, transparent, ${rgba(active.aura, 0.7)}, transparent)`,
                        }}
                      />
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim group-hover:text-platinum">
                          {s.label}
                        </span>
                        <span
                          className="text-[10px] opacity-0 transition-all duration-500 group-hover:translate-x-0.5 group-hover:opacity-100"
                          style={{ color: rgba(active.aura, 0.9) }}
                        >
                          →
                        </span>
                      </div>
                      <p className="mt-2.5 text-[12.5px] leading-relaxed text-platinum-soft/60 group-hover:text-platinum-soft/80">
                        {s.prompt}
                      </p>
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="thread"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-10"
              >
                {messages.map((m, i) => {
                  const isStreamingTurn =
                    m.role === 'assistant' &&
                    isStreaming &&
                    i === messages.length - 1;
                  return (
                    <Message
                      key={m.id}
                      message={m}
                      reasoning={isStreamingTurn ? reasoning : undefined}
                      traces={isStreamingTurn ? traces : undefined}
                      showTrace={isStreamingTurn && m.blocks.length === 0}
                      onSuggestion={sendMessage}
                      onRetry={retryMessage}
                      isLast={i === messages.length - 1}
                    />
                  );
                })}

                {/* Live reasoning before the first block lands */}
                {isStreaming &&
                  aiState === 'thinking' &&
                  messages[messages.length - 1]?.role === 'user' && (
                    <div className="flex gap-4 lg:gap-6">
                      <div className="w-9 shrink-0" />
                      <div className="flex-1 pt-1">
                        <LiveThinking aura={active.aura} reasoning={reasoning} />
                      </div>
                    </div>
                  )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Jump to latest */}
      <AnimatePresence>
        {showJump && (
          <motion.button
            type="button"
            initial={{ opacity: 0, y: 10, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.9 }}
            onClick={() => {
              setPinned(true);
              scrollToEnd();
            }}
            className="glass absolute bottom-[188px] left-1/2 z-20 flex h-9 -translate-x-1/2 items-center gap-2 rounded-full px-4 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors hover:text-platinum"
            aria-label="Scroll to latest"
          >
            <ArrowDown className="h-3 w-3" />
            Latest
          </motion.button>
        )}
      </AnimatePresence>

      {/* Command bar dock */}
      <div className="relative z-20 shrink-0 px-4 pb-5 pt-2 lg:px-10">
        <div className="mx-auto w-full max-w-[860px]">
          <CommandBar />
          <div className="mt-3 flex items-center justify-center gap-4 text-center">
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/40">
              AURELIS can be wrong · verify consequential output
            </span>
            <button
              type="button"
              onClick={() => setView('dashboard')}
              className="hidden items-center gap-1.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55 transition-colors hover:text-platinum sm:flex"
            >
              <Layers className="h-3 w-3" />
              Trace this thread
            </button>
            <button
              type="button"
              onClick={() => setView('knowledge')}
              className="hidden items-center gap-1.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55 transition-colors hover:text-platinum md:flex"
            >
              <GitBranch className="h-3 w-3" />
              Sources
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─ Live reasoning stream ──────────────────────────────────────── */

function LiveThinking({ aura, reasoning }: { aura: string; reasoning: string }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3.5">
        <span className="relative flex h-9 w-9 items-center justify-center">
          <motion.span
            className="absolute inset-0 rounded-full"
            style={{ background: `radial-gradient(circle, ${rgba(aura, 0.25)}, transparent 68%)` }}
            animate={{ opacity: [0.5, 1, 0.5], scale: [1, 1.18, 1] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
          />
          <span
            className="absolute inset-0 rounded-full border"
            style={{ borderColor: rgba(aura, 0.28) }}
          />
          <motion.span
            className="absolute inset-[-4px] rounded-full border-t"
            style={{ borderColor: rgba(aura, 0.9) }}
            animate={{ rotate: 360 }}
            transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
          />
          <span
            className="h-[11px] w-[11px] rounded-full"
            style={{
              background: `radial-gradient(circle at 38% 32%, #fff, ${rgba(aura, 0.9)} 55%, transparent)`,
            }}
          />
        </span>
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[10px] uppercase tracking-widest3 text-platinum">
            Reasoning
          </span>
          <motion.span
            className="font-mono text-3xs uppercase tracking-widest2"
            style={{ color: rgba(aura, 0.85) }}
            animate={{ opacity: [0.45, 1, 0.45] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            live
          </motion.span>
        </div>
      </div>

      {reasoning && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="max-w-[64ch] pl-[50px] text-[13.5px] font-[350] italic leading-[1.75] text-platinum-soft/60"
        >
          {reasoning}
          <motion.span
            className="ml-0.5 inline-block h-[13px] w-[2px] translate-y-[2px]"
            style={{ background: rgba(aura, 0.9) }}
            animate={{ opacity: [1, 0, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
          />
        </motion.p>
      )}
    </div>
  );
}

/** Exported so other surfaces can reuse the section framing. */
export { SectionLabel };