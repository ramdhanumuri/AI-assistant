# AURELIS — Private Intelligence

A premium, futuristic AI assistant interface. AURELIS is a dark, cinematic
"private intelligence layer" — a product that reads as an operating system for
thought rather than a chat window with bubbles.

The application is a fully interactive frontend. The model layer is simulated
locally by a deterministic response engine, so every surface can be exercised
without a backend.

## Stack

- **React 18** + **TypeScript** (strict)
- **Vite 5** for dev and build
- **Tailwind CSS** with a custom design-token layer
- **Framer Motion** for all motion
- **Lucide React** for icons

## Getting started

```bash
npm install
npm run dev      # http://localhost:12000
```

Other scripts:

```bash
npm run build      # typecheck + production bundle
npm run preview    # serve the production build
npm run typecheck  # tsc --noEmit
```

No environment variables are required — there is no backend dependency.

## Experience map

| View | Purpose |
| --- | --- |
| **Intelligence Home** | Cinematic hero, the AI Core orb, mode grid, active workstreams, recent threads |
| **Conversation** | Spatial thread view with rich, block-based assistant responses |
| **Voice** | Full-screen voice environment: listening / thinking / responding |
| **Intelligence Overview** | Metrics, throughput chart, mode distribution, knowledge sources, memory |
| **Knowledge / Tools / Memory / Projects** | Surfaces for the assistant's context layer |
| **Command Center** | Cmd/Ctrl-K control layer with fuzzy search and keyboard navigation |

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Cmd/Ctrl + K` | Toggle Command Center |
| `Cmd/Ctrl + Enter` | Send message |
| `Cmd/Ctrl + M` | Toggle voice capture |
| `Cmd/Ctrl + B` | Toggle sidebar |
| `Cmd/Ctrl + N` | New conversation |
| `Esc` | Close overlay / exit voice |
| Up, Down, Enter | Navigate and run Command Center results |

## Architecture

```
src/
├── App.tsx                      # Shell: background, boot sequence, router, toasts
├── components/
│   ├── AIOrb.tsx                # Layered AI Core — geometry, rings, particles, bars
│   ├── AmbientBackground.tsx    # Atmospheric light, grain, grid, ParticleField
│   ├── BootSequence.tsx         # Intro: light → core → ring → identity → reveal
│   ├── Message.tsx / MessageBlocks.tsx   # Rich response rendering
│   ├── CommandBar.tsx           # Glass input: voice, attach, tools, model, send
│   ├── CommandCenter.tsx        # Cmd/Ctrl-K overlay
│   ├── ModeSelector.tsx         # Seven intelligence modes
│   ├── Primitives.tsx           # GlassCard, Button (magnetic), StatusPill, …
│   └── Sidebar.tsx, TopNavigation.tsx, SettingsPanel.tsx
├── features/
│   ├── LandingHero.tsx          # Hero, modes, workstreams
│   ├── ChatInterface.tsx        # Conversation workspace
│   ├── VoiceInterface.tsx       # Voice session state machine
│   ├── IntelligenceDashboard.tsx
│   └── SystemSurfaces.tsx       # Knowledge, Tools, Memory, Projects
├── state/AppContext.tsx         # Single app state layer and orchestration
├── data/mock.ts                 # Modes, tools, conversations, projects, metrics
├── lib/engine.ts                # Deterministic response synthesis and streaming
├── lib/utils.ts                 # cx, rgba, seeded RNG, motion helpers
└── styles/globals.css           # Design tokens, glass utilities, grain, scrollbars
```

### Design system

Tokens live in `tailwind.config.ts` and `globals.css`: an obsidian-to-titanium
neutral ramp, platinum text tiers, a restrained champagne accent, and a soft
electric-blue aura that shifts per intelligence mode. Depth comes from layered
glass surfaces, inset highlights, and ambient radial light rather than heavy
borders or saturated gradients.

## Accessibility

- Full keyboard operability, including the Command Center and a skip link
- Visible focus rings; semantic landmarks and ARIA labelling on controls
- `prefers-reduced-motion` respected, plus an in-app motion toggle
- Live regions for toasts and streaming state

## Notes

Responses are generated locally from the prompt by `src/lib/engine.ts`.
Exchanging the simulator for a real model means replacing that one module — the
state layer and every view consume its streaming interface unchanged.