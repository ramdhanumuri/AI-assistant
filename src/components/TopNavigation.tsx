import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { useApp } from '@/state/AppContext';
import { MODE_BY_ID } from '@/data/mock';
import { cx, formatClock, rgba, useModLabel } from '@/lib/utils';
import { SidebarToggle } from '@/components/Sidebar';
import { StatusPill } from '@/components/Primitives';

const VIEW_TITLES: Record<string, { title: string; caption: string }> = {
  home: { title: 'Intelligence Home', caption: 'Ambient interface' },
  conversation: { title: 'Conversation', caption: 'Private thread' },
  voice: { title: 'Voice', caption: 'Live dialogue' },
  dashboard: { title: 'Intelligence Overview', caption: 'Activity & utilisation' },
  knowledge: { title: 'Knowledge', caption: 'Indexed corpus' },
  tools: { title: 'Tools', caption: 'Connected systems' },
  memory: { title: 'Memory', caption: 'Learned preferences' },
  projects: { title: 'Projects', caption: 'Active workstreams' },
};

export function TopNavigation({ meta: metaOverride }: { meta?: { title: string; caption: string } } = {}) {
  const { view, mode, aiState, settings, isStreaming, liveTokens } = useApp();
  const mod = useModLabel();
  const [clock, setClock] = useState(() => formatClock());
  const active = MODE_BY_ID[mode];
  /* Routes that live outside the view system (/profile, /admin) pass their own
     heading; otherwise it is derived from the current view. */
  const meta = metaOverride ?? VIEW_TITLES[view] ?? VIEW_TITLES.home;

  useEffect(() => {
    const t = window.setInterval(() => setClock(formatClock()), 15_000);
    return () => window.clearInterval(t);
  }, []);

  const stateLabel =
    aiState === 'idle'
      ? 'Standing by'
      : aiState === 'listening'
        ? 'Listening'
        : aiState === 'thinking'
          ? 'Reasoning'
          : 'Composing';

  return (
    <header className="relative z-30 shrink-0">
      <div className="flex h-16 items-center gap-4 px-5 lg:px-8">
        <SidebarToggle className="lg:hidden" />

        {/* Breadcrumb */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <motion.h1
              key={meta.title}
              initial={{ opacity: 0, y: 6, filter: 'blur(4px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="truncate text-[13.5px] font-light tracking-[0.14em] text-platinum"
            >
              {meta.title.toUpperCase()}
            </motion.h1>
            <span className="hidden h-3 w-px bg-white/12 sm:block" />
            <span className="hidden font-mono text-3xs uppercase tracking-widest2 text-platinum-dim sm:block">
              {meta.caption}
            </span>
          </div>
        </div>

        {/* Status cluster */}
        <div className="flex items-center gap-3">
          {/* Live token meter while composing */}
          <motion.div
            className="hidden items-center gap-2.5 md:flex"
            animate={{ opacity: isStreaming ? 1 : 0.45 }}
            transition={{ duration: 0.4 }}
          >
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
              {isStreaming ? `${liveTokens} tok` : 'idle'}
            </span>
            <span className="flex h-3 items-end gap-[2px]">
              {[0, 1, 2, 3].map((i) => (
                <motion.span
                  key={i}
                  className="w-[2px] rounded-full"
                  style={{ background: rgba(active.aura, 0.85) }}
                  animate={
                    isStreaming
                      ? { height: [3, 11, 5, 12, 4] }
                      : { height: 3 + i }
                  }
                  transition={
                    isStreaming
                      ? { duration: 1.1, repeat: Infinity, delay: i * 0.12, ease: 'easeInOut' }
                      : { duration: 0.5 }
                  }
                />
              ))}
            </span>
          </motion.div>

          <span className="hidden h-3 w-px bg-white/12 md:block" />

          <StatusPill
            label={stateLabel}
            aura={active.aura}
            pulse={aiState !== 'idle'}
            className="hidden sm:inline-flex"
          />

          <span className="hidden font-mono text-3xs uppercase tracking-widest2 text-platinum-dim lg:block">
            {clock} UTC
          </span>

          <div className="hidden items-center gap-2 rounded-full border border-white/[0.06] bg-white/[0.025] px-3 py-1.5 lg:flex">
            <ShieldCheck className="h-3 w-3 text-champagne/80" />
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
              {settings.citations ? 'Private · cited' : 'Private'}
            </span>
          </div>

          <div className="hidden xl:flex items-center gap-2">
            <kbd
              className={cx(
                'rounded border border-white/[0.08] bg-white/[0.03] px-2 py-1',
                'font-mono text-3xs uppercase tracking-wider text-platinum-dim',
              )}
            >
              {mod}K
            </kbd>
          </div>
        </div>
      </div>

      {/* Hairline under the bar with a live segment tracking the aura */}
      <div className="relative h-px w-full bg-white/[0.05]">
        <motion.div
          className="absolute inset-y-0 left-0"
          animate={{ width: isStreaming ? '100%' : '38%' }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          style={{
            background: `linear-gradient(90deg, transparent, ${rgba(
              active.aura,
              0.55,
            )}, transparent)`,
          }}
        />
      </div>
    </header>
  );
}