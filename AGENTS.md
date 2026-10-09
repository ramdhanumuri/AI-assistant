# AGENTS.md

## Project

AURELIS — a premium dark-luxury AI assistant. React 18 + TypeScript + Vite 5 +
Tailwind + Framer Motion + Lucide on the frontend; FastAPI on the backend. The
backend talks to a real model through a provider abstraction (STEP 6); the
default `simulator` provider is deterministic and exists so tests stay hermetic.

## Commands

```bash
npm run dev        # vite on 0.0.0.0:12000 (proxy host)
npm run build      # tsc --noEmit && vite build
npm run typecheck  # tsc --noEmit
```

Always typecheck before considering work done. `npm run build` runs it too.

## Backend (MODULE 2) - `backend/`

FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 + SQLite. The frontend's
`src/lib/engine.ts` simulator is untouched; chat turns go through
`app/ai/providers/` instead. Port 12001.

```bash
cd backend
python run.py                  # uvicorn on 0.0.0.0:12001, reload on
alembic upgrade head           # create the schema
python -m app.db.seed          # load reference + demo data
pytest                         # 426 tests
```

## AI integration (STEP 6) - `backend/app/ai/`

A provider-independent layer. `AIProvider` (`base.py`) exposes `generate()` /
`stream()`; `factory.py` resolves the adapter from `AI_PROVIDER`. Only the
OpenAI adapter and the `simulator` are implemented, but nothing outside
`providers/` knows a vendor's SDK — swapping providers is a new adapter plus
config, not a chat rewrite.

- **The provider key is backend-only.** It lives in `AI_PROVIDER_API_KEY` and
  must never reach a `VITE_*` variable, `/api/auth/me`, capabilities, admin
  responses or logs.
- **Validation ordering on the stream endpoint is deliberate.** Auth, CSRF,
  rate limit, conversation ownership, the model allow-list and provider config
  are all checked *before* `200 OK` and the SSE headers go out; once the stream
  starts there is no way to send a 404 or 429, so only mid-generation failures
  appear as in-band `error` frames.
- **Ownership is server-derived.** The owner id comes from the session, never
  from the client; another user's conversation ids 404 rather than 403, so
  existence does not leak.
- **Context is budgeted, not unbounded.** `context.py` caps the replay by
  `AI_MAX_CONTEXT_MESSAGES` / `AI_MAX_INPUT_TOKENS` while always keeping the
  system instructions and the current user turn.
- **Stream state is honest.** A disconnect or provider failure records
  `status` of `cancelled`/`failed` with `error_code` and keeps partial text; a
  turn is never marked `completed` unless it actually finished.
- **Token counts are only stored when the provider reports them** — `NULL`
  rather than an invented number. Cost stays zero unless real pricing is
  configured.
- **Rate limiting uses the `ai` scope** (`app/core/ratelimit.py`), separate from
  the ordinary write budget.
- **`NoDecode` is required on list-valued settings** (`CORS_ORIGINS`,
  `AI_ALLOWED_MODELS`). pydantic-settings JSON-decodes `list[str]` env values
  before field validators run, so without it the documented `a,b` form fails at
  boot.

## Security (STEP 5) - `backend/SECURITY.md` is the reference

Defence in depth on top of Step 4 auth. Read `backend/SECURITY.md` before
changing anything on the auth/transport path. The pieces that are easy to get
wrong:

- **Middleware order is load-bearing.** In `main.py`, add innermost first;
  Starlette makes the last-added outermost. Order is CORS → security headers →
  request context. CORS must stay outermost so a rejected response (413, 401,
  preflight) still carries CORS headers; security headers sit outside the
  request-context 413 so that refusal is decorated too.
- **Request ids.** `X-Request-ID` is echoed from the client only when short and
  `[A-Za-z0-9._-]`; otherwise server-generated. It lives in a `ContextVar`
  (`app/core/request_context.py`) so exception handlers and the security logger
  pick it up. Never put tokens in URLs.
- **Rate limiting is per-scope** (`app/core/ratelimit.py`). Auth scopes share
  `AUTH_RATE_LIMIT_ATTEMPTS`; `ai`/`write`/`admin`/... have their own budgets.
  Set `REDIS_URL` for shared state across workers; without it the in-process
  limiter gives each worker its own budget. Redis failure fails **open**.
- **Generic auth responses are deliberate.** Unknown email, wrong password,
  inactive account and lockout must look identical (or leak existence). Do not
  add "account locked" wording; a lockout is a 429 with the throttle's exact text.
- **Security events** are one closed vocabulary (`EVENT_TYPES` in
  `app/models/user.py`). Never log passwords, raw tokens, reset links or full
  bodies; `log_security_event` collapses whitespace to stop log injection.
- **Errors.** Validation responses drop Pydantic's `input`/`url` (they echo
  submitted secrets). Unexpected exceptions are generic 500s; detail is logged.
- **Config refuses to boot** outside development on a weak `AUTH_SECRET`,
  `DEBUG=true`, wildcard CORS, `COOKIE_SECURE=false`, or a plaintext public URL.
- **Uploads** (`app/core/uploads.py`) are validated and stored under a
  server-generated name; raw filenames never become path segments. Disabled
  unless `UPLOAD_STORAGE_DIR` is set.

### API contract - read before touching schemas

`src/types.ts` is authoritative; the backend adapts to the frontend, never the
reverse. Two rules that are easy to get wrong:

- **Timestamps the UI does arithmetic on are epoch milliseconds** (`updatedAt`,
  `lastMessageAt`, `createdAt`, ...), not ISO strings. `formatRelative(ts: number)`
  renders `NaN` against a string.
- **Three fields the UI prints verbatim are pre-formatted relative strings**
  (`activity.at`, `knowledge.updated`, `memory.learned`). The columns behind them
  stay real datetimes and the wording is derived on read - see `_relative_label`
  in `backend/app/schemas/common.py`. Do not store "4 min ago".

Request bodies accept both spellings (`mode`/`modeId`, `project`/`projectId`) via
`AliasChoices`, so existing frontend calls keep working; responses emit the
frontend's name only. `backend/tests/test_contract.py` freezes all of this - a
rename there is a deliberate, tested change, not a refactor.

`alembic/versions/0001` is only safe to amend while the schema is unreleased.
Once something depends on it, add a new migration instead. Drift is checked in
`backend/tests/test_migrations.py`.

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