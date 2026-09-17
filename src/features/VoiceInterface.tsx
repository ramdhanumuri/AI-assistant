import { AnimatePresence, motion } from 'framer-motion';
import { Mic, MicOff, Radio, Square } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '@/state/AppContext';
import { MODE_BY_ID } from '@/data/mock';
import { VOICE_RESPONSES } from '@/lib/engine';
import { cx, rgba, seeded } from '@/lib/utils';
import { AIOrb } from '@/components/AIOrb';
import { ParticleField } from '@/components/AmbientBackground';
import { Button, GlassCard } from '@/components/Primitives';

type VoicePhase = 'idle' | 'listening' | 'thinking' | 'responding';

const PHASE_COPY: Record<VoicePhase, { title: string; sub: string }> = {
  idle: { title: 'Tap to speak', sub: 'The core is standing by' },
  listening: { title: 'Listening…', sub: 'Speak naturally — you can interrupt at any time' },
  thinking: { title: 'Thinking…', sub: 'Composing a considered response' },
  responding: { title: 'Responding…', sub: 'Reply in progress' },
};

const DEMO_UTTERANCES = [
  'What is the binding constraint in the Helios cadence model, and how confident are you in it?',
  'Summarise the three decisions from the board pre-read and flag which one is reversible.',
  'Review the Atlas migration plan and tell me where it breaks first.',
  'Draft the opening paragraph of the investor narrative in a restrained voice.',
];

export function VoiceInterface() {
  const { mode, setView, settings, aiState } = useApp();
  const active = MODE_BY_ID[mode];

  const [phase, setPhase] = useState<VoicePhase>('idle');
  const [amplitude, setAmplitude] = useState(0.18);
  const [spoken, setSpoken] = useState('');
  const [reply, setReply] = useState('');
  const [history, setHistory] = useState<{ id: string; role: 'you' | 'aurelis'; text: string }[]>(
    [],
  );

  const timers = useRef<number[]>([]);
  const rafRef = useRef<number>(0);

  /* Mirrors `phase` so runSession can guard re-entry without being recreated. */
  const phaseRef = useRef<VoicePhase>('idle');
  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }, []);

  /* Simulated audio-reactive amplitude */
  useEffect(() => {
    if (!(phase === 'listening' || phase === 'responding')) return;
    let frame = 0;
    const tick = () => {
      frame += 1;
      const wave =
        Math.sin(frame / 11) * 0.3 + Math.sin(frame / 4.3) * 0.18 + Math.sin(frame / 27) * 0.22;
      setAmplitude(0.35 + Math.abs(wave) * 0.6);
      rafRef.current = window.requestAnimationFrame(tick);
    };
    rafRef.current = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(rafRef.current);
  }, [phase]);

  useEffect(() => clearTimers, [clearTimers]);

  const runSession = useCallback(
    (utterance: string) => {
      /* A session already in flight owns the timers; starting another would
         interleave two transcripts and desync the phase. */
      if (phaseRef.current !== 'idle') return;
      clearTimers();
      setSpoken('');
      setReply('');
      setPhase('listening');
      setAmplitude(0.4);

      /* Live transcription, word by word */
      const words = utterance.split(' ');
      words.forEach((_, i) => {
        timers.current.push(
          window.setTimeout(
            () => setSpoken(words.slice(0, i + 1).join(' ')),
            520 + i * 92,
          ),
        );
      });

      const listeningDone = 520 + words.length * 92 + 420;

      timers.current.push(
        window.setTimeout(() => {
          setPhase('thinking');
          setHistory((h) => [...h, { id: `${Date.now()}-you`, role: 'you', text: utterance }]);
        }, listeningDone),
      );

      const answer = VOICE_RESPONSES[Math.floor(Math.random() * VOICE_RESPONSES.length)];
      const answerWords = answer.split(' ');

      timers.current.push(
        window.setTimeout(() => {
          setPhase('responding');
          answerWords.forEach((_, i) => {
            timers.current.push(
              window.setTimeout(
                () => setReply(answerWords.slice(0, i + 1).join(' ')),
                340 + i * 74,
              ),
            );
          });
          timers.current.push(
            window.setTimeout(
              () => {
                setPhase('idle');
                setHistory((h) => [
                  ...h,
                  { id: `${Date.now()}-a`, role: 'aurelis', text: answer },
                ]);
                setSpoken('');
                setReply('');
              },
              340 + answerWords.length * 74 + 900,
            ),
          );
        }, listeningDone + 1500),
      );
    },
    [clearTimers],
  );

  const stop = () => {
    clearTimers();
    setPhase('idle');
    setAmplitude(0.18);
  };

  const statusLabel = PHASE_COPY[phase];
  const orbState = phase === 'idle' ? 'idle' : phase;

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <ParticleField aura={active.aura} count={40} />

      {/* Cinematic backdrop intensifies with the session */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        animate={{ opacity: phase === 'idle' ? 0.35 : 1 }}
        transition={{ duration: 1.2 }}
        style={{
          background: `radial-gradient(70% 60% at 50% 52%, ${rgba(
            active.aura,
            0.16,
          )}, transparent 70%)`,
        }}
      />

      <div className="relative z-10 flex min-h-0 flex-1 flex-col items-center overflow-y-auto px-6 py-8 lg:px-16">
        {/* Header */}
        <div className="flex w-full max-w-[1080px] items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.025] px-3 py-1.5">
              <Radio className="h-3 w-3 text-champagne/80" />
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                Voice session
              </span>
            </span>
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/55">
              Continuous · interruptible
            </span>
          </div>
          <button
            type="button"
            onClick={() => setView('conversation')}
            className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors hover:text-platinum"
          >
            Exit to text
          </button>
        </div>

        {/* Core + waveform */}
        <div className="relative mt-6 flex w-full flex-1 flex-col items-center justify-center">
          <div className="relative flex items-center justify-center">
            <AIOrb
              state={orbState}
              aura={active.aura}
              size={400}
              intensity={amplitude}
              particles={settings.particles}
            />

            {/* Peripheral waveform — only while audio is flowing */}
            <AnimatePresence>
              {(phase === 'listening' || phase === 'responding') && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.94 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.94 }}
                  transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                  className="pointer-events-none absolute inset-0"
                >
                  <WaveformRing aura={active.aura} amplitude={amplitude} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Phase readout */}
          <div className="mt-10 flex flex-col items-center text-center">
            <AnimatePresence mode="wait">
              <motion.div
                key={phase}
                initial={{ opacity: 0, y: 12, filter: 'blur(8px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -12, filter: 'blur(8px)' }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              >
                <h2
                  className="text-[clamp(1.6rem,4.4vw,2.6rem)] font-extralight uppercase tracking-[0.18em]"
                  style={{
                    color:
                      phase === 'idle'
                        ? 'rgba(230,232,238,0.9)'
                        : rgba(active.aura, 0.98),
                    textShadow:
                      phase === 'idle' ? 'none' : `0 0 42px ${rgba(active.aura, 0.6)}`,
                  }}
                >
                  {statusLabel.title}
                </h2>
                <p className="mt-3.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                  {statusLabel.sub}
                </p>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        {/* Live transcription + response */}
        <div className="w-full max-w-[820px]">
          <div className="grid gap-3 lg:grid-cols-2">
            <TranscriptionPanel
              label="You"
              text={spoken}
              aura="216 195 154"
              active={phase === 'listening'}
              placeholder="Waiting for speech…"
              minimal={false}
            />
            <TranscriptionPanel
              label="AURELIS"
              text={reply}
              aura={active.aura}
              active={phase === 'thinking' || phase === 'responding'}
              placeholder={phase === 'thinking' ? 'Reasoning over the request…' : 'Not speaking'}
              minimal
              thinking={phase === 'thinking'}
            />
          </div>

          {/* Controls */}
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            {phase === 'idle' ? (
              <Button
                size="lg"
                aura={active.aura}
                onClick={() =>
                  runSession(
                    DEMO_UTTERANCES[Math.floor(Math.random() * DEMO_UTTERANCES.length)],
                  )
                }
              >
                <Mic className="h-4 w-4" />
                Begin voice session
              </Button>
            ) : (
              <Button size="lg" variant="secondary" onClick={stop}>
                <Square className="h-3.5 w-3.5 fill-current" />
                End session
              </Button>
            )}

            <Button
              size="lg"
              variant="ghost"
              onClick={() =>
                runSession(
                  DEMO_UTTERANCES[Math.floor(Math.random() * DEMO_UTTERANCES.length)],
                )
              }
              disabled={phase !== 'idle'}
            >
              <MicOff className="h-4 w-4" />
              New prompt
            </Button>

            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/50">
              {aiState === 'idle' ? 'Core nominal' : aiState}
            </span>
          </div>

          {/* Session log */}
          {history.length > 0 && (
            <div className="mt-9">
              <div className="mb-3 flex items-center gap-3">
                <span className="h-px w-6 bg-white/20" />
                <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                  Session log
                </span>
              </div>
              <div className="space-y-2">
                {history
                  .slice()
                  .reverse()
                  .slice(0, 4)
                  .map((h, i) => (
                    <motion.div
                      key={h.id}
                      initial={{ opacity: 0, x: h.role === 'you' ? 14 : -14 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.5, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                    >
                      <GlassCard layer="flat" className="flex gap-4 p-4">
                        <span
                          className={cx(
                            'mt-1 h-1.5 w-1.5 shrink-0 rounded-full',
                          )}
                          style={{
                            background:
                              h.role === 'you'
                                ? rgba('216 195 154', 0.9)
                                : rgba(active.aura, 0.9),
                          }}
                        />
                        <div className="min-w-0">
                          <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70">
                            {h.role === 'you' ? 'You' : 'AURELIS'}
                          </div>
                          <p className="mt-1.5 text-[13px] leading-relaxed text-platinum-soft/80">
                            {h.text}
                          </p>
                        </div>
                      </GlassCard>
                    </motion.div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─ Peripheral waveform ring ──────────────────────────────────── */

function WaveformRing({ aura, amplitude }: { aura: string; amplitude: number }) {
  const bars = useMemo(
    () => Array.from({ length: 120 }, (_, i) => ({ id: i, base: seeded(i * 1.9) })),
    [],
  );

  return (
    <svg
      viewBox="0 0 600 600"
      className="h-full w-full"
      aria-hidden
      style={{ overflow: 'visible' }}
    >
      {bars.map((b, i) => {
        const angle = (i / bars.length) * Math.PI * 2;
        const r = 208;
        const h = 4 + b.base * 16 + amplitude * 30;
        const x1 = 300 + Math.cos(angle) * r;
        const y1 = 300 + Math.sin(angle) * r;
        const x2 = 300 + Math.cos(angle) * (r + h);
        const y2 = 300 + Math.sin(angle) * (r + h);
        return (
          <motion.line
            key={b.id}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={rgba(aura, 0.55)}
            strokeWidth={1.4}
            strokeLinecap="round"
            animate={{
              opacity: [0.2, 0.85, 0.25],
              x2: x2,
              y2: y2,
            }}
            transition={{
              duration: 0.7 + b.base * 0.9,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: b.base * 0.5,
            }}
          />
        );
      })}
    </svg>
  );
}

/* ─ Transcription panel ───────────────────────────────────────── */

function TranscriptionPanel({
  label,
  text,
  aura,
  active,
  placeholder,
  minimal,
  thinking = false,
}: {
  label: string;
  text: string;
  aura: string;
  active: boolean;
  placeholder: string;
  minimal: boolean;
  thinking?: boolean;
}) {
  return (
    <div
      className="relative min-h-[132px] overflow-hidden rounded-xl border p-4 transition-colors duration-500"
      style={{
        borderColor: active ? rgba(aura, 0.28) : 'rgba(255,255,255,0.06)',
        background: active ? rgba(aura, 0.045) : 'rgba(255,255,255,0.015)',
      }}
    >
      <div className="flex items-center justify-between">
        <span
          className="font-mono text-3xs uppercase tracking-widest2"
          style={{ color: active ? rgba(aura, 0.95) : 'rgba(143,149,163,0.8)' }}
        >
          {label}
        </span>
        {active && (
          <span className="flex items-center gap-1.5">
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="h-1 w-1 rounded-full"
                style={{ background: rgba(aura, 0.9) }}
                animate={{ opacity: [0.25, 1, 0.25] }}
                transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.16 }}
              />
            ))}
          </span>
        )}
      </div>

      <p
        className={cx(
          'mt-3 text-[13.5px] leading-[1.7]',
          text ? 'text-platinum-soft/92' : 'text-platinum-dim/50',
          minimal && 'italic',
        )}
      >
        {text || placeholder}
        {active && text && (
          <motion.span
            className="ml-0.5 inline-block h-[13px] w-[2px] translate-y-[2px]"
            style={{ background: rgba(aura, 0.9) }}
            animate={{ opacity: [1, 0, 1] }}
            transition={{ duration: 0.9, repeat: Infinity }}
          />
        )}
      </p>

      {thinking && (
        <div className="mt-3 flex gap-1">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <motion.span
              key={i}
              className="h-[2px] w-4 rounded-full"
              style={{ background: rgba(aura, 0.75) }}
              animate={{ opacity: [0.15, 0.9, 0.15], scaleY: [1, 2.4, 1] }}
              transition={{ duration: 1.3, repeat: Infinity, delay: i * 0.1 }}
            />
          ))}
        </div>
      )}
    </div>
  );
}