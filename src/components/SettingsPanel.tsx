import { AnimatePresence, motion } from 'framer-motion';
import { RotateCcw, ShieldCheck, X } from 'lucide-react';
import { useApp, type Settings } from '@/state/AppContext';
import { AI_MODES } from '@/data/mock';
import { cx, rgba } from '@/lib/utils';
import { Divider, Toggle } from '@/components/Primitives';

const CONTROLS: {
  key: keyof Settings;
  label: string;
  detail: string;
  kind: 'toggle';
  group: string;
}[] = [
  {
    key: 'ambientLight',
    label: 'Ambient light field',
    detail: 'Atmospheric lighting reacts to the active mode.',
    kind: 'toggle',
    group: 'Presence',
  },
  {
    key: 'particles',
    label: 'Depth particles',
    detail: 'Floating motes that give the interface dimensionality.',
    kind: 'toggle',
    group: 'Presence',
  },
  {
    key: 'reduceMotion',
    label: 'Restrained motion',
    detail: 'Reduces continuous animation across the interface.',
    kind: 'toggle',
    group: 'Presence',
  },
  {
    key: 'streaming',
    label: 'Streamed responses',
    detail: 'Render reasoning and content progressively.',
    kind: 'toggle',
    group: 'Intelligence',
  },
  {
    key: 'memory',
    label: 'Persistent memory',
    detail: 'AURELIS retains preferences and project context.',
    kind: 'toggle',
    group: 'Intelligence',
  },
  {
    key: 'citations',
    label: 'Source attribution',
    detail: 'Attach provenance to retrieved claims.',
    kind: 'toggle',
    group: 'Intelligence',
  },
  {
    key: 'soundscape',
    label: 'Ambient soundscape',
    detail: 'Low-level tonal bed during long sessions.',
    kind: 'toggle',
    group: 'Intelligence',
  },
];

const GROUPS = ['Presence', 'Intelligence'];

export function SettingsPanel() {
  const { settingsOpen, setSettingsOpen, settings, updateSettings, mode } = useApp();
  const active = AI_MODES.find((m) => m.id === mode) ?? AI_MODES[0];

  return (
    <AnimatePresence>
      {settingsOpen && (
        <motion.div
          className="fixed inset-0 z-[85] flex justify-end"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <div
            className="absolute inset-0 bg-obsidian-950/72 backdrop-blur-md"
            onClick={() => setSettingsOpen(false)}
            aria-hidden
          />

          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label="Preferences"
            initial={{ x: 420, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 420, opacity: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="glass-deep relative flex h-full w-full max-w-[440px] flex-col shadow-glass-lg"
          >
            <span
              aria-hidden
              className="absolute inset-x-10 top-0 h-px"
              style={{
                background: `linear-gradient(90deg, transparent, ${rgba(
                  active.aura,
                  0.8,
                )}, transparent)`,
              }}
            />

            {/* Header */}
            <div className="flex items-center justify-between px-6 pt-6 pb-5">
              <div>
                <h2 className="text-[1.05rem] font-light tracking-[0.06em] text-platinum">
                  Preferences
                </h2>
                <p className="mt-1.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/65">
                  Applied instantly · this device
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSettingsOpen(false)}
                aria-label="Close preferences"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.025] text-platinum-dim transition-colors hover:border-white/[0.15] hover:text-platinum"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <Divider />

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
              {GROUPS.map((group) => (
                <section key={group} className="mb-8 last:mb-0">
                  <div className="eyebrow mb-4 flex items-center gap-3">
                    <span className="h-px w-5 bg-white/20" />
                    {group}
                  </div>
                  <ul className="space-y-1">
                    {CONTROLS.filter((c) => c.group === group).map((c) => (
                      <li
                        key={c.key}
                        className="flex items-start justify-between gap-5 rounded-xl px-3 py-3 transition-colors duration-400 hover:bg-white/[0.025]"
                      >
                        <div className="min-w-0">
                          <label
                            htmlFor={`setting-${c.key}`}
                            className="block text-[13px] text-platinum-soft/92"
                          >
                            {c.label}
                          </label>
                          <p className="mt-1.5 text-[11.5px] leading-relaxed text-platinum-dim/70">
                            {c.detail}
                          </p>
                        </div>
                        <span id={`setting-${c.key}`}>
                          <Toggle
                            label={c.label}
                            aura={active.aura}
                            checked={Boolean(settings[c.key])}
                            onChange={(v) => updateSettings({ [c.key]: v })}
                          />
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}

              {/* Density */}
              <section className="mb-8">
                <div className="eyebrow mb-4 flex items-center gap-3">
                  <span className="h-px w-5 bg-white/20" />
                  Layout
                </div>
                <div className="flex gap-2">
                  {(['comfortable', 'compact'] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => updateSettings({ density: d })}
                      className={cx(
                        'flex-1 rounded-xl border px-4 py-3 text-left transition-colors duration-400',
                        settings.density === d
                          ? 'text-platinum'
                          : 'border-white/[0.07] text-platinum-dim hover:border-white/[0.14]',
                      )}
                      style={
                        settings.density === d
                          ? {
                              borderColor: rgba(active.aura, 0.3),
                              background: rgba(active.aura, 0.08),
                            }
                          : undefined
                      }
                    >
                      <span className="font-mono text-3xs uppercase tracking-widest2">
                        {d}
                      </span>
                    </button>
                  ))}
                </div>
              </section>

              {/* Privacy posture */}
              <section>
                <div className="eyebrow mb-4 flex items-center gap-3">
                  <span className="h-px w-5 bg-white/20" />
                  Privacy
                </div>
                <div
                  className="rounded-xl border p-4"
                  style={{
                    borderColor: rgba('216 195 154', 0.2),
                    background: rgba('216 195 154', 0.045),
                  }}
                >
                  <div className="flex items-center gap-2.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-champagne" />
                    <span className="font-mono text-3xs uppercase tracking-widest2 text-champagne-bright">
                      Private by default
                    </span>
                  </div>
                  <p className="mt-3 text-[12px] leading-relaxed text-platinum-soft/72">
                    Conversations, memory records and indexed knowledge stay within
                    your boundary. Tool calls are logged locally with full provenance
                    and can be revoked at any time.
                  </p>
                </div>
              </section>
            </div>

            <Divider />

            <div className="flex items-center justify-between px-6 py-4">
              <button
                type="button"
                onClick={() =>
                  updateSettings({
                    ambientLight: true,
                    particles: true,
                    reduceMotion: false,
                    streaming: true,
                    memory: true,
                    citations: true,
                    soundscape: false,
                    density: 'comfortable',
                  })
                }
                className="flex items-center gap-2 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors hover:text-platinum"
              >
                <RotateCcw className="h-3 w-3" />
                Reset to defaults
              </button>
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/45">
                AURELIS OS 4.2
              </span>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}