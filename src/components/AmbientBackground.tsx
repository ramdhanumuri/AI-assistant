import { motion, useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';
import { cx, rgba, seeded } from '@/lib/utils';

interface AmbientBackgroundProps {
  aura: string;
  /** Shifts the light field per view so each surface feels distinct. */
  variant?: 'home' | 'conversation' | 'voice' | 'dashboard' | 'system';
  intense?: boolean;
  className?: string;
}

const VARIANT_LIGHT: Record<
  NonNullable<AmbientBackgroundProps['variant']>,
  { x: number; y: number; scale: number; goldX: number; goldY: number }
> = {
  home: { x: 50, y: 42, scale: 1, goldX: 78, goldY: 82 },
  conversation: { x: 22, y: 18, scale: 0.82, goldX: 88, goldY: 74 },
  voice: { x: 50, y: 50, scale: 1.25, goldX: 50, goldY: 96 },
  dashboard: { x: 82, y: 14, scale: 0.9, goldX: 12, goldY: 88 },
  system: { x: 50, y: 8, scale: 0.7, goldX: 20, goldY: 92 },
};

/**
 * The atmospheric substrate of the product: obsidian base, layered radial
 * lighting, an almost-invisible engineering grid, and film grain.
 */
export function AmbientBackground({
  aura,
  variant = 'home',
  intense = false,
  className,
}: AmbientBackgroundProps) {
  const reduced = useReducedMotion();
  const light = VARIANT_LIGHT[variant];

  return (
    <div
      aria-hidden
      className={cx(
        'pointer-events-none absolute inset-0 overflow-hidden',
        className,
      )}
    >
      {/* Base obsidian gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(120%_90%_at_50%_-10%,#0b0d17_0%,#06070d_46%,#030408_100%)]" />

      {/* Primary diffuse light — follows the aura colour */}
      <motion.div
        className="absolute rounded-full blur-[140px]"
        style={{
          left: `${light.x}%`,
          top: `${light.y}%`,
          width: '62vw',
          height: '62vw',
          translateX: '-50%',
          translateY: '-50%',
          background: `radial-gradient(circle, ${rgba(
            aura,
            intense ? 0.3 : 0.19,
          )} 0%, ${rgba(aura, 0.06)} 42%, transparent 72%)`,
        }}
        animate={
          reduced
            ? undefined
            : {
                scale: [light.scale, light.scale * 1.1, light.scale],
                opacity: [0.82, 1, 0.82],
              }
        }
        transition={{ duration: 14, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Champagne counter-light — the restraint that reads as expensive */}
      <motion.div
        className="absolute rounded-full blur-[120px]"
        style={{
          left: `${light.goldX}%`,
          top: `${light.goldY}%`,
          width: '42vw',
          height: '42vw',
          translateX: '-50%',
          translateY: '-50%',
          background: `radial-gradient(circle, rgba(216,195,154,${
            intense ? 0.16 : 0.1
          }) 0%, rgba(216,195,154,0.03) 46%, transparent 74%)`,
        }}
        animate={reduced ? undefined : { scale: [1, 1.14, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 19, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Deep floor shadow — grounds the floating architecture */}
      <div className="absolute inset-x-0 bottom-0 h-[38vh] bg-gradient-to-t from-obsidian-950 via-obsidian-950/70 to-transparent" />

      {/* Engineering grid — barely perceptible */}
      <div
        className="absolute inset-0 opacity-[0.14]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)',
          backgroundSize: '84px 84px',
          maskImage:
            'radial-gradient(120% 80% at 50% 40%, #000 8%, transparent 72%)',
          WebkitMaskImage:
            'radial-gradient(120% 80% at 50% 40%, #000 8%, transparent 72%)',
        }}
      />

      {/* Fine horizontal scan — subtle sense of a live system */}
      {!reduced && (
        <motion.div
          className="absolute inset-x-0 h-[42vh] opacity-[0.05]"
          style={{
            background:
              'linear-gradient(180deg, transparent, rgba(255,255,255,0.5), transparent)',
          }}
          animate={{ top: ['-45vh', '105vh'] }}
          transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}
        />
      )}

      {/* Corner tonal anchors */}
      <div className="absolute -left-24 top-1/3 h-[36vh] w-[36vh] rounded-full bg-[radial-gradient(circle,rgba(110,168,255,0.07),transparent_70%)] blur-[60px]" />
      <div className="absolute -right-16 bottom-1/4 h-[30vh] w-[30vh] rounded-full bg-[radial-gradient(circle,rgba(216,195,154,0.06),transparent_70%)] blur-[60px]" />

      {/* Film grain */}
      <div className="noise-layer absolute inset-0 opacity-[0.045] mix-blend-overlay" />

      {/* Vignette */}
      <div className="absolute inset-0 bg-[radial-gradient(100%_100%_at_50%_50%,transparent_52%,rgba(0,0,0,0.62)_100%)]" />
    </div>
  );
}

interface ParticleFieldProps {
  aura: string;
  count?: number;
  enabled?: boolean;
}

/**
 * Depth particles drifting through the interface. Deterministic layout keeps
 * the composition stable across renders and avoids hydration jitter.
 */
export function ParticleField({ aura, count = 42, enabled = true }: ParticleFieldProps) {
  const reduced = useReducedMotion();
  const particles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        x: seeded(i * 2.1) * 100,
        y: seeded(i * 4.7) * 100,
        depth: 0.25 + seeded(i * 6.3) * 0.75,
        size: 0.8 + seeded(i * 8.9) * 2,
        dur: 20 + seeded(i * 3.3) * 34,
        delay: seeded(i * 5.5) * 14,
        gold: seeded(i * 9.1) > 0.82,
      })),
    [count],
  );

  if (!enabled || reduced) return null;

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {particles.map((p) => (
        <motion.span
          key={p.id}
          className="absolute rounded-full"
          style={{
            left: `${p.x}%`,
            top: `${p.y}%`,
            width: p.size * (0.7 + p.depth),
            height: p.size * (0.7 + p.depth),
            background: p.gold ? rgba('216 195 154', 0.75) : rgba(aura, 0.6),
            boxShadow: `0 0 ${p.size * 5}px ${
              p.gold ? rgba('216 195 154', 0.5) : rgba(aura, 0.45)
            }`,
            filter: `blur(${(1 - p.depth) * 0.9}px)`,
          }}
          animate={{
            y: [0, -28 * p.depth, 0],
            x: [0, 14 * (p.depth - 0.5), 0],
            opacity: [0, 0.55 * p.depth + 0.15, 0],
          }}
          transition={{
            duration: p.dur,
            delay: p.delay,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
}