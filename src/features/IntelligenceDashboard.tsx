import { motion } from 'framer-motion';
import {
  ArrowUpRight,
  Boxes,
  Database,
  Gauge,
  Library,
  Plug,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { useApp } from '@/state/AppContext';
import {
  ACTIVITY_FEED,
  CONVERSATIONS,
  KNOWLEDGE_SOURCES,
  MEMORY,
  MODE_BY_ID,
  PROJECTS,
  TOOLS,
  USAGE_SERIES,
} from '@/data/mock';
import { cx, formatRelative, rgba } from '@/lib/utils';
import { GlassCard, SectionLabel } from '@/components/Primitives';

export function IntelligenceDashboard() {
  const { setView, openConversation, mode, settings } = useApp();
  const active = MODE_BY_ID[mode];

  const totals = [
    { label: 'Sessions', value: '1,284', delta: '+18%', icon: Gauge },
    { label: 'Tokens processed', value: '48.2M', delta: '+7.4%', icon: Boxes },
    { label: 'Knowledge items', value: '240,148', delta: '+2.1k', icon: Library },
    { label: 'Connected tools', value: `${TOOLS.filter((t) => t.connected).length}/7`, delta: 'stable', icon: Plug },
  ];

  return (
    <div className="relative min-h-0 flex-1 overflow-y-auto px-5 py-6 lg:px-10">
      <div className="mx-auto w-full max-w-[1280px] space-y-8">
        {/* ── Summary tiles ─────────────────────────────────────── */}
        <section>
          <SectionLabel
            trailing={
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                Rolling 7 days
              </span>
            }
          >
            Intelligence overview
          </SectionLabel>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {totals.map((t, i) => (
              <motion.div
                key={t.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
              >
                <GlassCard interactive aura={active.aura} className="p-5">
                  <div className="flex items-start justify-between">
                    <t.icon className="h-3.5 w-3.5 text-platinum-dim" />
                    <span
                      className="flex items-center gap-1 font-mono text-3xs uppercase tracking-widest2"
                      style={{ color: rgba('216 195 154', 0.9) }}
                    >
                      <ArrowUpRight className="h-3 w-3" />
                      {t.delta}
                    </span>
                  </div>
                  <div className="mt-5 text-[2rem] font-extralight leading-none tracking-tight text-platinum tabular-nums">
                    {t.value}
                  </div>
                  <div className="mt-2.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                    {t.label}
                  </div>
                </GlassCard>
              </motion.div>
            ))}
          </div>
        </section>

        {/* ── Usage chart + activity ───────────────────────────── */}
        <section className="grid gap-4 xl:grid-cols-[1.55fr_1fr]">
          <GlassCard layer="raised" className="p-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <SectionLabel>Throughput</SectionLabel>
                <div className="mt-4 flex items-baseline gap-3">
                  <span className="text-[2.4rem] font-extralight leading-none tracking-tight text-platinum tabular-nums">
                    1,199
                  </span>
                  <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                    requests this week
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-5">
                <Legend colour={active.aura} label="Requests" />
                <Legend colour="216 195 154" label="Tool calls" />
              </div>
            </div>

            <UsageChart aura={active.aura} className="mt-8" />
          </GlassCard>

          <GlassCard layer="raised" className="p-6">
            <SectionLabel trailing={<span className="font-mono text-3xs text-platinum-dim/50">live</span>}>
              Activity
            </SectionLabel>
            <ul className="mt-5 space-y-1">
              {ACTIVITY_FEED.map((a, i) => {
                const aMode = MODE_BY_ID[a.mode];
                return (
                  <motion.li
                    key={a.id}
                    initial={{ opacity: 0, x: 14 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.55, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                    className="group relative flex gap-3.5 rounded-lg px-3 py-3 transition-colors duration-400 hover:bg-white/[0.03]"
                  >
                    <span className="relative mt-1.5 flex h-2 w-2 shrink-0 items-center justify-center">
                      <span
                        className="absolute h-2 w-2 rounded-full opacity-30"
                        style={{ background: rgba(aMode.aura, 0.9) }}
                      />
                      <span
                        className="relative h-1 w-1 rounded-full"
                        style={{ background: rgba(aMode.aura, 1) }}
                      />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12.5px] leading-relaxed text-platinum-soft/82">
                        {a.label}
                      </p>
                      <div className="mt-1.5 flex items-center gap-2 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                        <span style={{ color: rgba(aMode.aura, 0.8) }}>{aMode.label}</span>
                        <span className="opacity-40">·</span>
                        <span>{a.at}</span>
                      </div>
                    </div>
                  </motion.li>
                );
              })}
            </ul>
          </GlassCard>
        </section>

        {/* ── Mode distribution + knowledge + tools ────────────── */}
        <section className="grid gap-4 lg:grid-cols-3">
          <GlassCard layer="raised" className="p-6">
            <SectionLabel>Mode distribution</SectionLabel>
            <ModeDistribution className="mt-6" />
          </GlassCard>

          <GlassCard layer="raised" className="p-6">
            <SectionLabel
              trailing={
                <button
                  type="button"
                  onClick={() => setView('knowledge')}
                  className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60 transition-colors hover:text-platinum"
                >
                  Manage
                </button>
              }
            >
              Knowledge sources
            </SectionLabel>
            <ul className="mt-5 space-y-2.5">
              {KNOWLEDGE_SOURCES.slice(0, 4).map((k) => (
                <li key={k.id} className="flex items-center gap-3.5">
                  <span
                    className={cx(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border',
                    )}
                    style={{
                      borderColor:
                        k.status === 'indexing'
                          ? rgba('216 195 154', 0.3)
                          : 'rgba(255,255,255,0.07)',
                      background:
                        k.status === 'indexing'
                          ? rgba('216 195 154', 0.07)
                          : 'rgba(255,255,255,0.02)',
                    }}
                  >
                    <Database
                      className="h-3.5 w-3.5"
                      style={{
                        color:
                          k.status === 'indexing'
                            ? rgba('216 195 154', 0.9)
                            : 'rgba(143,149,163,0.9)',
                      }}
                    />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12.5px] text-platinum-soft/88">
                      {k.name}
                    </div>
                    <div className="mt-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                      {k.items.toLocaleString()} items · {k.updated}
                    </div>
                  </div>
                  <span
                    className="shrink-0 font-mono text-3xs uppercase tracking-widest2"
                    style={{
                      color:
                        k.status === 'synced'
                          ? rgba(active.aura, 0.85)
                          : k.status === 'indexing'
                            ? rgba('216 195 154', 0.9)
                            : 'rgba(143,149,163,0.6)',
                    }}
                  >
                    {k.status}
                  </span>
                </li>
              ))}
            </ul>
          </GlassCard>

          <GlassCard layer="raised" className="p-6">
            <SectionLabel
              trailing={
                <button
                  type="button"
                  onClick={() => setView('memory')}
                  className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60 transition-colors hover:text-platinum"
                >
                  Inspect
                </button>
              }
            >
              Memory
            </SectionLabel>
            <ul className="mt-5 space-y-3.5">
              {MEMORY.slice(0, 3).map((m) => (
                <li key={m.id}>
                  <div className="flex items-start gap-2.5">
                    <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-champagne/70" />
                    <p className="text-[12.5px] leading-relaxed text-platinum-soft/78">
                      {m.statement}
                    </p>
                  </div>
                  <div className="mt-2.5 flex items-center gap-3 pl-[22px]">
                    <div className="h-px flex-1 bg-white/[0.07]">
                      <motion.div
                        className="h-px"
                        initial={{ width: 0 }}
                        animate={{ width: `${m.confidence * 100}%` }}
                        transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
                        style={{
                          background: `linear-gradient(90deg, transparent, ${rgba(
                            active.aura,
                            0.8,
                          )})`,
                        }}
                      />
                    </div>
                    <span className="font-mono text-3xs tabular-nums text-platinum-dim/60">
                      {Math.round(m.confidence * 100)}%
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </GlassCard>
        </section>

        {/* ── Projects + recent threads ─────────────────────────── */}
        <section className="grid gap-4 xl:grid-cols-[1fr_1.35fr]">
          <GlassCard layer="raised" className="p-6">
            <SectionLabel
              trailing={
                <button
                  type="button"
                  onClick={() => setView('projects')}
                  className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60 transition-colors hover:text-platinum"
                >
                  All
                </button>
              }
            >
              Projects
            </SectionLabel>
            <div className="mt-5 space-y-4">
              {PROJECTS.map((p, i) => (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.6, delay: i * 0.07 }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-[13px] text-platinum/88">{p.name}</span>
                    <span
                      className="shrink-0 font-mono text-3xs tabular-nums"
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
                      transition={{ duration: 1.2, delay: 0.2 + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                      style={{
                        background: `linear-gradient(90deg, transparent, ${rgba(p.accent, 0.95)})`,
                      }}
                    />
                  </div>
                </motion.div>
              ))}
            </div>
          </GlassCard>

          <GlassCard layer="raised" className="p-6">
            <SectionLabel
              trailing={
                <span className="flex items-center gap-2 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                  <ShieldCheck className="h-3 w-3 text-champagne/70" />
                  {settings.citations ? 'Cited' : 'Uncited'}
                </span>
              }
            >
              Recent conversations
            </SectionLabel>
            <div className="mt-5 overflow-hidden rounded-xl border border-white/[0.05]">
              {CONVERSATIONS.slice(0, 5).map((c, i) => {
                const cMode = MODE_BY_ID[c.mode];
                return (
                  <motion.button
                    key={c.id}
                    type="button"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: i * 0.06 }}
                    onClick={() => openConversation(c.id)}
                    className={cx(
                      'group flex w-full items-center gap-4 px-4 py-3.5 text-left transition-colors duration-400',
                      'border-b border-white/[0.04] last:border-0 hover:bg-white/[0.03]',
                    )}
                  >
                    <span
                      className="h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: rgba(cMode.aura, 0.85) }}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] text-platinum-soft/88 transition-colors group-hover:text-platinum">
                        {c.title}
                      </span>
                      <span className="mt-1 block font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                        {cMode.label} · {c.messageCount} msgs
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/50">
                      {formatRelative(c.updatedAt)}
                    </span>
                  </motion.button>
                );
              })}
            </div>
          </GlassCard>
        </section>
      </div>
    </div>
  );
}

/* ── Charts ────────────────────────────────────────────────── */

function Legend({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: rgba(colour, 0.95), boxShadow: `0 0 8px ${rgba(colour, 0.7)}` }}
      />
      <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
        {label}
      </span>
    </span>
  );
}

/**
 * Hand-composed SVG line chart. Deliberately restrained: no gridline clutter,
 * one emphasised series, soft area fill, and a hover-free static composition
 * that animates on mount.
 */
function UsageChart({ aura, className }: { aura: string; className?: string }) {
  const W = 720;
  const H = 220;
  const PAD_X = 8;
  const PAD_Y = 24;

  const max = Math.max(...USAGE_SERIES.map((p) => p.value)) * 1.18;
  const stepX = (W - PAD_X * 2) / (USAGE_SERIES.length - 1);
  const scaleY = (v: number) => H - PAD_Y - (v / max) * (H - PAD_Y * 2);

  const points = USAGE_SERIES.map((p, i) => ({ x: PAD_X + i * stepX, y: scaleY(p.value), ...p }));
  const secondary = USAGE_SERIES.map((p, i) => ({
    x: PAD_X + i * stepX,
    y: scaleY(p.secondary),
  }));

  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');
  const area = `${path} L ${W - PAD_X} ${H - PAD_Y} L ${PAD_X} ${H - PAD_Y} Z`;
  const secondaryPath = secondary
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');

  return (
    <div className={className}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Weekly throughput chart">
        <defs>
          <linearGradient id="usage-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={rgba(aura, 0.28)} />
            <stop offset="100%" stopColor={rgba(aura, 0)} />
          </linearGradient>
          <linearGradient id="usage-stroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={rgba(aura, 0.35)} />
            <stop offset="50%" stopColor={rgba(aura, 1)} />
            <stop offset="100%" stopColor={rgba('216 195 154', 0.85)} />
          </linearGradient>
        </defs>

        {/* Baseline only */}
        <line
          x1={PAD_X}
          y1={H - PAD_Y}
          x2={W - PAD_X}
          y2={H - PAD_Y}
          stroke="rgba(255,255,255,0.07)"
          strokeWidth="1"
        />

        <motion.path
          d={area}
          fill="url(#usage-area)"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.4, delay: 0.35 }}
        />

        <motion.path
          d={secondaryPath}
          fill="none"
          stroke={rgba('216 195 154', 0.55)}
          strokeWidth="1"
          strokeDasharray="3 5"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.6, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
        />

        <motion.path
          d={path}
          fill="none"
          stroke="url(#usage-stroke)"
          strokeWidth="1.8"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        />

        {points.map((p, i) => (
          <motion.g
            key={p.label}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.9 + i * 0.08 }}
          >
            <circle cx={p.x} cy={p.y} r="9" fill={rgba(aura, 0.1)} />
            <circle cx={p.x} cy={p.y} r="2.6" fill={rgba(aura, 1)} />
            <circle cx={p.x} cy={p.y} r="5.5" fill="none" stroke={rgba(aura, 0.35)} strokeWidth="1" />
          </motion.g>
        ))}

        {/* Labels sit inside the plot as quiet metadata */}
        {points.map((p, i) => (
          <text
            key={`l-${p.label}`}
            x={p.x}
            y={H - 6}
            textAnchor="middle"
            className="font-mono"
            style={{
              fontSize: 9,
              letterSpacing: '0.18em',
              fill: i === 4 ? rgba(aura, 0.95) : 'rgba(143,149,163,0.6)',
              textTransform: 'uppercase',
            }}
          >
            {p.label}
          </text>
        ))}
      </svg>
    </div>
  );
}

const MODE_WEIGHTS = [
  { id: 'analysis' as const, weight: 0.28 },
  { id: 'coding' as const, weight: 0.24 },
  { id: 'research' as const, weight: 0.18 },
  { id: 'creative' as const, weight: 0.14 },
  { id: 'vision' as const, weight: 0.09 },
  { id: 'voice' as const, weight: 0.07 },
];

function ModeDistribution({ className }: { className?: string }) {
  let cumulative = 0;
  const R = 56;
  const C = 2 * Math.PI * R;
  const circumference = C;

  return (
    <div className={cx('flex items-center gap-7', className)}>
      <div className="relative h-[148px] w-[148px] shrink-0">
        <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90">
          <circle
            cx="80"
            cy="80"
            r={R}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth="8"
          />
          {MODE_WEIGHTS.map((m, i) => {
            const mMode = MODE_BY_ID[m.id];
            const dash = m.weight * circumference;
            const offset = cumulative * circumference;
            cumulative += m.weight;
            return (
              <motion.circle
                key={m.id}
                cx="80"
                cy="80"
                r={R}
                fill="none"
                stroke={rgba(mMode.aura, 0.9)}
                strokeWidth="8"
                strokeLinecap="butt"
                strokeDasharray={`${dash} ${circumference - dash}`}
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset: -offset }}
                transition={{ duration: 1.4, delay: 0.15 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[1.4rem] font-extralight tabular-nums text-platinum">1,199</span>
          <span className="mt-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
            requests
          </span>
        </div>
      </div>

      <ul className="min-w-0 flex-1 space-y-2.5">
        {MODE_WEIGHTS.map((m) => {
          const mMode = MODE_BY_ID[m.id];
          return (
            <li key={m.id} className="flex items-center gap-3">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: rgba(mMode.aura, 0.9) }}
              />
              <span className="flex-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/75">
                {mMode.label}
              </span>
              <span className="font-mono text-3xs tabular-nums text-platinum-soft/80">
                {Math.round(m.weight * 100)}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}