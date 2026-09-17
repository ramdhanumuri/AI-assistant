# AGENTS.md

## Project

AURELIS — a premium dark-luxury AI assistant frontend. React 18 + TypeScript +
Vite 5 + Tailwind + Framer Motion + Lucide. No backend: the model layer is a
deterministic local simulator in `src/lib/engine.ts`.

## Commands

```bash
npm run dev        # vite on 0.0.0.0:12000 (proxy host)
npm run build      # tsc --noEmit && vite build
npm run typecheck  # tsc --noEmit
```

Always typecheck before considering work done. `npm run build` runs it too.

## Dev-server proxy

The preview host is `*.prod-runtime.all-hands.dev`, so `vite.config.ts` sets
`server.allowedHosts` to `['.prod-runtime.all-hands.dev', 'localhost']`. Removing
it breaks the proxied preview with a host-check error.

## Architecture notes

- **Single state layer.** `src/state/AppContext.tsx` owns view, mode, AI state,
  conversations, settings, overlays and toasts. Views are presentational and
  read/write through `useApp()`. Global keyboard shortcuts live here.
- **`src/lib/engine.ts` is the seam** between UI and "model". It synthesises a
  response from the prompt and streams it. Swapping in a real LLM means
  replacing this module only; consumers use its streaming interface unchanged.
- **Design tokens** live in `tailwind.config.ts` plus CSS variables in
  `src/styles/globals.css` (obsidian→titanium ramp, platinum text tiers,
  champagne accent, per-mode `aura`). Prefer tokens over raw colour values.
- **Mode identity** is driven by `MODE_BY_ID[id].aura`, threaded through glass,
  glow and orb components rather than hardcoded per view.

## Pitfalls hit before — do not reintroduce

- **No side effects inside a `setState` updater.** The Escape handler previously
  closed overlays from within an updater function; that is impure and doubles
  under StrictMode. Keep side effects outside updaters.
- **Scope streaming state to the live turn.** `ChatInterface` must only attach
  live reasoning/traces to the turn currently streaming, otherwise completed
  messages render stale "thinking" data.
- **Guard against re-entrant simulated sessions.** `VoiceInterface.runSession`
  early-returns unless its `phaseRef` is `idle`. Without the guard, a second
  click interleaves timers from two sessions and the phase desyncs.
- **Timers must be cleared on unmount** (`useEffect(() => clearTimers, ...)`),
  or a view switch leaves orphaned `setTimeout` calls firing into a dead tree.
- **Custom list markers need `list-none`.** Timeline blocks use a gradient line
  plus custom dots; leaving default `<ol>` markers adds stray numbers.

## Accessibility baseline

Keyboard operability everywhere, visible focus rings, ARIA labels on icon-only
controls, and reduced-motion support via `useReducedMotion` plus the in-app
`settings.reduceMotion` toggle. Keep these intact when adding components.

## Verification

Simulated timings mean a phase change is not observable in the same instant as
the click. When verifying voice or streaming behaviour in a browser, wait a few
seconds before reading state; accessibility snapshots can also lag behind the
DOM.