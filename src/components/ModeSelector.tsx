import { motion } from 'framer-motion';
import { AI_MODES } from '@/data/mock';
import { useApp } from '@/state/AppContext';
import { cx, rgba } from '@/lib/utils';
import type { AIModeId } from '@/types';

interface ModeSelectorProps {
  variant?: 'rail' | 'inline';
  className?: string;
}

/**
 * Mode selector. Each mode owns an aura colour that propagates through the
 * whole interface; the active indicator slides with a shared layout animation.
 */
export function ModeSelector({ variant = 'rail', className }: ModeSelectorProps) {
  const { mode, setMode } = useApp();

  if (variant === 'inline') {
    return (
      <div className={cx('flex flex-wrap items-center gap-2', className)} role="radiogroup" aria-label="AI mode">
        {AI_MODES.map((m) => {
          const isActive = m.id === mode;
          return (
            <button
              key={m.id}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => setMode(m.id)}
              className={cx(
                'relative overflow-hidden rounded-full border px-4 py-2 transition-colors duration-400',
                isActive ? 'text-platinum' : 'text-platinum-dim hover:text-platinum',
              )}
              style={{
                borderColor: isActive ? rgba(m.aura, 0.4) : 'rgba(255,255,255,0.07)',
                background: isActive ? rgba(m.aura, 0.11) : 'rgba(255,255,255,0.02)',
              }}
            >
              <span className="relative z-10 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest2">
                <span style={{ color: rgba(m.aura, 0.9) }}>{m.glyph}</span>
                {m.label}
              </span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={cx('flex items-center gap-1 overflow-x-auto', className)}
      role="radiogroup"
      aria-label="AI mode"
    >
      {AI_MODES.map((m) => {
        const isActive = m.id === mode;
        return (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => setMode(m.id)}
            className={cx(
              'group relative shrink-0 rounded-full px-3.5 py-2 transition-colors duration-400',
              isActive ? 'text-platinum' : 'text-platinum-dim hover:text-platinum',
            )}
          >
            {isActive && (
              <motion.span
                layoutId="mode-rail-active"
                transition={{ type: 'spring', stiffness: 420, damping: 36 }}
                className="absolute inset-0 rounded-full border"
                style={{
                  borderColor: rgba(m.aura, 0.32),
                  background: `linear-gradient(180deg, ${rgba(m.aura, 0.16)}, ${rgba(
                    m.aura,
                    0.05,
                  )})`,
                  boxShadow: `0 0 28px -8px ${rgba(m.aura, 0.7)}`,
                }}
              />
            )}
            <span className="relative z-10 flex items-center gap-2 whitespace-nowrap font-mono text-[10px] uppercase tracking-widest2">
              <span
                className="transition-colors"
                style={{ color: isActive ? rgba(m.aura, 1) : rgba(m.aura, 0.45) }}
              >
                {m.glyph}
              </span>
              {m.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Full mode cards used on the landing experience. */
export function ModeShowcase({ className }: { className?: string }) {
  const { setMode, setView } = useApp();

  return (
    <div className={cx('grid gap-3 sm:grid-cols-2 lg:grid-cols-3', className)}>
      {AI_MODES.filter((m) => m.id !== 'voice').map((m, i) => (
        <motion.button
          key={m.id}
          type="button"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 + i * 0.06, ease: [0.16, 1, 0.3, 1] }}
          onClick={() => {
            setMode(m.id as AIModeId);
            setView('conversation');
          }}
          className="group relative overflow-hidden rounded-2xl border border-white/[0.06] bg-white/[0.018] p-5 text-left transition-all duration-500 ease-cinematic hover:border-white/[0.14] hover:bg-white/[0.04]"
        >
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
            style={{
              background: `radial-gradient(320px circle at 20% 0%, ${rgba(m.aura, 0.14)}, transparent 68%)`,
            }}
          />
          <div className="relative flex items-start justify-between gap-3">
            <span
              className="text-[1.4rem] leading-none"
              style={{ color: rgba(m.aura, 0.92) }}
            >
              {m.glyph}
            </span>
            <span
              className="font-mono text-3xs uppercase tracking-widest2 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
              style={{ color: rgba(m.aura, 0.85) }}
            >
              Engage →
            </span>
          </div>
          <h3 className="relative mt-4 text-[15px] font-light tracking-wide text-platinum">
            {m.label}
          </h3>
          <p className="relative mt-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
            {m.caption}
          </p>
          <p className="relative mt-3 text-[12.5px] leading-relaxed text-platinum-soft/70">
            {m.description}
          </p>
        </motion.button>
      ))}
    </div>
  );
}