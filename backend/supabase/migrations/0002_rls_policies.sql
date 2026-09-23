-- AURELIS Intelligence API — Row Level Security.
-- Migration 0002.
--
-- ── Why RLS is enabled but has no policies yet ────────────────────────────
-- Supabase exposes the `public` schema over PostgREST to the `anon` and
-- `authenticated` roles. With RLS disabled, any holder of the public anon key
-- could read and write every row. Enabling RLS with zero policies is
-- deny-by-default: those roles see nothing and can write nothing.
--
-- Policies are intentionally NOT written here. A policy needs a notion of
-- "who owns this row", and identity is MODULE 4's deliverable. Inventing a
-- placeholder ownership rule now would either be wrong or would have to be
-- torn out. MODULE 4 adds the policies; see supabase/README.md for the exact
-- shape those policies are expected to take.
--
-- ── Why not FORCE ─────────────────────────────────────────────────────────
-- `enable row level security` (used below) leaves the table owner exempt, so
-- the backend's own Postgres connection and the Alembic migration path keep
-- working. `force row level security` would also subject the owner, and is the
-- correct hardening step once MODULE 4 introduces a dedicated non-owner
-- runtime role. Do not enable it before then, or the API loses table access.

alter table ai_modes          enable row level security;
alter table daily_usage       enable row level security;
alter table knowledge_sources enable row level security;
alter table memory_records    enable row level security;
alter table projects          enable row level security;
alter table tool_integrations enable row level security;
alter table activity_events   enable row level security;
alter table conversations     enable row level security;
alter table messages          enable row level security;

-- Defence in depth: strip the blanket grants Supabase applies to the public
-- schema so that even a future accidental `using (true)` policy is not the
-- only thing standing between the anon key and the data. MODULE 4 re-grants
-- only what its policies require.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;

-- ── Reference data is read-only and non-sensitive ─────────────────────────
-- ai_modes is design tokens (labels, colours) with no user data, so a public
-- read policy is safe and lets the frontend theme itself before login. The
-- write path stays owner-only.
drop policy if exists ai_modes_public_read on ai_modes;
create policy ai_modes_public_read on ai_modes
    for select
    to anon, authenticated
    using (true);

grant select on ai_modes to anon, authenticated;

-- ── Template for MODULE 4 (commented — do not enable early) ──────────────
-- Once users exist, per-user tables need an ownership column and policies of
-- this shape. conversations/messages have no owner column yet, which is
-- exactly why they cannot be exposed today.
--
--   alter table conversations add column owner_id uuid references auth.users (id);
--   create policy conversations_owner on conversations
--       for all to authenticated
--       using (owner_id = auth.uid())
--       with check (owner_id = auth.uid());
