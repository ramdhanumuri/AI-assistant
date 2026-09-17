import { useEffect, useState } from 'react';

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

/** Tailwind-agnostic rgba helper for the aura colour system. */
export function rgba(triple: string, alpha: number): string {
  return `rgba(${triple.split(' ').join(',')},${alpha})`;
}

export function clamp(v: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, v));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * clamp(t);
}

export function formatRelative(ts: number, reference = Date.now()): string {
  const diff = reference - ts;
  const min = 60_000;
  if (diff < min) return 'just now';
  if (diff < 60 * min) return `${Math.floor(diff / min)} min ago`;
  const hr = 60 * min;
  if (diff < 24 * hr) return `${Math.floor(diff / hr)} hr ago`;
  const day = 24 * hr;
  if (diff < 7 * day) return `${Math.floor(diff / day)} d ago`;
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function formatClock(d = new Date()): string {
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export function uid(prefix = 'id'): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Stable pseudo-random in [0,1) from a numeric seed — keeps visuals deterministic. */
export function seeded(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

export function usePrefersReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

/** Tracks whether a media query is false (i.e. the "real" breakpoint gate). */
export function useIsDesktop(): boolean {
  return useMediaQuery('(min-width: 1024px)');
}

export function useIsAtLeast(md: number): boolean {
  return useMediaQuery(`(min-width: ${md}px)`);
}

/** Platform-aware modifier label for shortcut hints. */
export function useModLabel(): string {
  const [mod, setMod] = useState('⌘');
  useEffect(() => {
    const platform =
      (navigator as unknown as { userAgentData?: { platform?: string } }).userAgentData
        ?.platform ?? navigator.platform ?? '';
    if (/win|linux/i.test(platform)) setMod('Ctrl');
  }, []);
  return mod;
}