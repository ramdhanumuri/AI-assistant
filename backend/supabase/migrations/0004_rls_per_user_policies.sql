-- AURELIS Intelligence API — per-user Row Level Security.
-- Migration 0004; follows the rules in ../README.md:
--   * idempotent (safe to replay)
--   * statements grouped, drop-then-create for policies
--
-- ── Why this migration exists ─────────────────────────────────────────────
-- Migrations 0002/0003 enabled RLS deny-by-default and revoked the blanket
-- grants Supabase gives `anon`/`authenticated`. This migration adds the
-- *positive* per-user policies MODULE 4 deferred, so that if a browser ever
-- talks to PostgREST directly with `auth.uid()`, ownership is enforced in the
-- database and not only in the API.
--
-- ── Why the API is unaffected ─────────────────────────────────────────────
-- Policies apply to the `anon` and `authenticated` roles. The FastAPI backend
-- connects as the table owner (`postgres`), which `enable row level security`
-- leaves exempt unless `force row level security` is set. We deliberately do
-- NOT force RLS here — the API remains the single writer and its own
-- ownership checks are the primary control. See supabase/README.md.
--
-- ── The identity a policy can key on ──────────────────────────────────────
-- Policies use `auth.uid()`, which PostgREST derives from a Supabase-issued
-- JWT. AURELIS issues its own sessions and does not mint Supabase JWTs, so
-- these policies are inert for the AURELIS SPA today: with no Supabase JWT,
-- `auth.uid()` is null and every policy denies. They are the correct posture
-- for a direct-to-PostgREST client and a safe default for one that never
-- arrives — not a substitute for the application layer's checks.

-- ── users ─────────────────────────────────────────────────────────────────
-- A user may read and update only their own row. Password digests, role and
-- active state are columns on that row, but column-level protection is a
-- separate concern (grants) — the API never exposes them, and this policy at
-- least prevents reading someone else's account.
drop policy if exists users_select_own on users;
create policy users_select_own on users
    for select to authenticated
    using (id = auth.uid());

drop policy if exists users_update_own on users;
create policy users_update_own on users
    for update to authenticated
    using (id = auth.uid())
    with check (id = auth.uid());

-- ── user_preferences ──────────────────────────────────────────────────────
drop policy if exists user_preferences_own on user_preferences;
create policy user_preferences_own on user_preferences
    for all to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- ── conversations ─────────────────────────────────────────────────────────
-- NULL owner rows (the MODULE 2 demo data) match no `auth.uid()`, so they stay
-- invisible — the same rule the API applies.
drop policy if exists conversations_owner on conversations;
create policy conversations_owner on conversations
    for all to authenticated
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

-- ── messages ──────────────────────────────────────────────────────────────
-- A message has no owner column; ownership is inherited from its conversation.
drop policy if exists messages_owner on messages;
create policy messages_owner on messages
    for all to authenticated
    using (
        exists (
            select 1 from conversations c
            where c.id = messages.conversation_id
              and c.owner_id = auth.uid()
        )
    )
    with check (
        exists (
            select 1 from conversations c
            where c.id = messages.conversation_id
              and c.owner_id = auth.uid()
        )
    );

-- ── memory_records ────────────────────────────────────────────────────────
-- `owner_id` was reserved for exactly this in MODULE 2, so these policies can
-- be written now without a schema change. NULL owner rows stay invisible.
drop policy if exists memory_records_owner on memory_records;
create policy memory_records_owner on memory_records
    for all to authenticated
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

-- ── sessions and reset tokens: never browser-readable ─────────────────────
-- These hold token digests. No policy grants `anon`/`authenticated` any access;
-- it is re-asserted here so the posture survives a future accidental grant.
-- (RLS was enabled on them in 0003; with zero policies and no grant, the
-- browser roles remain denied.)
revoke all on auth_sessions          from anon, authenticated;
revoke all on password_reset_tokens  from anon, authenticated;
revoke all on auth_events            from anon, authenticated;

-- ── Admin access ──────────────────────────────────────────────────────────
-- AURELIS has no Supabase `admin` role, and inventing one here would duplicate
-- the application's `role` column with a second source of truth. Admin reads
-- are served by the backend, not PostgREST, so no admin policy is defined.

-- ── Positive grants for the policies above ────────────────────────────────
-- 0002/0003 revoked everything; a policy without a grant still denies. Grant
-- only the verbs the policies cover.
grant select, update         on users              to authenticated;
grant select, insert, update, delete on user_preferences     to authenticated;
grant select, insert, update, delete on conversations        to authenticated;
grant select, insert, update, delete on messages             to authenticated;
grant select, insert, update, delete on memory_records       to authenticated;
