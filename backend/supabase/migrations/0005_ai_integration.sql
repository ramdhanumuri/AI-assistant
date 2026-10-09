-- AURELIS Intelligence API — AI integration (STEP 6).
-- Migration 0005. Mirrors Alembic revision 0003_ai_integration.
--
-- ── Why this is a separate file ───────────────────────────────────────────
-- 0001 and 0003 are already applied in deployed environments, so they are not
-- amended. This migration is additive and idempotent (`if not exists`), which
-- keeps it safe to re-run against a database that is already at 0004.
--
-- ── Scope ─────────────────────────────────────────────────────────────────
-- 1. The AI provenance columns on `messages`, so a turn can be recorded as
--    completed / failed / cancelled with the model and token counts that
--    produced it. Every column is nullable or defaulted, so existing rows stay
--    valid with no backfill.
-- 2. `ai_usage_events`, the append-only usage ledger.
--
-- No provider credential is stored anywhere in this migration, and no message
-- content is copied out of `messages` into the ledger.

-- ── messages: AI provenance ───────────────────────────────────────────────
-- `status` defaults to 'completed': every pre-STEP-6 row is, by definition, a
-- message that was written successfully.
alter table messages add column if not exists status         text not null default 'completed';
alter table messages add column if not exists model          text;
alter table messages add column if not exists provider       text;
alter table messages add column if not exists input_tokens   integer;
alter table messages add column if not exists output_tokens  integer;
alter table messages add column if not exists total_tokens   integer;
alter table messages add column if not exists latency_ms     integer;
alter table messages add column if not exists error_code     text;
alter table messages add column if not exists idempotency_key text;

create index if not exists ix_messages_idempotency_key on messages (idempotency_key);

-- ── ai_usage_events ───────────────────────────────────────────────────────
-- No foreign keys to users/conversations on purpose: a usage row is an
-- accounting fact and must outlive the conversation it describes, exactly as
-- `auth_events` outlives a deleted account.
create table if not exists ai_usage_events (
    id                     serial primary key,
    user_id                text,
    conversation_id        text,
    message_id             text,
    provider               text        not null,
    model                  text        not null,
    status                 text        not null,
    error_code             text,
    input_tokens           integer,
    output_tokens          integer,
    total_tokens           integer,
    latency_ms             integer,
    time_to_first_token_ms integer,
    estimated_cost         double precision,
    currency               text,
    pricing_version        text,
    request_started_at     timestamptz not null,
    request_completed_at   timestamptz,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);

create index if not exists ix_ai_usage_events_user_id         on ai_usage_events (user_id);
create index if not exists ix_ai_usage_events_conversation_id on ai_usage_events (conversation_id);
create index if not exists ix_ai_usage_events_provider        on ai_usage_events (provider);
create index if not exists ix_ai_usage_events_model           on ai_usage_events (model);
create index if not exists ix_ai_usage_events_status          on ai_usage_events (status);
create index if not exists ix_ai_usage_user_time              on ai_usage_events (user_id, request_started_at);
create index if not exists ix_ai_usage_status_time            on ai_usage_events (status, request_started_at);

-- ── Deny-by-default for the browser roles ─────────────────────────────────
-- The ledger is operator telemetry, not user data: it is read through the
-- backend's admin endpoints (which are role-gated in the application), never
-- over PostgREST. Enabling RLS with zero policies and no grant means the anon
-- and authenticated roles can neither read nor write it. 0002/0003 revoked the
-- blanket grants; re-asserted here so the posture survives a later grant.
alter table ai_usage_events enable row level security;

revoke all on ai_usage_events from anon, authenticated;

-- The policy shape that WOULD be required if this table were ever exposed to
-- browsers directly. Kept commented because it is deliberately not needed: the
-- backend connection is the table owner and is exempt from RLS.
--
--   create policy ai_usage_events_owner on ai_usage_events
--       for select to authenticated
--       using (user_id = auth.uid());
