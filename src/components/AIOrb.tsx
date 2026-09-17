import { motion, useReducedMotion } from 'framer-motion';
import { useMemo } from 'react';
import type { AIState } from '@/types';
import { cx, rgba, seeded } from '@/lib/utils';

interface AIOrbProps {
  state: AIState;
  aura: string; // "r g b"
  /** Visual diameter in px at the md breakpoint. Scales down responsively. */
  size?: number;
  /** 0–1 live intensity, e.g. audio amplitude or token throughput. */
  intensity?: number;
  particles?: boolean;
  label?: string;
  className?: string;
}

const STATE_COPY: Record<AIState, string> = {
  idle: 'Standing by',
  listening: 'Listening',
  thinking: 'Reasoning',
  responding: 'Composing',
};

/**
 * The AI Core. Layered concentric geometry over a glass nucleus:
 * energy rings, rotating micro-elements, light diffusion and a
 * breathing nucleus whose cadence changes with the assistant state.
 */
export function AIOrb({
  state,
  aura,
  size = 320,
  intensity = 0.4,
  particles = true,
  label,
  className,
}: AIOrbProps) {
  const reduced = useReducedMotion();

  const orbits = useMemo(
    () =>
      [
        { r: 0.5, dur: 34, dash: '1 5', tilt: -18, opacity: 0.5 },
        { r: 0.5, dur: 52, dash: '2 11', tilt: 22, opacity: 0.34 },
        { r: 0.5, dur: 74, dash: '0.5 9', tilt: -64, opacity: 0.24 },
        { r: 0.5, dur: 96, dash: '1 14', tilt: 78, opacity: 0.18 },
      ].map((o, i) => ({ ...o, id: i, offset: seeded(i + 3) * 40 - 20 })),
    [],
  );

  const motes = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        id: i,
        angle: seeded(i * 2.3) * 360,
        radius: 0.36 + seeded(i * 5.1) * 0.28,
        size: 1 + seeded(i * 7.7) * 2.1,
        dur: 12 + seeded(i * 11.2) * 16,
        delay: seeded(i * 3.9) * 6,
      })),
    [],
  );

  const breathing = state === 'idle' || state === 'listening';
  const nucleusScale = state === 'thinking' ? 0.94 : state === 'responding' ? 1.02 : 1;
  const glowOpacity = state === 'idle' ? 0.32 : 0.62;

  return (
    <div
      className={cx('relative select-none', className)}
      style={{
        width: `min(${size}px, 68vw)`,
        height: `min(${size}px, 68vw)`,
      }}
      role="img"
      aria-label={`AI Core — ${STATE_COPY[state]}${label ? ` · ${label}` : ''}`}
    >
      {/* ── Atmospheric diffusion ───────────────────────────────── */}
      <motion.div
        aria-hidden
        className="absolute inset-[-38%] rounded-full blur-[64px]"
        style={{
          background: `radial-gradient(circle at 50% 50%, ${rgba(aura, 0.3)} 0%, ${rgba(
            aura,
            0.1,
          )} 34%, transparent 68%)`,
        }}
        animate={{
          opacity: reduced ? glowOpacity * 0.7 : [glowOpacity * 0.75, glowOpacity, glowOpacity * 0.75],
          scale: reduced ? 1 : [1, 1.06, 1],
        }}
        transition={{ duration: state === 'thinking' ? 2.4 : 7.5, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* ── Champagne contoured rim light ───────────────────────── */}
      <div
        aria-hidden
        className="absolute inset-[6%] rounded-full"
        style={{
          background:
            'conic-gradient(from 210deg, rgba(216,195,154,0.34), transparent 28%, transparent 62%, rgba(110,168,255,0.34) 88%, transparent)',
          maskImage: 'radial-gradient(circle, transparent 63%, #000 66%, #000 71%, transparent 74%)',
          WebkitMaskImage:
            'radial-gradient(circle, transparent 63%, #000 66%, #000 71%, transparent 74%)',
          opacity: 0.85,
        }}
      />

      {/* ── Rotating orbital rings ──────────────────────────────── */}
      {orbits.map((o) => (
        <motion.div
          key={o.id}
          aria-hidden
          className="absolute inset-[3%] rounded-full"
          style={{
            border: `1px dashed ${rgba(aura, o.opacity * 0.9)}`,
            borderTopColor: 'transparent',
            borderLeftColor: 'transparent',
            rotateX: o.tilt,
            transformStyle: 'preserve-3d',
            scaleX: 1,
            scaleY: 0.42,
          }}
          animate={
            reduced
              ? undefined
              : { rotate: [o.offset, o.offset + 360] }
          }
          transition={{ duration: o.dur, repeat: Infinity, ease: 'linear' }}
        />
      ))}

      {/* ── Precision tick ring ─────────────────────────────────── */}
      <div
        aria-hidden
        className="absolute inset-[14%] rounded-full"
        style={{
          background: `repeating-conic-gradient(from 0deg, ${rgba(
            aura,
            0.5,
          )} 0deg 0.7deg, transparent 0.7deg 9deg)`,
          maskImage: 'radial-gradient(circle, transparent 88%, #000 89%, #000 100%)',
          WebkitMaskImage: 'radial-gradient(circle, transparent 88%, #000 89%, #000 100%)',
          opacity: 0.4,
        }}
      />

      {/* ── Glass shell ─────────────────────────────────────────── */}
      <div
        aria-hidden
        className="absolute inset-[21%] rounded-full border border-white/[0.09]"
        style={{
          background:
            'radial-gradient(circle at 34% 26%, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.03) 30%, rgba(6,7,13,0.72) 72%)',
          backdropFilter: 'blur(14px)',
          boxShadow: `inset 0 1px 1px rgba(255,255,255,0.16), inset 0 -28px 48px -22px ${rgba(
            aura,
            0.5,
          )}, 0 34px 90px -34px ${rgba(aura, 0.55)}`,
        }}
      />

      {/* ── Nucleus ───────────────────────────────────────────── ── */}
      <motion.div
        aria-hidden
        className="absolute left-1/2 top-1/2 rounded-full"
        style={{
          width: '26%',
          height: '26%',
          x: '-50%',
          y: '-50%',
          background: `radial-gradient(circle at 40% 34%, rgba(255,255,255,0.96) 0%, ${rgba(
            aura,
            0.95,
          )} 26%, ${rgba(aura, 0.42)} 58%, transparent 78%)`,
          filter: 'blur(1px)',
        }}
        animate={
          reduced
            ? { opacity: 0.9 }
            : breathing
              ? { scale: [1, 1.09, 1], opacity: [0.86, 1, 0.86] }
              : {
                  scale: [nucleusScale, nucleusScale * 1.13, nucleusScale],
                  opacity: [0.92, 1, 0.92],
                }
        }
        transition={{
          duration: state === 'thinking' ? 1.5 : state === 'listening' ? 2 : 5.6,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* ── State-reactive inner sweep ──────────────────────────── */}
      {(state === 'listening' || state === 'responding' || state === 'thinking') && (
        <motion.div
          aria-hidden
          className="absolute inset-[21%] rounded-full overflow-hidden"
          style={{
            background: `conic-gradient(from 0deg, transparent 0%, ${rgba(
              aura,
              state === 'thinking' ? 0.5 : 0.34,
            )} 22%, transparent 48%)`,
          }}
          animate={reduced ? undefined : { rotate: 360 }}
          transition={{
            duration: state === 'thinking' ? 3.4 : 6.2,
            repeat: Infinity,
            ease: 'linear',
          }}
        />
      )}

      {/* ── Audio-reactive bars ─────────────────────────────────── */}
      {state === 'listening' && <ReactiveBars aura={aura} intensity={intensity} />}

      {/* ── Orbiting motes ──────────────────────────────────────── */}
      {particles && !reduced && (
        <div aria-hidden className="absolute inset-0">
          {motes.map((m) => (
            <motion.span
              key={m.id}
              className="absolute left-1/2 top-1/2 rounded-full"
              style={{
                width: m.size,
                height: m.size,
                background:
                  m.id % 3 === 0 ? rgba('216 195 154', 0.85) : rgba(aura, 0.8),
                boxShadow: `0 0 ${m.size * 4}px ${rgba(
                  m.id % 3 === 0 ? '216 195 154' : aura,
                  0.7,
                )}`,
                marginLeft: -m.size / 2,
                marginTop: -m.size / 2,
              }}
              animate={{
                x: [
                  Math.cos((m.angle * Math.PI) / 180) * (size * m.radius - size * 0.5),
                  Math.cos(((m.angle + 360) * Math.PI) / 180) * (size * m.radius - size * 0.5),
                ],
                y: [
                  Math.sin((m.angle * Math.PI) / 180) * (size * m.radius * 0.42 - size * 0.5),
                  Math.sin(((m.angle + 360) * Math.PI) / 180) * (size * m.radius * 0.42 - size * 0.5),
                ],
                opacity: [0, 0.9, 0.9, 0],
              }}
              transition={{
                duration: m.dur,
                delay: m.delay,
                repeat: Infinity,
                ease: 'linear',
              }}
            />
          ))}
        </div>
      )}

      {/* ── Outer pulse rings ───────────────────────────────────── */}
      {(state === 'listening' || state === 'responding') && !reduced && (
        <>
          {[0, 1].map((i) => (
            <motion.div
              key={i}
              aria-hidden
              className="absolute inset-[16%] rounded-full border"
              style={{ borderColor: rgba(aura, 0.4) }}
              animate={{ scale: [0.9, 1.45], opacity: [0.5, 0] }}
              transition={{
                duration: 3.4,
                delay: i * 1.7,
                repeat: Infinity,
                ease: 'easeOut',
              }}
            />
          ))}
        </>
      )}
    </div>
  );
}

function ReactiveBars({ aura, intensity }: { aura: string; intensity: number }) {
  const bars = useMemo(
    () => Array.from({ length: 72 }, (_, i) => ({ id: i, base: seeded(i * 1.7) })),
    [],
  );

  return (
    <div aria-hidden className="absolute inset-0">
      {bars.map((b, i) => {
        const angle = (i / bars.length) * 360;
        const height = 10 + b.base * 20 + intensity * 48;
        return (
          <motion.span
            key={b.id}
            className="absolute left-1/2 top-1/2 rounded-full"
            style={{
              width: 1.5,
              marginLeft: -0.75,
              background: `linear-gradient(180deg, ${rgba(aura, 0.85)}, ${rgba(
                aura,
                0.04,
              )})`,
              transformOrigin: '50% 0%',
              transform: `rotate(${angle}deg) translateY(22%)`,
              height,
            }}
            animate={{
              height: [height * 0.4, height, height * 0.48],
              opacity: [0.3, 0.95, 0.35],
            }}
            transition={{
              duration: 0.85 + b.base * 0.9,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: b.base * 0.4,
            }}
          />
        );
      })}
    </div>
  );
}