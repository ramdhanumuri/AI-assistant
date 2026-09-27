/* Shared chrome for the signed-out screens.

   These pages sit *outside* the app shell (no sidebar, no top navigation), so
   they carry their own ambient backdrop and wordmark. The backdrop reuses the
   same aura system as the app so the transition into the product feels
   continuous rather than like a separate site. */

import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Link } from '@/lib/router';
import { AmbientBackground } from '@/components/AmbientBackground';
import { cx } from '@/lib/utils';

export function AuthShell({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
  wide = false,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="relative flex min-h-full w-full flex-col overflow-y-auto bg-obsidian-950">
      <AmbientBackground aura="110 168 255" variant="home" intense={false} />

      {/* Back to the public landing page */}
      <header className="relative z-20 flex shrink-0 items-center justify-between px-5 py-5 lg:px-10">
        <Link
          to="/"
          className="flex items-center gap-3 rounded-lg transition-opacity duration-300 hover:opacity-80"
          aria-label="AURELIS home"
        >
          <span className="text-[15px] font-light tracking-[0.34em] text-platinum">AURELIS</span>
        </Link>
        <span className="hidden font-mono text-3xs uppercase tracking-widest2 text-platinum-dim sm:block">
          Secure access
        </span>
      </header>

      <main className="relative z-10 flex flex-1 items-center justify-center px-5 pb-10 pt-2 sm:pb-16">
        <motion.div
          initial={{ opacity: 0, y: 18, filter: 'blur(12px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className={cx('w-full', wide ? 'max-w-[560px]' : 'max-w-[440px]')}
        >
          <div className="mb-8 text-center">
            <div className="eyebrow">{eyebrow}</div>
            <h1 className="mt-3 text-[clamp(1.7rem,4.4vw,2.3rem)] font-extralight tracking-[-0.03em] gradient-platinum">
              {title}
            </h1>
            <p className="mx-auto mt-3 max-w-[38ch] text-[13.5px] leading-relaxed text-platinum-dim">
              {subtitle}
            </p>
          </div>

          <div className="glass edge-light rounded-[20px] p-6 shadow-glass sm:p-8">{children}</div>

          {footer && (
            <div className="mt-6 text-center text-[12.5px] text-platinum-dim">{footer}</div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
