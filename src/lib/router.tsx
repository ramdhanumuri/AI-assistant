/* A minimal History-API router.

   The app previously tracked navigation in React state alone, so a deep link
   or a refresh always landed on the home view. Authentication needs real URLs:
   `/login` has to survive a reload, and a bookmarked `/admin` has to resolve
   to the right guard.

   This is deliberately small — the app has eight routes and no nested layouts.
   Pulling in a routing library would cost more than it saves here, and the
   Vite dev server already serves `index.html` for unknown paths. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { cx } from '@/lib/utils';

export type RoutePath =
  | '/'
  | '/login'
  | '/register'
  | '/chat'
  | '/profile'
  | '/settings'
  | '/admin'
  | '/forgot-password'
  | '/reset-password';

export function currentPath(): string {
  if (typeof window === 'undefined') return '/';
  const { pathname } = window.location;
  return pathname === '' ? '/' : pathname.replace(/\/+$/, '') || '/';
}

interface RouterValue {
  path: string;
  navigate: (to: string, options?: { replace?: boolean }) => void;
}

const RouterCtx = createContext<RouterValue | null>(null);

export function RouterProvider({ children }: { children: ReactNode }) {
  const [path, setPath] = useState(currentPath);

  useEffect(() => {
    const onPop = () => setPath(currentPath());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = useCallback((to: string, options?: { replace?: boolean }) => {
    const next = to.startsWith('/') ? to : `/${to}`;
    if (currentPath() === next.replace(/\/+$/, '') || next === '/') {
      /* Same target: still sync state in case it drifted from the URL. */
      setPath(currentPath());
    }
    if (options?.replace) window.history.replaceState(null, '', next);
    else window.history.pushState(null, '', next);
    setPath(currentPath());
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, []);

  const value = useMemo(() => ({ path, navigate }), [path, navigate]);

  return <RouterCtx.Provider value={value}>{children}</RouterCtx.Provider>;
}

export function useRouter(): RouterValue {
  const ctx = useContext(RouterCtx);
  if (!ctx) throw new Error('useRouter must be used inside <RouterProvider>');
  return ctx;
}

export function Link({
  to,
  replace,
  className,
  children,
  ...rest
}: {
  to: string;
  replace?: boolean;
  className?: string;
  children: ReactNode;
} & Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, 'href'>) {
  const { navigate } = useRouter();

  return (
    <a
      href={to}
      className={cx(className)}
      onClick={(event) => {
        /* Let the browser handle modified clicks (new tab, download, …). */
        if (event.defaultPrevented) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (event.button !== 0) return;
        event.preventDefault();
        navigate(to, { replace });
      }}
      {...rest}
    >
      {children}
    </a>
  );
}
