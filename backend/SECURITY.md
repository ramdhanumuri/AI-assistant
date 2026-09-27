# Security model

The reference for what protects the API, what the defaults are, and what a
deployment must configure. It covers the layers added in Step 5 on top of the
Step 4 authentication foundation.

## Defence in depth

```
Internet
  │  HTTPS / TLS                     (deployment; HSTS emitted when cookie-secure)
  ▼
Security headers                    app/core/security_headers.py
  │  CORS (explicit origins)        app/main.py
  ▼
Rate limiting (per scope)           app/core/ratelimit.py
  │  Body-size guard + request id   app/core/request_context.py
  ▼
Request validation (Pydantic)       app/api/v1/*, app/schemas/*
  │
Authentication (JWT + cookies)      app/services/auth.py, app/api/deps.py
  │
Authorization (role + ownership)    app/api/deps.py, repositories
  │
CSRF (double-submit)                app/api/cookies.py
  │
Application services
  ▼
Database (SQLAlchemy, parameterised) → PostgreSQL / Supabase (RLS)
```

## Request correlation

Every response carries `X-Request-ID`. A client may suggest an id, but it is
echoed only when it is ≤128 characters and matches `[A-Za-z0-9._-]`; otherwise a
server-generated id is used. The id is placed in a `ContextVar` so exception
handlers and the security-event logger append it to their log lines.

## Rate limiting

Sliding window, per scope. With `REDIS_URL` set the counters live in Redis so all
workers share one budget; without it an in-process limiter is used (correct for a
single worker, per-worker budgets for several — an attacker gains N× with N
workers).

| Scope | Budget | Window | Notes |
| --- | --- | --- | --- |
| `login`, `register`, `refresh`, `password-reset` | `AUTH_RATE_LIMIT_ATTEMPTS` (10) | `AUTH_RATE_LIMIT_WINDOW_SECONDS` (300) | keyed on client address |
| `ai` | 60 | 60 | per authenticated user (message turns) |
| `write` | 120 | 60 | per authenticated user (create conversation/project/memory) |
| `search` | 120 | 60 | reserved |
| `admin` | 240 | 60 | per administrator |
| `upload` | 20 | 3600 | reserved for Step 8 |

Redis failure fails open (logged) so a cache outage cannot take authentication
down. A shared store is the recommended production posture.

## Brute-force protection

Layered, and deliberately not a permanent lock:

1. Address throttle (above), per auth scope.
2. Per-account failed-login counter. At `AUTH_MAX_FAILED_LOGINS` (10) the account
   is locked for `AUTH_LOCKOUT_SECONDS` (900). The counter clears on success and
   the lock expires on its own.
3. Sustained attempts against a locked account escalate to a
   `suspicious_activity` event every `AUTH_MAX_FAILED_LOGINS` further tries.

The lock and throttle responses are byte-identical (`429`, "Too many attempts.
Try again shortly.") so an attacker cannot distinguish "rate limited" from
"account locked", and unknown-email, wrong-password and inactive-account all
return the same `401`. Password verification for an unknown account runs against
a dummy hash so response latency does not disclose existence.

## Sessions and refresh tokens

- Access token: short-lived signed JWT (`ACCESS_TOKEN_EXPIRE_MINUTES`), carries
  the session id, in an HttpOnly cookie (or `Authorization: Bearer` for API
  clients).
- Refresh token: opaque, stored only as a SHA-256 digest. Rotation replaces it on
  every refresh; the old digest is marked used.
- **Reuse detection**: presenting an already-rotated token revokes every session
  for the account, records `token_reuse_detected`, and forces fresh
  authentication.
- Logout, password change and deactivation revoke server-side, effective on the
  next request rather than at token expiry.

## Cookies

| Cookie | HttpOnly | Secure | SameSite | Purpose |
| --- | --- | --- | --- | --- |
| `aurelis_session` | yes | outside dev | `COOKIE_SAMESITE` (lax) | access token |
| `aurelis_refresh` | yes | outside dev | same | refresh token |
| `aurelis_csrf` | no (by design) | same | same | double-submit value; no credential |

Tokens never appear in a URL.

## CSRF

Double-submit: the CSRF cookie value must equal the `X-CSRF-Token` header on
`POST`/`PUT`/`PATCH`/`DELETE`. Safely-method requests are exempt. A bearer client
with no cookies is exempt because nothing attaches its credential automatically.
Missing and mismatched tokens produce the same `403`, and the presented token is
never echoed.

## Security headers

Applied to every response. The API policy is `default-src 'none'; script-src
'none'; …; frame-ancestors 'none'` — an API response cannot become a script.
Interactive docs (`/docs`, `/redoc`) get a scoped policy that permits
`cdn.jsdelivr.net`. `Strict-Transport-Security` is emitted only when cookies are
secure (i.e. over HTTPS). Auth responses add `Cache-Control: no-store`.

## Errors

Clients receive `{"error": {"code", "message"}}`. Validation errors carry
`type`/`loc`/`msg` per field but **not** the submitted `input` (which could echo
a password or token) or `url`. Unexpected exceptions return a generic 500; the
detail is logged server-side and tied to the response by `X-Request-ID`.

## Security events

Emitted as structured log lines via `app/core/security_events.py` and persisted
(in service code) to `auth_events` for the admin feed. Vocabulary lives in one
place (`EVENT_TYPES`). Events carry a keyed subject digest, coarse client
metadata and request id — never passwords, raw tokens, reset links or full
request bodies. The free-text detail is length-capped and whitespace-collapsed to
prevent log injection.

## File uploads (Step 8 foundation)

`app/core/uploads.py` validates size, extension and MIME, and mints a
server-generated stored name (uuid + allowed extension), so a client filename
never becomes a path segment. `resolve_storage_path` re-checks the resolved path
is inside the storage root. Uploads are disabled unless `UPLOAD_STORAGE_DIR` is
set. Regexes and traversal tests cover `../`, `..\`, encoded forms, control
characters and Windows device names.

## Database

All queries use SQLAlchemy ORM/Core with bound parameters; no string-built SQL.
Row Level Security is enabled on every table (deny-by-default) with per-user
policies in `supabase/migrations/0004_rls_per_user_policies.sql`. The FastAPI
backend connects as the table owner and is the sole writer; RLS policies key on
Supabase `auth.uid()` and are the posture for a future direct-to-PostgREST
client. See `supabase/README.md`.

## Deployment requirements

A production deployment must set, at minimum:

- `APP_ENV` to a non-development value.
- `AUTH_SECRET` to ≥32 random bytes (the app refuses placeholders and short keys).
- `COOKIE_SECURE=true`; `COOKIE_SAMESITE=lax` or `none` (none requires secure).
- `CORS_ORIGINS` to the explicit list of trusted origins (no `*`).
- `DEBUG=false`.
- `DATABASE_URL` a PostgreSQL/Supabase URL.
- `REDIS_URL` for a multi-worker deployment (shared rate-limit state).
- HTTPS termination in front of the app; optionally `ENABLE_API_DOCS=false`
  (already the default outside development).

The startup validators reject a debug/traceback config, a wildcard CORS origin
with credentials, a plaintext public URL, and SameSite=None without Secure.

## Known limitations

- **Supabase RLS was not verified against a live project** from this environment
  (no credentials, no Postgres server). The policies are syntax-checked and
  coverage-tested; see `supabase/README.md` for the non-production verification
  procedure.
- **Redis is not a dependency of the base image.** Distributed limiting requires
  installing the `redis` package and setting `REDIS_URL`; until then the
  in-process limiter is in force and `active_backend()` reports it.
- **MFA and email verification are architecture-only.** They are not implemented;
  `email_verified_at` / verification-token tables are not created, and password
  reset uses the Step 4 stub (no email is delivered).
- **AI provider integration is Step 6.** No provider key handling exists yet;
  rate limits, body-size limits and timeout/error handling are the foundation.
- **File uploads have no route yet** (Step 8); only the validator exists.
