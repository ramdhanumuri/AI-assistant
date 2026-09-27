/* The signed-in identity chip and its menu.

   Sits in the sidebar footer. Everything it renders is read from
   `useAuth()`, which is in turn fed by the server's `/auth/me` — the role
   badge here is a label, never a permission. */

import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronUp, Loader2, LogOut, Settings, ShieldCheck, UserRound } from 'lucide-react';
import { useAuth } from '@/state/AuthContext';
import { errorMessage } from '@/lib/api';
import { Link, useRouter } from '@/lib/router';
import { cx } from '@/lib/utils';

function initialsOf(name: string, email: string): string {
  const source = name.trim() || email;
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 0) return '··';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export function UserMenu({ collapsed }: { collapsed: boolean }) {
  const { user, isAdmin, logout } = useAuth();
  const { navigate } = useRouter();

  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  /* Close on outside click and on Escape. The listener is only attached while
     open, and the Escape handler is registered outside any state updater. */
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (!user) return null;

  const onSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    setError(null);
    try {
      await logout();
      setOpen(false);
      navigate('/login', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <div ref={rootRef} className="relative mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cx(
          'flex w-full items-center gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] py-2 transition-colors duration-400 hover:border-white/[0.12] hover:bg-white/[0.04]',
          collapsed ? 'justify-center px-0' : 'px-3',
        )}
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-champagne/25 bg-champagne/[0.07] font-mono text-[10px] tracking-wider text-champagne">
          {initialsOf(user.fullName, user.email)}
        </span>

        {!collapsed && (
          <>
            <span className="min-w-0 flex-1 text-left">
              <span className="block truncate text-[12px] text-platinum-soft">
                {user.fullName}
              </span>
              <span className="block truncate font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                {user.role}
              </span>
            </span>
            <ChevronUp
              className={cx(
                'h-3.5 w-3.5 shrink-0 text-platinum-dim transition-transform duration-400 ease-cinematic',
                open && 'rotate-180',
              )}
            />
          </>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: 8, filter: 'blur(8px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: 8, filter: 'blur(8px)' }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className={cx(
              'glass-deep absolute z-50 w-[248px] overflow-hidden rounded-xl p-1.5 shadow-glass-lg',
              collapsed ? 'bottom-0 left-[calc(100%+10px)]' : 'bottom-[calc(100%+8px)] left-0',
            )}
          >
            <div className="px-3 py-2.5">
              <div className="truncate text-[12.5px] text-platinum-soft">{user.fullName}</div>
              <div className="truncate font-mono text-3xs tracking-wider text-platinum-dim">
                {user.email}
              </div>
              {isAdmin && (
                <div className="mt-1.5 inline-flex items-center gap-1.5 rounded-full border border-champagne/25 bg-champagne/[0.07] px-2 py-0.5">
                  <ShieldCheck className="h-2.5 w-2.5 text-champagne" />
                  <span className="font-mono text-3xs uppercase tracking-widest2 text-champagne">
                    Administrator
                  </span>
                </div>
              )}
            </div>

            <div className="hairline my-1" />

            <Link
              to="/profile"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] text-platinum-dim transition-colors duration-300 hover:bg-white/[0.05] hover:text-platinum"
            >
              <UserRound className="h-3.5 w-3.5" />
              Profile & security
            </Link>

            <Link
              to="/settings"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] text-platinum-dim transition-colors duration-300 hover:bg-white/[0.05] hover:text-platinum"
            >
              <Settings className="h-3.5 w-3.5" />
              Preferences
            </Link>

            {isAdmin && (
              <Link
                to="/admin"
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] text-champagne/90 transition-colors duration-300 hover:bg-champagne/[0.07] hover:text-champagne-bright"
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                Administration
              </Link>
            )}

            <div className="hairline my-1" />

            {error && (
              <p role="alert" className="px-3 py-1.5 text-[11.5px] text-rose-300/90">
                {error}
              </p>
            )}

            <button
              type="button"
              role="menuitem"
              onClick={onSignOut}
              disabled={signingOut}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] text-platinum-dim transition-colors duration-300 hover:bg-rose-400/[0.08] hover:text-rose-200 disabled:opacity-50"
            >
              {signingOut ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <LogOut className="h-3.5 w-3.5" />
              )}
              {signingOut ? 'Signing out…' : 'Sign out'}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
