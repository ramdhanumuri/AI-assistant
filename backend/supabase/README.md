# MODULE 3 — Supabase data layer

This module puts the AURELIS schema on Supabase and wires the FastAPI backend
to it. It is deliberately **non-breaking**: the app still runs on SQLite with
no Supabase configuration at all.

## What is authoritative

`backend/alembic/` remains the schema source of truth for the ORM. The files in
`supabase/migrations/` are the Postgres/Supabase expression of the same schema,
kept in lockstep and checked by `tests/test_supabase.py`.

| Concern | Owner |
| --- | --- |
| Runtime queries the API serves | SQLAlchemy over `DATABASE_URL` |
| Schema evolution (ORM + SQLite) | Alembic |
| Schema on Supabase / Postgres | `supabase/migrations/*.sql` |
| REST / Realtime / Storage | `app/db/supabase.py` seam |

## Migration rules

1. **Idempotent.** Every statement is `if not exists` / guarded, so replaying a
   file is safe and a partially-applied run can be retried.
2. **Tables first, dependencies second.** `create table` blocks carry no foreign
   keys; FKs, unique constraints and indexes are added afterwards so creation
   order never matters.
3. **Constraints are never inline.** `create table if not exists` skips the
   whole statement when the table already exists — including inline
   constraints — so a constraint written inline would silently fail to appear
   on a replay. They are added in guarded `do $$ ... $$` blocks instead.
4. **Never edit an applied migration.** Add a new numbered file.

## Applying the migrations

### Option A — Supabase SQL editor

1. Open **Dashboard → SQL Editor → New query**.
2. Paste the contents of `migrations/0001_core_schema.sql`, run it.
3. Paste the contents of `migrations/0002_rls_policies.sql`, run it.
4. Load the reference/demo data (see *Seeding* below).

### Option B — Supabase CLI

```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

### Option C — direct psql

```bash
export SUPABASE_DB_URL='postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres'
for f in migrations/0001_core_schema.sql migrations/0002_rls_policies.sql; do
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done
```

## Seeding

There is no `seed.sql` on purpose: the seed lives in `app/db/seed.py` and is
already the single source of truth. Duplicating ~780 lines of data into SQL
would create a second copy that silently drifts. Point the existing seeder at
the project instead:

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres'
.venv/bin/python -m app.db.seed
```

Seeding is idempotent — reference rows are upserted by primary key and content
rows are only inserted when absent — so re-running never clobbers work done
through the API.

Note: the seeder runs as the table owner, which `enable row level security`
leaves exempt, so RLS does not block it. This is a further reason not to switch
to `force row level security` before MODULE 4 provides a non-owner runtime role.


## Row Level Security

`0002_rls_policies.sql` **enables RLS on every table and writes no policies**,
apart from a public read policy on `ai_modes` (design tokens; no user data).

This is intentional, not an omission:

- With RLS off, Supabase exposes `public` over PostgREST to the `anon` and
  `authenticated` roles, so the public anon key would read and write every row.
- With RLS on and no policy, those roles see nothing. **Deny-by-default.**
- Writing real policies needs a notion of row ownership, which is MODULE 4's
  deliverable (identity). A placeholder rule would be wrong or would have to be
  torn out.

The migration also revokes the blanket `anon`/`authenticated` grants on the
`public` schema, so a future accidental `using (true)` policy is not the only
thing protecting the data.

`enable row level security` leaves the table owner exempt, which is what keeps
the backend's own connection and the Alembic path working. **Do not switch to
`force row level security`** until a dedicated non-owner runtime role exists, or
the API loses table access.

## Step 5 — per-user policies

`0004_rls_per_user_policies.sql` adds the positive per-user policies that
MODULE 4 deferred, now that ownership columns exist:

- `users`: a user selects/updates only their own row.
- `user_preferences`: owner-only via `user_id = auth.uid()`.
- `conversations`: `owner_id = auth.uid()`; NULL-owner demo rows match nobody.
- `messages`: ownership inherited from the conversation (`exists` subquery).
- `memory_records`: `owner_id = auth.uid()` (`owner_id` was reserved in MODULE 2).
- `auth_sessions`, `password_reset_tokens`, `auth_events`: explicitly revoked
  from `anon`/`authenticated` — these hold token digests and must stay
  server-only.

**Scope of these policies.** They key on `auth.uid()`, which PostgREST derives
from a *Supabase-issued* JWT. AURELIS issues its own sessions and does not mint
Supabase JWTs, so for the current SPA `auth.uid()` is null and every policy
denies — the correct deny-by-default posture, not a substitute for the
application layer's own ownership checks. They exist so a future
direct-to-PostgREST client cannot read another user's rows.

**Why no admin policy.** AURELIS has no Supabase `admin` role; inventing one
would duplicate the application's `role` column with a second source of truth.
Administrator reads are served by the backend, not PostgREST.

### RLS verification

The policies are static SQL; they are checked for PostgreSQL syntax and
coverage in `tests/test_supabase.py`. A full end-to-end verification against a
*hosted* Supabase project has not been run from this environment (no project
credentials and no Postgres server are available here) — see the Step 5
limitations. To verify against a non-production project:

1. Apply `0001`–`0004` in the SQL editor.
2. As the `anon` role, `select * from conversations` must return **zero** rows
   (denied), not an error and not another user's data.
3. With a Supabase JWT for user A, `select * from conversations` must return
   only A's rows; selecting a known B-owned id must return zero rows.
4. `select * from users` as `anon`/`authenticated` must be denied.
5. Confirm the service-role key is used only by the backend and is absent from
   every `VITE_`-prefixed variable and the built frontend bundle.

Never run these against a production project.

## Backend configuration

Copy `.env.example` to `.env` and fill in from **Dashboard → Project Settings**:

| Variable | Where it comes from | Notes |
| --- | --- | --- |
| `DATABASE_URL` | Database → Connection string (URI) | Use `postgresql+psycopg://`. Supabase's `postgres://` prefix must become `postgresql+psycopg://`. |
| `SUPABASE_URL` | API → Project URL | |
| `SUPABASE_ANON_KEY` | API → anon/public | Safe for browsers; respects RLS. |
| `SUPABASE_SERVICE_ROLE_KEY` | API → service_role | **Server only.** Bypasses RLS. Never in a `VITE_` variable or any client bundle. |

Connection pooling note: the transaction pooler (port `6543`) does not support
prepared statements. If you hit `prepared statement ... already exists`, either
use the session pooler on `5432` or disable server-side prepared statements for
the engine.

Verify the wiring:

```bash
curl localhost:12001/api/v1/health/ready   # -> "supabase": "ok"
curl localhost:12001/api/v1/system/info    # -> supabase.configured: true
```

## Monitoring

Nothing is provisioned by this module — no alerting, dashboards or exporters
were created, and none should be claimed as configured. What exists is the
hook a monitor attaches to:

| Signal | Source | Intended use |
| --- | --- | --- |
| Liveness | `GET /api/v1/health` | Process up. Never touches the database, so a DB blip cannot trigger a restart loop. |
| Readiness | `GET /api/v1/health/ready` | 503 when Postgres is unreachable. Gate traffic on this. Reports `supabase` for visibility only. |
| Supabase reachability | `supabase` field on readiness | `ok` / `unconfigured` / `unavailable`. |
| Structured logs | `app/core/logging.py` | JSON-ish stdout; ship to your log sink. |

For a real deployment, add the platform dashboards:

- **Supabase Dashboard → Reports**: database size, connections, API requests,
  and the Postgres logs. Supabase's built-in alerts cover disk and CPU only.
- **PITR / log drains**: Supabase Pro supports point-in-time recovery and log
  drains to a SIEM. Neither is enabled by this repo.

## Backup status

**No backup was configured or taken by this module.** Nothing here creates a
schedule, and no restore has ever been tested.

What Supabase provides and what you must decide:

| Plan | Backups |
| --- | --- |
| Free | None. Export manually (`supabase db dump`) or the data is unrecoverable. |
| Pro | Daily backups, 7-day retention, PITR available as a paid add-on. |
| Team / Enterprise | Longer retention; PITR available. |

Minimum for production:

```bash
supabase db dump --db-url "$SUPABASE_DB_URL" -f schema.sql
supabase db dump --db-url "$SUPABASE_DB_URL" --data-only -f data.sql
```

A backup that has never been restored is not a backup. Before trusting one,
restore it into a scratch project and confirm the row counts.

## Tests

```bash
cd backend
.venv/bin/python -m pytest -q
```

`tests/test_supabase.py` covers the seam and the migration files **without
needing a live Supabase project**:

- unconfigured / configured behaviour and the `rest_url` normalisation
- anon-by-default vs. opt-in service-role headers
- an unreachable host degrading to `unavailable` rather than raising
- `HealthResponse` / `SystemInfo` reporting the state without leaking secrets
- every ORM table present in `0001` and RLS-enabled in `0002`
- both migrations parsing under the **real PostgreSQL grammar** (via `pglast`)

The SQL is syntax-checked, but it has **not been executed against a Postgres
server** — no server or Docker daemon was available in the build environment.
Executing the migrations on the real project is the remaining verification step
listed below.
