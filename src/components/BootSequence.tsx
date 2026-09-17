import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useMemo, useState } from 'react';

interface BootSequenceProps {
  onComplete: () => void;
}

const PHASES = [
  { id: 'dark', duration: 420 },
  { id: 'light', duration: 520 },
  { id: 'orb', duration: 760 },
  { id: 'ring', duration: 620 },
  { id: 'identity', duration: 780 },
] as const;

const RING_R = 132;

/**
 * The cinematic cold start. Black → ambient light → core → orbital ring →
 * identity → interface reveal. Runs once, ends fast, and is skippable on any
 * key or pointer input so it never becomes a wait.
 */
export function BootSequence({ onComplete }: BootSequenceProps) {
  const [phase, setPhase] = useState(0);
  const [exiting, setExiting] = useState(false);

  const total = useMemo(() => PHASES.reduce((a, p) => a + p.duration, 0), []);

  useEffect(() => {
    if (exiting) return;
    const timers: number[] = [];
    let acc = 0;
    PHASES.forEach((p, i) => {
      acc += p.duration;
      timers.push(
        window.setTimeout(() => setPhase(i + 1), acc),
      );
    });
    return () => timers.forEach(window.clearTimeout);
  }, [exiting]);

  useEffect(() => {
    const skip = () => {
      setExiting(true);
      window.setTimeout(onComplete, 620);
    };
    const failSafe = window.setTimeout(skip, total + 500);
    window.addEventListener('keydown', skip);
    window.addEventListener('pointerdown', skip);
    return () => {
      window.clearTimeout(failSafe);
      window.removeEventListener('keydown', skip);
      window.removeEventListener('pointerdown', skip);
    };
  }, [onComplete, total]);

  useEffect(() => {
    if (phase < PHASES.length || exiting) return;
    const t = window.setTimeout(() => {
      setExiting(true);
      window.setTimeout(onComplete, 620);
    }, 260);
    return () => window.clearTimeout(t);
  }, [phase, exiting, onComplete, PHASES.length]);

  return (
    <AnimatePresence>
      {!exiting && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-obsidian-950"
          exit={{ opacity: 0, filter: 'blur(16px)', scale: 1.02 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Ambient light bloom */}
          <motion.div
            aria-hidden
            className="absolute h-[70vmin] w-[70vmin] rounded-full blur-[110px]"
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{
              opacity: phase >= 1 ? 1 : 0,
              scale: phase >= 2 ? 1 : 0.6,
            }}
            transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
            style={{
              background:
                'radial-gradient(circle, rgba(110,168,255,0.22) 0%, rgba(216,195,154,0.06) 40%, transparent 70%)',
            }}
          />

          <div className="relative flex flex-col items-center">
            {/* Core */}
            <motion.div
              className="relative"
              initial={{ opacity: 0, scale: 0.72 }}
              animate={{
                opacity: phase >= 2 ? 1 : 0,
                scale: phase >= 2 ? 1 : 0.72,
              }}
              transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
            >
              <div
                className="h-[124px] w-[124px] rounded-full border border-white/[0.08]"
                style={{
                  background:
                    'radial-gradient(circle at 36% 28%, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.03) 32%, rgba(5,6,10,0.9) 74%)',
                  boxShadow:
                    'inset 0 1px 1px rgba(255,255,255,0.2), 0 0 90px -14px rgba(110,168,255,0.7)',
                }}
              />
              <motion.div
                aria-hidden
                className="absolute left-1/2 top-1/2 h-[34px] w-[34px] -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{
                  background:
                    'radial-gradient(circle at 40% 34%, #fff 0%, rgba(156,198,255,0.95) 30%, rgba(110,168,255,0.35) 62%, transparent 80%)',
                }}
                animate={{ opacity: [0.75, 1, 0.75], scale: [1, 1.12, 1] }}
                transition={{ duration: 3.4, repeat: Infinity, ease: 'easeInOut' }}
              />
            </motion.div>

            {/* Orbital ring forming */}
            {phase >= 3 && (
              <svg
                className="pointer-events-none absolute left-1/2 top-[62px] -translate-x-1/2 -translate-y-1/2"
                width={RING_R * 2 + 40}
                height={RING_R * 2 + 40}
                viewBox={`0 0 ${RING_R * 2 + 40} ${RING_R * 2 + 40}`}
                aria-hidden
              >
                <motion.circle
                  cx={RING_R + 20}
                  cy={RING_R + 20}
                  r={RING_R}
                  fill="none"
                  stroke="rgba(216,195,154,0.5)"
                  strokeWidth="1"
                  strokeDasharray="0 900"
                  initial={{ strokeDasharray: '0 900' }}
                  animate={{ strokeDasharray: '900 0' }}
                  transition={{ duration: 1.5, ease: [0.22, 0.61, 0.36, 1] }}
                />
                <motion.circle
                  cx={RING_R + 20}
                  cy={RING_R + 20}
                  r={RING_R - 16}
                  fill="none"
                  stroke="rgba(110,168,255,0.35)"
                  strokeWidth="1"
                  initial={{ strokeDasharray: '0 900', rotate: 0 }}
                  animate={{ strokeDasharray: '620 0' }}
                  transition={{ duration: 1.7, delay: 0.12, ease: [0.22, 0.61, 0.36, 1] }}
                />
              </svg>
            )}

            {/* Identity */}
            <motion.div
              className="relative mt-24 flex flex-col items-center"
              initial={{ opacity: 0, y: 12, filter: 'blur(8px)' }}
              animate={
                phase >= 4
                  ? { opacity: 1, y: 0, filter: 'blur(0px)' }
                  : { opacity: 0, y: 12, filter: 'blur(8px)' }
              }
              transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="text-[2.6rem] font-extralight leading-none tracking-[0.44em] text-platinum">
                AURELIS
              </div>
              <div className="mt-5 font-mono text-3xs uppercase tracking-widest3 text-platinum-dim">
                Private Intelligence Layer
              </div>
            </motion.div>

            {/* Progress hairline */}
            <motion.div
              className="mt-14 h-px bg-white/15"
              initial={{ width: 0 }}
              animate={{ width: phase >= 4 ? 220 : 60 }}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
            >
              <motion.div
                className="h-px"
                style={{
                  background:
                    'linear-gradient(90deg, rgba(216,195,154,0.9), rgba(110,168,255,0.9))',
                }}
                initial={{ width: '0%' }}
                animate={{ width: `${(phase / PHASES.length) * 100}%` }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              />
            </motion.div>
          </div>

          <motion.button
            type="button"
            onClick={() => {
              setExiting(true);
              window.setTimeout(onComplete, 620);
            }}
            className="absolute bottom-10 font-mono text-3xs uppercase tracking-widest3 text-platinum-dim/60 transition-colors hover:text-platinum"
            initial={{ opacity: 0 }}
            animate={{ opacity: phase >= 2 ? 1 : 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            Skip intro
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}