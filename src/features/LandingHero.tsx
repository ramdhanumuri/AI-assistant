import { motion } from 'framer-motion';
import { ArrowRight, AudioLines, Command, Plus } from 'lucide-react';
import { useApp } from '@/state/AppContext';
import { MODE_BY_ID, PROJECTS, CONVERSATIONS } from '@/data/mock';
import { cx, formatRelative, rgba } from '@/lib/utils';
import { AIOrb } from '@/components/AIOrb';
import { Button, GlassCard, SectionLabel, StatusPill } from '@/components/Primitives';
import { ModeShowcase } from '@/components/ModeSelector';
import { ParticleField } from '@/components/AmbientBackground';

export function LandingHero() {
  const { mode, setView, newConversation, openConversation, settings, aiState } = useApp();
  const active = MODE_BY_ID[mode];

  const recent = CONVERSATIONS.slice(0, 3);

  return (
    <div className="relative min-h-0 flex-1 overflow-y-auto">
      {settings.particles && <ParticleField aura={active.aura} count={38} />}

      {/* ── Hero ─────────────────────────────────────────────────── */}
      <section className="relative px-6 pb-20 pt-10 lg:px-16 lg:pt-16">
        <div className="mx-auto w-full max-w-[1240px]">
          <div className="grid items-center gap-14 lg:grid-cols-[1.15fr_0.85fr] lg:gap-10">
            {/* Editorial column */}
            <div className="relative z-10 order-2 lg:order-1">
              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-wrap items-center gap-3"
              >
                <StatusPill
                  label={aiState === 'idle' ? 'Core online' : aiState}
                  aura={active.aura}
                  pulse={aiState !== 'idle'}
                />
                <span className="font-mono text-3xs uppercase tracking-widest3 text-platinum-dim/60">
                  Private · Local-first · Cited
                </span>
              </motion.div>

              <h1 className="mt-8 text-cinematic">
                <motion.span
                  initial={{ opacity: 0, y: 26, filter: 'blur(14px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  transition={{ duration: 1.1, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
                  className="block text-[clamp(2.6rem,7.2vw,5.6rem)] font-extralight gradient-platinum"
                >
                  Your intelligence,
                </motion.span>
                <motion.span
                  initial={{ opacity: 0, y: 26, filter: 'blur(14px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  transition={{ duration: 1.1, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
                  className="block text-[clamp(2.6rem,7.2vw,5.6rem)] font-extralight gradient-gold italic"
                >
                  amplified.
                </motion.span>
              </h1>

              <motion.p
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.9, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="mt-8 max-w-[54ch] text-[15px] font-[350] leading-[1.8] text-platinum-soft/68"
              >
                AURELIS is a private intelligence layer that reads your context, holds
                your preferences, and works across research, engineering, analysis and
                creative direction — quietly, accurately, and entirely on your terms.
              </motion.p>

              {/* Primary actions */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.9, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="mt-11 flex flex-wrap items-center gap-3"
              >
                <Button size="lg" onClick={newConversation} aura={active.aura}>
                  Start conversation
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="lg"
                  variant="secondary"
                  onClick={() => setView('dashboard')}
                >
                  Explore intelligence
                </Button>
                <Button
                  size="lg"
                  variant="ghost"
                  onClick={() => setView('voice')}
                  className="gap-2"
                >
                  <AudioLines className="h-3.5 w-3.5" />
                  Voice
                </Button>
              </motion.div>

              {/* Precision metrics rail */}
              <motion.dl
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 1, delay: 0.7 }}
                className="mt-14 grid max-w-[560px] grid-cols-3 gap-6 border-t border-white/[0.07] pt-7"
              >
                {[
                  { k: 'Context window', v: '2.4M', d: 'tokens' },
                  { k: 'Response latency', v: '180', d: 'ms median' },
                  { k: 'Memory records', v: '1,284', d: 'learned' },
                ].map((m) => (
                  <div key={m.k}>
                    <dt className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/65">
                      {m.k}
                    </dt>
                    <dd className="mt-2.5 flex items-baseline gap-1.5">
                      <span className="text-[1.6rem] font-extralight tracking-tight text-platinum">
                        {m.v}
                      </span>
                      <span className="font-mono text-3xs uppercase tracking-wider text-platinum-dim/55">
                        {m.d}
                      </span>
                    </dd>
                  </div>
                ))}
              </motion.dl>
            </div>

            {/* Core column */}
            <div className="relative order-1 flex items-center justify-center lg:order-2">
              <div className="relative flex h-[380px] w-full items-center justify-center sm:h-[460px] lg:h-[560px]">
                <AIOrb
                  state={aiState}
                  aura={active.aura}
                  size={420}
                  particles={settings.particles}
                />

                {/* Orbiting metadata callouts — dimensional annotation */}
                {ORB_CALLOUTS.map((c, i) => (
                  <motion.div
                    key={c.label}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 1, delay: 1 + i * 0.15 }}
                    className="pointer-events-none absolute hidden xl:block"
                    style={{ left: c.left, top: c.top }}
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className="h-px w-10"
                        style={{
                          background: `linear-gradient(90deg, ${rgba(active.aura, 0.5)}, transparent)`,
                        }}
                      />
                      <div>
                        <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
                          {c.label}
                        </div>
                        <div className="mt-1 font-mono text-[10px] tabular-nums text-platinum/85">
                          {c.value}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Modes ────────────────────────────────────────────────── */}
      <section className="relative px-6 pb-20 lg:px-16">
        <div className="mx-auto w-full max-w-[1240px]">
          <SectionLabel
            trailing={
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
                Seven specialised modes
              </span>
            }
          >
            Intelligence modes
          </SectionLabel>
          <ModeShowcase className="mt-7" />
        </div>
      </section>

      {/* ── Active workstreams + recent ──────────────────────────── */}
      <section className="relative px-6 pb-24 lg:px-16">
        <div className="mx-auto grid w-full max-w-[1240px] gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <SectionLabel>Active workstreams</SectionLabel>
            <div className="mt-5 space-y-3">
              {PROJECTS.slice(0, 3).map((p, i) => (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-60px' }}
                  transition={{ duration: 0.7, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                >
                  <GlassCard interactive aura={p.accent} className="p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-3">
                          <span
                            className="h-1.5 w-1.5 rounded-full"
                            style={{
                              background: rgba(p.accent, 0.95),
                              boxShadow: `0 0 10px ${rgba(p.accent, 0.8)}`,
                            }}
                          />
                          <h3 className="text-[15px] font-light tracking-wide text-platinum">
                            {p.name}
                          </h3>
                        </div>
                        <p className="mt-2.5 max-w-[52ch] text-[12.5px] leading-relaxed text-platinum-soft/62">
                          {p.brief}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
                          {p.threads} threads
                        </div>
                        <div
                          className="mt-1.5 font-mono text-[13px] tabular-nums"
                          style={{ color: rgba(p.accent, 0.95) }}
                        >
                          {Math.round(p.progress * 100)}%
                        </div>
                      </div>
                    </div>
                    {/* Progress as energy line */}
                    <div className="mt-4 h-px w-full bg-white/[0.06]">
                      <motion.div
                        className="h-px"
                        initial={{ width: 0 }}
                        whileInView={{ width: `${p.progress * 100}%` }}
                        viewport={{ once: true }}
                        transition={{ duration: 1.4, delay: 0.2 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                        style={{
                          background: `linear-gradient(90deg, transparent, ${rgba(p.accent, 0.95)})`,
                          boxShadow: `0 0 12px ${rgba(p.accent, 0.6)}`,
                        }}
                      />
                    </div>
                  </GlassCard>
                </motion.div>
              ))}
            </div>
          </div>

          <div>
            <SectionLabel
              trailing={
                <button
                  type="button"
                  onClick={() => setView('conversation')}
                  className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60 transition-colors hover:text-platinum"
                >
                  All
                </button>
              }
            >
              Resume
            </SectionLabel>
            <div className="mt-5 space-y-2">
              {recent.map((c, i) => {
                const cMode = MODE_BY_ID[c.mode];
                return (
                  <motion.button
                    key={c.id}
                    type="button"
                    initial={{ opacity: 0, x: 16 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, margin: '-40px' }}
                    transition={{ duration: 0.65, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                    onClick={() => openConversation(c.id)}
                    className={cx(
                      'group relative block w-full overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.015] p-4 text-left',
                      'transition-all duration-500 ease-cinematic hover:border-white/[0.14] hover:bg-white/[0.04]',
                    )}
                  >
                    <span
                      aria-hidden
                      className="absolute inset-y-3 left-0 w-px transition-all duration-500"
                      style={{ background: rgba(cMode.aura, 0.5) }}
                    />
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-mono text-3xs uppercase tracking-widest2" style={{ color: rgba(cMode.aura, 0.85) }}>
                        {cMode.label}
                      </span>
                      <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/50">
                        {formatRelative(c.updatedAt)}
                      </span>
                    </div>
                    <h4 className="mt-2.5 truncate text-[13.5px] text-platinum/90">
                      {c.title}
                    </h4>
                    <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed text-platinum-soft/58">
                      {c.preview}
                    </p>
                  </motion.button>
                );
              })}
            </div>

            <GlassCard layer="flat" className="mt-4 p-5">
              <div className="flex items-center gap-2.5">
                <Command className="h-3.5 w-3.5 text-champagne/80" />
                <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                  Command center
                </span>
              </div>
              <p className="mt-3 text-[12.5px] leading-relaxed text-platinum-soft/65">
                Reach any conversation, mode, project or tool from a single layer.
              </p>
              <div className="mt-4">
                <Button
                  variant="gold"
                  size="sm"
                  onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
                >
                  <Plus className="h-3 w-3" />
                  Open ⌘K
                </Button>
              </div>
            </GlassCard>
          </div>
        </div>
      </section>
    </div>
  );
}

const ORB_CALLOUTS = [
  { label: 'Attention', value: 'stable', left: '2%', top: '24%' },
  { label: 'Retrieval', value: '4 sources', left: '72%', top: '18%' },
  { label: 'Memory', value: '1,284 records', left: '68%', top: '74%' },
  { label: 'Posture', value: 'private', left: '0%', top: '70%' },
];