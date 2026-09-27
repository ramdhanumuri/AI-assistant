/* The single source of truth for "who is signed in".

   Every component reads auth through `useAuth()`. No component calls the auth
   endpoints directly, so there is exactly one place that can drift.

   Two rules this file exists to enforce:

   * The role is whatever the *server* last told us. Nothing here reads a role
     from a URL, a form or storage, and `updateProfile` cannot change it — the
     backend would reject the field anyway (`extra="forbid"`).
   * `status` starts as `loading`, never `unauthenticated`. The app renders a
     splash until the boot-time `/auth/me` resolves, so a signed-in user never
     sees a login screen flash on reload. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { ApiError, authApi, errorMessage, onSessionExpired, refreshSession } from '@/lib/api';
import type { AuthUser, LoginInput, Preferences, RegisterInput } from '@/lib/authTypes';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthState {
  status: AuthStatus;
  user: AuthUser | null;
  preferences: Preferences | null;
  accessTokenExpiresAt: number | null;

  isAuthenticated: boolean;
  isAdmin: boolean;

  /* Set when the session ended on its own (expiry, revocation, deactivation)
     rather than because the user pressed sign out. The login screen uses it to
     explain why the user is looking at it again. */
  endedReason: string | null;
  clearEndedReason: () => void;

  login: (input: LoginInput) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;

  updateProfile: (patch: { fullName?: string; avatarUrl?: string | null }) => Promise<void>;
  updatePreferences: (patch: Partial<Preferences>) => Promise<void>;

  /* Re-read the identity from the server. Used after a password change, which
     revokes every other session. */
  reload: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/* Refresh this long before the access token actually expires, so an ordinary
   request never has to eat the refresh round trip. */
const REFRESH_LEAD_MS = 60_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [accessTokenExpiresAt, setAccessTokenExpiresAt] = useState<number | null>(null);
  const [endedReason, setEndedReason] = useState<string | null>(null);

  /* Guards against setting state after the provider unmounts (StrictMode
     double-invokes effects in development). */
  const mountedRef = useRef(true);

  const applySession = useCallback(
    (next: {
      user: AuthUser;
      preferences: Preferences;
      accessTokenExpiresAt: number;
    }) => {
      setUser(next.user);
      setPreferences(next.preferences);
      setAccessTokenExpiresAt(next.accessTokenExpiresAt);
      setStatus('authenticated');
      setEndedReason(null);
    },
    [],
  );

  const clearSession = useCallback((reason: string | null) => {
    setUser(null);
    setPreferences(null);
    setAccessTokenExpiresAt(null);
    setStatus('unauthenticated');
    setEndedReason(reason);
  }, []);

  /* ── Boot: decide between the app and the login screen ──────────── */
  useEffect(() => {
    mountedRef.current = true;
    const controller = new AbortController();

    void (async () => {
      try {
        const state = await authApi.me(controller.signal);
        if (!mountedRef.current) return;
        applySession(state);
      } catch (error) {
        if (!mountedRef.current) return;
        if (error instanceof DOMException && error.name === 'AbortError') return;
        /* 401 is the expected answer for a signed-out visitor; anything else
           (a 500, an offline backend) must not be reported as a session
           expiry, but it does still mean we have no identity to render. */
        clearSession(null);
      }
    })();

    return () => {
      mountedRef.current = false;
      controller.abort();
    };
  }, [applySession, clearSession]);

  /* ── The API layer tells us when a refresh ultimately failed ─────── */
  useEffect(
    () =>
      onSessionExpired(() => {
        if (!mountedRef.current) return;
        clearSession('Your session has expired. Please sign in again.');
      }),
    [clearSession],
  );

  /* ── Proactive refresh, so writes rarely hit a 401 at all ───────── */
  useEffect(() => {
    if (status !== 'authenticated' || !accessTokenExpiresAt) return;

    const delay = Math.max(5_000, accessTokenExpiresAt - Date.now() - REFRESH_LEAD_MS);
    const timer = window.setTimeout(() => {
      void (async () => {
        const ok = await refreshSession();
        if (!ok) {
          if (mountedRef.current) {
            clearSession('Your session has expired. Please sign in again.');
          }
          return;
        }
        try {
          const state = await authApi.me();
          if (mountedRef.current) applySession(state);
        } catch {
          /* The refresh succeeded, so the session is alive; a failed identity
             read here is transient and the next boot will reconcile it. */
        }
      })();
    }, delay);

    return () => window.clearTimeout(timer);
  }, [accessTokenExpiresAt, applySession, clearSession, status]);

  const login = useCallback(
    async (input: LoginInput) => {
      const state = await authApi.login(input);
      applySession(state);
    },
    [applySession],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const state = await authApi.register(input);
      applySession(state);
    },
    [applySession],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (error) {
      /* A failed logout must still leave the UI signed out: the local session
         is already unusable from the user's point of view, and the server
         cookie will be cleared by the next 401/refresh cycle. Surface the
         problem rather than silently pretending it worked. */
      if (!(error instanceof ApiError) || error.kind !== 'unauthorized') {
        throw error;
      }
    } finally {
      if (mountedRef.current) clearSession(null);
    }
  }, [clearSession]);

  const updateProfile = useCallback(
    async (patch: { fullName?: string; avatarUrl?: string | null }) => {
      const updated = await authApi.updateProfile(patch);
      if (mountedRef.current) setUser(updated);
    },
    [],
  );

  const updatePreferences = useCallback(async (patch: Partial<Preferences>) => {
    const updated = await authApi.updatePreferences(patch);
    if (mountedRef.current) setPreferences(updated);
  }, []);

  const reload = useCallback(async () => {
    const state = await authApi.me();
    if (mountedRef.current) applySession(state);
  }, [applySession]);

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      preferences,
      accessTokenExpiresAt,
      isAuthenticated: status === 'authenticated' && user !== null,
      /* Derived from the server's value only. */
      isAdmin: status === 'authenticated' && user?.role === 'admin',
      endedReason,
      clearEndedReason: () => setEndedReason(null),
      login,
      register,
      logout,
      updateProfile,
      updatePreferences,
      reload,
    }),
    [
      status,
      user,
      preferences,
      accessTokenExpiresAt,
      endedReason,
      login,
      register,
      logout,
      updateProfile,
      updatePreferences,
      reload,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export { errorMessage };
