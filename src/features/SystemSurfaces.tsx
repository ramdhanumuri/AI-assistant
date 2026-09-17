import { motion } from 'framer-motion';
import {
  Brain,
  Database,
  FileText,
  FolderKanban,
  GitBranch,
  ListOrdered,
  Pause,
  Plug,
  RefreshCw,
  Sparkles,
  Table2,
  Rss,
} from 'lucide-react';
import { useApp } from '@/state/AppContext';
import {
  CONVERSATIONS,
  KNOWLEDGE_SOURCES,
  MEMORY,
  MODE_BY_ID,
  PROJECTS,
  TOOLS,
} from '@/data/mock';
import { cx, formatRelative, rgba } from '@/lib/utils';
import { GlassCard, SectionLabel, Button } from '@/components/Primitives';

/* ── Projects ──────────────────────────────────────────────────── */

export function ProjectsSurface() {
  const { openConversation, setView, mode } = useApp();
  const active = MODE_BY_ID[mode];

  return (
    <SurfaceFrame
      eyebrow="Workstreams"
      title="Projects"
      caption="Context carried across threads, memory and tool access."
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {PROJECTS.map((p, i) => {
          const threads = CONVERSATIONS.filter((c) => c.project === p.name);
          return (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            >
              <GlassCard interactive aura={p.accent} className="h-full p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{
                          background: rgba(p.accent, 0.95),
                          boxShadow: `0 0 12px ${rgba(p.accent, 0.8)}`,
                        }}
                      />
                      <h3 className="text-[1.05rem] font-light tracking-wide text-platinum">
                        {p.name}
                      </h3>
                    </div>
                    <p className="mt-3 max-w-[46ch] text-[12.5px] leading-relaxed text-platinum-soft/65">
                      {p.brief}
                    </p>
                  </div>
                  <FolderKanban
                    className="h-4 w-4 shrink-0"
                    style={{ color: rgba(p.accent, 0.7) }}
                  />
                </div>

                <div className="mt-6 flex items-center gap-5">
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
                        Completion
                      </span>
                      <span
                        className="font-mono text-3xs tabular-nums"
                        style={{ color: rgba(p.accent, 0.9) }}
                      >
                        {Math.round(p.progress * 100)}%
                      </span>
                    </div>
                    <div className="mt-2.5 h-px w-full bg-white/[0.06]">
                      <motion.div
                        className="h-px"
                        initial={{ width: 0 }}
                        animate={{ width: `${p.progress * 100}%` }}
                        transition={{ duration: 1.3, delay: 0.3 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                        style={{
                          background: `linear-gradient(90deg, transparent, ${rgba(p.accent, 0.95)})`,
                        }}
                      />
                    </div>
                  </div>
                  <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
                    {p.threads} threads
                  </span>
                </div>

                {threads.length > 0 && (
                  <div className="mt-6 space-y-1.5">
                    {threads.slice(0, 3).map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => openConversation(t.id)}
                        className="group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-400 hover:bg-white/[0.035]"
                      >
                        <GitBranch className="h-3 w-3 shrink-0 text-platinum-dim/60" />
                        <span className="min-w-0 flex-1 truncate text-[12.5px] text-platinum-soft/80 transition-colors group-hover:text-platinum">
                          {t.title}
                        </span>
                        <span className="shrink-0 font-mono text-3xs uppercase tracking-wider text-platinum-dim/50">
                          {formatRelative(t.updatedAt)}
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                <div className="mt-6 flex gap-2">
                  <Button size="sm" aura={p.accent} onClick={() => setView('conversation')}>
                    Open workstream
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setView('knowledge')}>
                    Sources
                  </Button>
                </div>
              </GlassCard>
            </motion.div>
          );
        })}
      </div>
      <p className="mt-6 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/40">
        Current mode · {active.label}
      </p>
    </SurfaceFrame>
  );
}

/* ── Knowledge ─────────────────────────────────────────────────── */

const KIND_ICON = {
  document: FileText,
  repository: GitBranch,
  dataset: Table2,
  feed: Rss,
};

export function KnowledgeSurface() {
  const { mode } = useApp();
  const active = MODE_BY_ID[mode];
  const total = KNOWLEDGE_SOURCES.reduce((a, k) => a + k.items, 0);

  return (
    <SurfaceFrame
      eyebrow="Indexed corpus"
      title="Knowledge"
      caption={`${total.toLocaleString()} items indexed and retrievable with provenance.`}
    >
      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <GlassCard layer="raised" className="p-6">
          <SectionLabel
            trailing={
              <span className="flex items-center gap-2 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
                <RefreshCw className="h-3 w-3" />
                Auto-sync
              </span>
            }
          >
            Sources
          </SectionLabel>
          <ul className="mt-5 space-y-2">
            {KNOWLEDGE_SOURCES.map((k, i) => {
              const Icon = KIND_ICON[k.kind];
              const tone =
                k.status === 'indexing'
                  ? '216 195 154'
                  : k.status === 'paused'
                    ? '139 147 163'
                    : active.aura;
              return (
                <motion.li
                  key={k.id}
                  initial={{ opacity: 0, x: 14 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.6, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                >
                  <div className="group flex items-center gap-4 rounded-xl border border-white/[0.05] bg-white/[0.012] p-4 transition-colors duration-400 hover:border-white/[0.12] hover:bg-white/[0.03]">
                    <span
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border"
                      style={{
                        borderColor: rgba(tone, 0.24),
                        background: rgba(tone, 0.07),
                      }}
                    >
                      <Icon className="h-4 w-4" style={{ color: rgba(tone, 0.9) }} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] text-platinum/90">{k.name}</div>
                      <div className="mt-1.5 flex items-center gap-2.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
                        <span>{k.kind}</span>
                        <span className="opacity-40">·</span>
                        <span className="tabular-nums">{k.items.toLocaleString()} items</span>
                        <span className="opacity-40">·</span>
                        <span>{k.updated}</span>
                      </div>
                    </div>
                    <span
                      className="shrink-0 font-mono text-3xs uppercase tracking-widest2"
                      style={{ color: rgba(tone, 0.9) }}
                    >
                      {k.status}
                    </span>
                  </div>
                </motion.li>
              );
            })}
          </ul>
        </GlassCard>

        <div className="space-y-4">
          <GlassCard layer="raised" className="p-6">
            <SectionLabel>Retrieval posture</SectionLabel>
            <div className="mt-6 space-y-5">
              {[
                { label: 'Vector coverage', value: 0.94 },
                { label: 'Freshness (< 24h)', value: 0.81 },
                { label: 'Provenance linked', value: 0.99 },
                { label: 'Duplicate suppression', value: 0.88 },
              ].map((m, i) => (
                <div key={m.label}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
                      {m.label}
                    </span>
                    <span className="font-mono text-3xs tabular-nums text-platinum-soft/85">
                      {Math.round(m.value * 100)}%
                    </span>
                  </div>
                  <div className="mt-2.5 h-[3px] w-full overflow-hidden rounded-full bg-white/[0.055]">
                    <motion.div
                      className="h-full rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${m.value * 100}%` }}
                      transition={{ duration: 1.2, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                      style={{
                        background: `linear-gradient(90deg, ${rgba(active.aura, 0.35)}, ${rgba(
                          active.aura,
                          0.95,
                        )})`,
                        boxShadow: `0 0 12px ${rgba(active.aura, 0.55)}`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard layer="flat" className="p-6">
            <div className="flex items-center gap-2.5">
              <ListOrdered className="h-3.5 w-3.5 text-champagne/80" />
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                Indexing schedule
              </span>
            </div>
            <p className="mt-3.5 text-[12.5px] leading-relaxed text-platinum-soft/68">
              Incremental re-index runs every 15 minutes. Full rebuilds occur nightly
              at 02:00 UTC and complete without interrupting retrieval.
            </p>
            <div className="mt-4 flex items-center gap-2 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
              <Pause className="h-3 w-3" />
              Next incremental in 6 min
            </div>
          </GlassCard>
        </div>
      </div>
    </SurfaceFrame>
  );
}

/* ── Tools ─────────────────────────────────────────────────────── */

export function ToolsSurface() {
  const { mode, notify } = useApp();
  const active = MODE_BY_ID[mode];
  const totalCalls = TOOLS.reduce((a, t) => a + t.calls, 0);

  return (
    <SurfaceFrame
      eyebrow="Capability layer"
      title="Tools"
      caption={`${TOOLS.filter((t) => t.connected).length} connected · ${totalCalls.toLocaleString()} calls this cycle.`}
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {TOOLS.map((t, i) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
          >
            <GlassCard interactive aura={active.aura} className="h-full p-5">
              <div className="flex items-start justify-between gap-4">
                <span
                  className="flex h-10 w-10 items-center justify-center rounded-lg border"
                  style={{
                    borderColor: t.connected
                      ? rgba(active.aura, 0.24)
                      : 'rgba(255,255,255,0.07)',
                    background: t.connected
                      ? rgba(active.aura, 0.07)
                      : 'rgba(255,255,255,0.02)',
                  }}
                >
                  <Plug
                    className="h-4 w-4"
                    style={{
                      color: t.connected
                        ? rgba(active.aura, 0.9)
                        : 'rgba(143,149,163,0.6)',
                    }}
                  />
                </span>
                <span
                  className="flex items-center gap-2 font-mono text-3xs uppercase tracking-widest2"
                  style={{
                    color: t.connected
                      ? rgba(active.aura, 0.9)
                      : 'rgba(143,149,163,0.65)',
                  }}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{
                      background: t.connected
                        ? rgba(active.aura, 0.95)
                        : 'rgba(255,255,255,0.18)',
                    }}
                  />
                  {t.connected ? 'connected' : 'offline'}
                </span>
              </div>

              <h3 className="mt-5 text-[14px] font-light text-platinum/92">{t.name}</h3>
              <div className="mt-2 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
                {t.category} · {t.permission}
              </div>

              <div className="mt-5 flex items-end justify-between">
                <div>
                  <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                    Calls
                  </div>
                  <div className="mt-1.5 text-[1.35rem] font-extralight tabular-nums text-platinum-soft/90">
                    {t.calls.toLocaleString()}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    notify(
                      t.connected
                        ? `${t.name} disconnected`
                        : `${t.name} requested — awaiting approval`,
                    )
                  }
                  className={cx(
                    'rounded-full border px-3.5 py-1.5 font-mono text-3xs uppercase tracking-widest2 transition-colors duration-400',
                    t.connected
                      ? 'border-white/[0.09] text-platinum-dim hover:border-white/[0.18] hover:text-platinum'
                      : 'text-platinum',
                  )}
                  style={
                    t.connected
                      ? undefined
                      : {
                          borderColor: rgba(active.aura, 0.32),
                          background: rgba(active.aura, 0.09),
                        }
                  }
                >
                  {t.connected ? 'Revoke' : 'Connect'}
                </button>
              </div>
            </GlassCard>
          </motion.div>
        ))}
      </div>
    </SurfaceFrame>
  );
}

/* ── Memory ────────────────────────────────────────────────────── */

export function MemorySurface() {
  const { mode, settings, updateSettings } = useApp();
  const active = MODE_BY_ID[mode];

  return (
    <SurfaceFrame
      eyebrow="Learned context"
      title="Memory"
      caption={`${MEMORY.length} active records · ${settings.memory ? 'persistence enabled' : 'persistence disabled'}.`}
    >
      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <GlassCard layer="raised" className="p-6">
          <SectionLabel
            trailing={
              <button
                type="button"
                onClick={() => updateSettings({ memory: !settings.memory })}
                className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60 transition-colors hover:text-platinum"
              >
                {settings.memory ? 'Disable persistence' : 'Enable persistence'}
              </button>
            }
          >
            Records
          </SectionLabel>
          <ul className="mt-5 space-y-2.5">
            {MEMORY.map((m, i) => (
              <motion.li
                key={m.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                className="group rounded-xl border border-white/[0.05] bg-white/[0.012] p-4 transition-colors duration-400 hover:border-white/[0.12] hover:bg-white/[0.03]"
              >
                <div className="flex items-start gap-3.5">
                  <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-champagne/70" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] leading-relaxed text-platinum-soft/88">
                      {m.statement}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <span
                        className="rounded-full border px-2.5 py-0.5 font-mono text-3xs uppercase tracking-widest2"
                        style={{
                          borderColor: rgba(active.aura, 0.22),
                          background: rgba(active.aura, 0.06),
                          color: rgba(active.aura, 0.9),
                        }}
                      >
                        {m.scope}
                      </span>
                      <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                        learned {m.learned}
                      </span>
                      <span className="ml-auto font-mono text-3xs tabular-nums text-platinum-soft/75">
                        {Math.round(m.confidence * 100)}% confidence
                      </span>
                    </div>
                  </div>
                </div>
              </motion.li>
            ))}
          </ul>
        </GlassCard>

        <div className="space-y-4">
          <GlassCard layer="raised" className="p-6">
            <div className="flex items-center gap-2.5">
              <Brain className="h-3.5 w-3.5 text-champagne/80" />
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                How memory is used
              </span>
            </div>
            <ul className="mt-4 space-y-3.5">
              {[
                'Preferences shape tone, structure and level of detail.',
                'Project context is attached automatically to related threads.',
                'Low-confidence records are surfaced rather than silently applied.',
                'You can inspect and revoke any record at any time.',
              ].map((line, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className="mt-[7px] h-[5px] w-[5px] shrink-0 rotate-45"
                    style={{ background: rgba(active.aura, 0.7) }}
                  />
                  <span className="text-[12.5px] leading-relaxed text-platinum-soft/70">
                    {line}
                  </span>
                </li>
              ))}
            </ul>
          </GlassCard>

          <GlassCard layer="flat" className="p-6">
            <div className="flex items-center gap-2.5">
              <Database className="h-3.5 w-3.5 text-platinum-dim" />
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                Storage
              </span>
            </div>
            <div className="mt-4 flex items-baseline gap-2.5">
              <span className="text-[1.7rem] font-extralight tabular-nums text-platinum">
                1,284
              </span>
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
                records · 18.4 MB
              </span>
            </div>
            <p className="mt-3.5 text-[12px] leading-relaxed text-platinum-soft/62">
              Stored locally and encrypted at rest. No memory content leaves your boundary.
            </p>
          </GlassCard>
        </div>
      </div>
    </SurfaceFrame>
  );
}

/* ── Shared surface frame ──────────────────────────────────────── */

function SurfaceFrame({
  eyebrow,
  title,
  caption,
  children,
}: {
  eyebrow: string;
  title: string;
  caption: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative min-h-0 flex-1 overflow-y-auto px-5 py-7 lg:px-10">
      <div className="mx-auto w-full max-w-[1280px]">
        <motion.header
          initial={{ opacity: 0, y: 14, filter: 'blur(8px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="mb-8"
        >
          <div className="eyebrow flex items-center gap-3">
            <span className="h-px w-6 bg-white/20" />
            {eyebrow}
          </div>
          <h2 className="mt-4 text-[clamp(1.9rem,4vw,2.7rem)] font-extralight tracking-[-0.02em] gradient-platinum">
            {title}
          </h2>
          <p className="mt-3.5 max-w-[62ch] text-[13.5px] leading-relaxed text-platinum-soft/62">
            {caption}
          </p>
        </motion.header>
        {children}
      </div>
    </div>
  );
}