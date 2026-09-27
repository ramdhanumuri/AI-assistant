import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  Brain,
  ChevronsLeft,
  FolderKanban,
  Library,
  MessagesSquare,
  PanelLeft,
  Plus,
  Plug,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { useMemo } from 'react';
import { useApp } from '@/state/AppContext';
import { useAuth } from '@/state/AuthContext';
import { Link } from '@/lib/router';
import { MODE_BY_ID } from '@/data/mock';
import { cx, formatRelative, rgba } from '@/lib/utils';
import { UserMenu } from '@/components/UserMenu';
import type { ViewId } from '@/types';

const NAV: { id: ViewId; label: string; icon: typeof Activity }[] = [
  { id: 'conversation', label: 'Conversations', icon: MessagesSquare },
  { id: 'projects', label: 'Projects', icon: FolderKanban },
  { id: 'knowledge', label: 'Knowledge', icon: Library },
  { id: 'tools', label: 'Tools', icon: Plug },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'dashboard', label: 'Intelligence', icon: Activity },
];

export function Sidebar() {
  const {
    sidebarOpen,
    toggleSidebar,
    view,
    setView,
    conversations,
    openConversation,
    activeConversationId,
    newConversation,
    setCommandOpen,
    setSettingsOpen,
    mode,
    aiState,
    settings,
    isStreaming,
  } = useApp();

  const active = MODE_BY_ID[mode];
  const recent = useMemo(() => conversations.slice(0, 7), [conversations]);
  const { isAdmin } = useAuth();

  return (
    <>
      {/* Mobile scrim */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            key="scrim"
            className="fixed inset-0 z-30 bg-obsidian-950/70 backdrop-blur-sm lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={toggleSidebar}
            aria-hidden
          />
        )}
      </AnimatePresence>

      <motion.aside
        aria-label="Primary navigation"
        initial={false}
        animate={{ width: sidebarOpen ? 268 : 76 }}
        transition={{ type: 'spring', stiffness: 340, damping: 34, mass: 0.7 }}
        className={cx(
          'relative z-40 flex shrink-0 flex-col overflow-hidden',
          'border-r border-white/[0.055] bg-obsidian-950/72 backdrop-blur-2xl',
          'max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:transition-transform max-lg:duration-500 max-lg:ease-cinematic',
          !sidebarOpen && 'max-lg:-translate-x-full',
        )}
      >
        {/* AI Core identity */}
        <div className="relative shrink-0 px-5 pt-6 pb-5">
          <button
            type="button"
            onClick={() => setView('home')}
            className="flex w-full items-center gap-3.5 rounded-xl text-left transition-opacity hover:opacity-90"
            aria-label="AURELIS home"
          >
            <CoreMark aura={active.aura} active={aiState !== 'idle'} />
            <AnimatePresence initial={false}>
              {sidebarOpen && (
                <motion.div
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                  className="min-w-0"
                >
                  <div className="text-[0.95rem] font-light tracking-[0.3em] text-platinum">
                    AURELIS
                  </div>
                  <div className="mt-1 truncate font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                    {aiState === 'idle' ? 'Standing by' : `${active.label} · active`}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </button>
        </div>

        {/* Primary action */}
        <div className="shrink-0 px-3.5 pb-4">
          <button
            type="button"
            onClick={newConversation}
            className={cx(
              'group relative flex h-11 w-full items-center gap-3 overflow-hidden rounded-xl',
              'border border-white/[0.08] bg-white/[0.035] transition-all duration-500 ease-cinematic',
              'hover:border-white/[0.16] hover:bg-white/[0.06]',
              sidebarOpen ? 'px-4' : 'justify-center px-0',
            )}
            aria-label="New conversation"
          >
            <span
              aria-hidden
              className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-0 transition-all duration-[900ms] ease-cinematic group-hover:left-[120%] group-hover:opacity-100"
            />
            <Plus className="h-4 w-4 shrink-0 text-platinum-dim transition-colors group-hover:text-champagne" />
            {sidebarOpen && (
              <span className="font-mono text-[10px] uppercase tracking-widest2 text-platinum-dim transition-colors group-hover:text-platinum">
                New conversation
              </span>
            )}
          </button>
        </div>

        {/* Search / command trigger */}
        <div className="shrink-0 px-3.5 pb-3">
          <button
            type="button"
            onClick={() => setCommandOpen(true)}
            className={cx(
              'flex h-10 w-full items-center gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02]',
              'text-left transition-colors duration-400 hover:border-white/[0.12] hover:bg-white/[0.05]',
              sidebarOpen ? 'px-4' : 'justify-center px-0',
            )}
            aria-label="Open command center"
          >
            <Search className="h-3.5 w-3.5 shrink-0 text-platinum-dim" />
            {sidebarOpen && (
              <>
                <span className="flex-1 font-mono text-[10px] uppercase tracking-widest2 text-platinum-dim/70">
                  Command
                </span>
                <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[9px] text-platinum-dim">
                  ⌘K
                </kbd>
              </>
            )}
          </button>
        </div>

        <div className="hairline mx-4 shrink-0" />

        {/* Navigation */}
        <nav className="shrink-0 px-3.5 py-3">
          <ul className="space-y-0.5">
            {NAV.map((item) => {
              const isActive = view === item.id;
              const Icon = item.icon;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setView(item.id)}
                    aria-current={isActive ? 'page' : undefined}
                    className={cx(
                      'group relative flex h-10 w-full items-center gap-3 rounded-lg transition-colors duration-400',
                      sidebarOpen ? 'px-3.5' : 'justify-center px-0',
                      isActive ? 'text-platinum' : 'text-platinum-dim hover:text-platinum',
                    )}
                  >
                    {isActive && (
                      <motion.span
                        layoutId="sidebar-active"
                        transition={{ type: 'spring', stiffness: 380, damping: 34 }}
                        className="absolute inset-0 rounded-lg border border-white/[0.09]"
                        style={{
                          background: `linear-gradient(100deg, ${rgba(
                            active.aura,
                            0.13,
                          )}, rgba(255,255,255,0.015))`,
                        }}
                      />
                    )}
                    {isActive && (
                      <span
                        aria-hidden
                        className="absolute -left-3.5 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full"
                        style={{
                          background: rgba(active.aura, 0.95),
                          boxShadow: `0 0 12px ${rgba(active.aura, 0.85)}`,
                        }}
                      />
                    )}
                    <Icon className="relative z-10 h-4 w-4 shrink-0" />
                    {sidebarOpen && (
                      <span className="relative z-10 font-mono text-[10.5px] uppercase tracking-widest2">
                        {item.label}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="hairline mx-4 shrink-0" />

        {/* Recent threads */}
        <div className="min-h-0 flex-1 overflow-y-auto px-3.5 py-4">
          {sidebarOpen ? (
            <>
              <div className="mb-3 flex items-center justify-between px-1">
                <span className="eyebrow">Recent</span>
                <span className="font-mono text-[9px] text-platinum-dim/60">
                  {conversations.length}
                </span>
              </div>
              <ul className="space-y-0.5">
                {recent.map((c) => {
                  const isActive = c.id === activeConversationId;
                  const cMode = MODE_BY_ID[c.mode];
                  return (
                    <li key={c.id}>
                      <button
                        type="button"
                        onClick={() => openConversation(c.id)}
                        className={cx(
                          'group relative w-full rounded-lg px-3 py-2.5 text-left transition-colors duration-400',
                          isActive ? 'bg-white/[0.055]' : 'hover:bg-white/[0.03]',
                        )}
                      >
                        <div className="flex items-start gap-2.5">
                          <span
                            className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                            style={{
                              background: rgba(cMode.aura, isActive ? 0.95 : 0.4),
                              boxShadow: isActive ? `0 0 8px ${rgba(cMode.aura, 0.8)}` : 'none',
                            }}
                          />
                          <div className="min-w-0 flex-1">
                            <div
                              className={cx(
                                'truncate text-[12.5px] leading-snug transition-colors',
                                isActive
                                  ? 'text-platinum'
                                  : 'text-platinum-soft/85 group-hover:text-platinum',
                              )}
                            >
                              {c.title}
                            </div>
                            <div className="mt-1 flex items-center gap-2 font-mono text-[9px] uppercase tracking-wider text-platinum-dim/60">
                              <span>{cMode.label}</span>
                              <span className="opacity-40">·</span>
                              <span>{formatRelative(c.updatedAt)}</span>
                              {c.pinned && (
                                <>
                                  <span className="opacity-40">·</span>
                                  <span className="text-champagne/70">Pinned</span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <div className="flex flex-col items-center gap-2 pt-2">
              {recent.slice(0, 5).map((c) => {
                const cMode = MODE_BY_ID[c.mode];
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => openConversation(c.id)}
                    aria-label={c.title}
                    className="flex h-9 w-9 items-center justify-center rounded-lg transition-colors hover:bg-white/[0.05]"
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ background: rgba(cMode.aura, 0.7) }}
                    />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-white/[0.05] p-3.5">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className={cx(
              'flex h-10 w-full items-center gap-3 rounded-lg text-platinum-dim transition-colors duration-400 hover:bg-white/[0.04] hover:text-platinum',
              sidebarOpen ? 'px-3.5' : 'justify-center px-0',
            )}
            aria-label="Settings"
          >
            <Settings2 className="h-4 w-4 shrink-0" />
            {sidebarOpen && (
              <span className="font-mono text-[10.5px] uppercase tracking-widest2">
                Settings
              </span>
            )}
          </button>

          {/* Administration is rendered only for a server-confirmed admin.
              Hiding it is cosmetic — `/api/v1/admin/*` re-checks the role. */}
          {isAdmin && (
            <Link
              to="/admin"
              className={cx(
                'flex h-10 w-full items-center gap-3 rounded-lg text-champagne/90 transition-colors duration-400 hover:bg-champagne/[0.07] hover:text-champagne-bright',
                sidebarOpen ? 'px-3.5' : 'justify-center px-0',
              )}
              title="Administration"
            >
              <ShieldCheck className="h-4 w-4 shrink-0" />
              {sidebarOpen && (
                <span className="font-mono text-[10.5px] uppercase tracking-widest2">
                  Admin
                </span>
              )}
            </Link>
          )}

          <UserMenu collapsed={!sidebarOpen} />

          {sidebarOpen && (
            <div className="mt-3 flex items-center justify-between rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2.5">
              <div className="flex items-center gap-2">
                <Sparkles className="h-3 w-3 text-champagne/80" />
                <span className="font-mono text-[9px] uppercase tracking-widest2 text-platinum-dim">
                  {settings.memory ? 'Memory on' : 'Memory off'}
                </span>
              </div>
              <span
                className="font-mono text-[9px] uppercase tracking-widest2"
                style={{
                  color: isStreaming ? rgba(active.aura, 1) : 'rgba(139,147,163,0.7)',
                }}
              >
                {isStreaming ? 'live' : 'idle'}
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={toggleSidebar}
            className={cx(
              'mt-2 flex h-9 w-full items-center gap-3 rounded-lg text-platinum-dim/70 transition-colors duration-400 hover:bg-white/[0.04] hover:text-platinum',
              sidebarOpen ? 'px-3.5' : 'justify-center px-0',
            )}
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <ChevronsLeft
              className={cx(
                'h-3.5 w-3.5 shrink-0 transition-transform duration-500 ease-cinematic',
                !sidebarOpen && 'rotate-180',
              )}
            />
            {sidebarOpen && (
              <span className="font-mono text-[9.5px] uppercase tracking-widest2">
                Collapse
              </span>
            )}
          </button>
        </div>
      </motion.aside>
    </>
  );
}

/** Compact identity mark used in the sidebar header. */
function CoreMark({ aura, active }: { aura: string; active: boolean }) {
  return (
    <span className="relative flex h-9 w-9 shrink-0 items-center justify-center">
      <span
        className="absolute inset-0 rounded-full border"
        style={{ borderColor: rgba(aura, 0.22) }}
      />
      <motion.span
        className="absolute inset-[5px] rounded-full"
        style={{
          background: `radial-gradient(circle at 38% 32%, #fff 0%, ${rgba(
            aura,
            0.9,
          )} 34%, ${rgba(aura, 0.25)} 70%, transparent 88%)`,
        }}
        animate={
          active
            ? { opacity: [0.7, 1, 0.7], scale: [1, 1.1, 1] }
            : { opacity: [0.65, 0.95, 0.65], scale: [1, 1.04, 1] }
        }
        transition={{ duration: active ? 2.2 : 5.4, repeat: Infinity, ease: 'easeInOut' }}
      />
    </span>
  );
}

/** Exported for the mobile top bar. */
export function SidebarToggle({ className }: { className?: string }) {
  const { toggleSidebar } = useApp();
  return (
    <button
      type="button"
      onClick={toggleSidebar}
      aria-label="Toggle navigation"
      className={cx(
        'flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.07] bg-white/[0.03] text-platinum-dim transition-colors hover:text-platinum',
        className,
      )}
    >
      <PanelLeft className="h-4 w-4" />
    </button>
  );
}