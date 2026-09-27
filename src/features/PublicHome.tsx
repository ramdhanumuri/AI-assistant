/* The public landing page at `/`.

   Rendered only for signed-out visitors: `/` redirects an authenticated user
   straight into the workspace. It therefore lives outside `AppProvider` and
   reads nothing from `useApp()` — only `useAuth()` for the sign-in state. */

import { motion } from 'framer-motion';
import { ArrowRight, Lock, ShieldCheck, Sparkles } from 'lucide-react';
import { AmbientBackground, ParticleField } from '@/components/AmbientBackground';
import { AIOrb } from '@/components/AIOrb';
import { Button, GlassCard, SectionLabel } from '@/components/Primitives';
import { Link } from '@/lib/router';
import { rgba } from '@/lib/utils';

const AURA = '110 168 255';

const PILLARS = [
  {
    icon: Lock,
    title: 'Private by architecture',
    body: 'Sessions live in HttpOnly cookies. Nothing token-shaped is ever readable from the page, and no credential is stored in the browser.',
  },
  {
    icon: ShieldCheck,
    title: 'Server-enforced access',
    body: 'Roles are owned by the server. Every protected call re-checks your identity and role on the way in — the interface is never the authority.',
  },
  {
    icon: Sparkles,
    title: 'Context that persists',
    body: 'Preferences, memory and conversation history follow your account across devices, scoped to you and nobody else.',
  },
];

export function PublicHome() {
  return (
    <div className="relative min-h-full w-full overflow-y-auto bg-obsidian-950">
      <AmbientBackground aura={AURA} variant="home" intense />
      <ParticleField aura={AURA} count={30} />

      <div className="relative z-10">
        <header className="flex items-center justify-between px-5 py-5 lg:px-12">
          <span className="text-[15px] font-light tracking-[0.34em] text-platinum">AURELIS</span>
          <nav className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-full px-4 py-2 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors duration-300 hover:text-platinum"
            >
              Sign in
            </Link>
            <Link to="/register">
              <Button variant="gold" size="sm">
                Create account
              </Button>
            </Link>
          </nav>
        </header>

        <section className="px-5 pb-16 pt-8 lg:px-12 lg:pt-16">
          <div className="mx-auto grid w-full max-w-[1240px] items-center gap-14 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="order-2 lg:order-1">
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="font-mono text-3xs uppercase tracking-widest3 text-platinum-dim/70"
              >
                Private intelligence layer
              </motion.div>

              <h1 className="mt-7 text-cinematic">
                <motion.span
                  initial={{ opacity: 0, y: 24, filter: 'blur(14px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  transition={{ duration: 1, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
                  className="block text-[clamp(2.4rem,6.6vw,4.8rem)] font-extralight gradient-platinum"
                >
                  Your intelligence,
                </motion.span>
                <motion.span
                  initial={{ opacity: 0, y: 24, filter: 'blur(14px)' }}
                  animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  transition={{ duration: 1, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  className="block text-[clamp(2.4rem,6.6vw,4.8rem)] font-extralight gradient-gold italic"
                >
                  amplified.
                </motion.span>
              </h1>

              <motion.p
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.9, delay: 0.36, ease: [0.16, 1, 0.3, 1] }}
                className="mt-7 max-w-[52ch] text-[15px] font-[350] leading-[1.8] text-platinum-soft/68"
              >
                AURELIS reads your context, holds your preferences, and works across research,
                engineering and analysis — quietly, accurately, and entirely on your terms.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.9, delay: 0.46, ease: [0.16, 1, 0.3, 1] }}
                className="mt-10 flex flex-wrap items-center gap-3"
              >
                <Link to="/register">
                  <Button size="lg" aura={AURA}>
                    Create your account
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
                <Link to="/login">
                  <Button size="lg" variant="secondary">
                    Sign in
                  </Button>
                </Link>
              </motion.div>
            </div>

            <div className="order-1 flex items-center justify-center lg:order-2">
              <div className="relative flex h-[320px] w-full items-center justify-center sm:h-[420px] lg:h-[520px]">
                <AIOrb state="idle" aura={AURA} size={380} particles />
              </div>
            </div>
          </div>
        </section>

        <section className="px-5 pb-24 lg:px-12">
          <div className="mx-auto w-full max-w-[1240px]">
            <SectionLabel>Built for trust</SectionLabel>
            <div className="mt-7 grid gap-4 md:grid-cols-3">
              {PILLARS.map((pillar, i) => (
                <motion.div
                  key={pillar.title}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-60px' }}
                  transition={{ duration: 0.7, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                >
                  <GlassCard interactive aura={AURA} className="h-full p-6">
                    <span
                      className="flex h-9 w-9 items-center justify-center rounded-full border"
                      style={{
                        borderColor: rgba(AURA, 0.25),
                        background: rgba(AURA, 0.07),
                      }}
                    >
                      <pillar.icon className="h-4 w-4" style={{ color: rgba(AURA, 1) }} />
                    </span>
                    <h3 className="mt-5 text-[15px] font-light tracking-wide text-platinum">
                      {pillar.title}
                    </h3>
                    <p className="mt-3 text-[12.5px] leading-relaxed text-platinum-soft/62">
                      {pillar.body}
                    </p>
                  </GlassCard>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <footer className="border-t border-white/[0.05] px-5 py-8 lg:px-12">
          <div className="mx-auto flex w-full max-w-[1240px] flex-wrap items-center justify-between gap-4">
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/60">
              AURELIS · Private intelligence
            </span>
            <div className="flex items-center gap-5">
              <Link
                to="/login"
                className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70 transition-colors hover:text-platinum"
              >
                Sign in
              </Link>
              <Link
                to="/register"
                className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/70 transition-colors hover:text-platinum"
              >
                Create account
              </Link>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
