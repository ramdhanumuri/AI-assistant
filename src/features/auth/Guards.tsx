/* Route guards.

   These decide what to *render*. They are a usability layer only — every
   protected API is independently guarded server-side by
   `require_authenticated_user` / `require_admin`, so bypassing these in a
   console buys an attacker nothing but an empty shell and a wall of 401s. */

import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '@/state/AuthContext';
import { useRouter } from '@/lib/router';
import { AmbientBackground } from '@/components/AmbientBackground';
import { Button } from '@/components/Primitives';
import { AuthShell } from '@/features/auth/AuthShell';

/** The boot splash. Rendered until the identity is known, so a signed-in user
 *  never sees the login screen flash on reload. */
export function AuthLoadingScreen() {
  return (
    <div className="relative flex h-full w-full flex-col items-center justify-center bg-obsidian-950">
      <AmbientBackground aura="110 168 255" variant="home" intense={false} />
      <div className="relative z-10 flex flex-col items-center">
        <div className="text-[1.6rem] font-extralight leading-none tracking-[0.44em] text-platinum">
          AURELIS
        </div>
        <div className="mt-5 h-px w-40 overflow-hidden bg-white/10">
          <div className="h-px w-1/3 animate-[shimmer_1.4s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-champagne to-transparent" />
        </div>
        <div className="mt-5 font-mono text-3xs uppercase tracking-widest3 text-platinum-dim">
          Establishing secure session
        </div>
      </div>
      <style>{`
        @keyframes shimmer {
          0%   { transform: translateX(-120%); }
          100% { transform: translateX(420%); }
        }
      `}</style>
    </div>
  );
}

/** Signed-in only. Redirects to `/login` once the auth state has resolved. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const { navigate } = useRouter();

  useEffect(() => {
    if (status === 'unauthenticated') navigate('/login', { replace: true });
  }, [status, navigate]);

  if (status === 'loading') return <AuthLoadingScreen />;
  if (status === 'unauthenticated') return <AuthLoadingScreen />;
  return <>{children}</>;
}

/** Signed-in *and* admin. A normal user gets a professional refusal, not a
 *  redirect loop. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { status, isAdmin } = useAuth();
  const { navigate } = useRouter();

  useEffect(() => {
    if (status === 'unauthenticated') navigate('/login', { replace: true });
  }, [status, navigate]);

  if (status === 'loading' || status === 'unauthenticated') return <AuthLoadingScreen />;
  if (!isAdmin) return <AccessDenied />;
  return <>{children}</>;
}

/** Signed-out only — keeps an authenticated user off `/login` and
 *  `/register`. */
export function RequireGuest({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const { navigate } = useRouter();

  useEffect(() => {
    if (status === 'authenticated') navigate('/chat', { replace: true });
  }, [status, navigate]);

  if (status === 'loading') return <AuthLoadingScreen />;
  if (status === 'authenticated') return <AuthLoadingScreen />;
  return <>{children}</>;
}

export function AccessDenied() {
  const { user } = useAuth();
  const { navigate } = useRouter();

  return (
    <AuthShell
      eyebrow="Authorization"
      title="Access denied"
      subtitle="This area is restricted to administrators. Your account does not carry the required role."
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-champagne" />
          <p className="text-[13px] leading-relaxed text-platinum-soft">
            Authorization is enforced on the server, not in the browser. Signed in as{' '}
            <span className="text-platinum">{user?.email ?? 'unknown'}</span> with role{' '}
            <span className="font-mono text-3xs text-champagne">{user?.role ?? 'unknown'}</span>.
          </p>
        </div>
        <Button size="lg" className="w-full" onClick={() => navigate('/chat')}>
          Return to your workspace
        </Button>
      </div>
    </AuthShell>
  );
}

export function NotFoundScreen() {
  const { status } = useAuth();
  const { navigate } = useRouter();
  const authed = status === 'authenticated';

  return (
    <AuthShell
      eyebrow="Navigation"
      title="Page not found"
      subtitle="That route does not exist in this workspace."
    >
      <Button
        size="lg"
        className="w-full"
        onClick={() => navigate(authed ? '/chat' : '/')}
      >
        {authed ? 'Return to your workspace' : 'Return home'}
      </Button>
    </AuthShell>
  );
}
