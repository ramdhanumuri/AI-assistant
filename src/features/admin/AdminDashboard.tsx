/* Administrator dashboard.

   Every panel here is backed by an endpoint behind `require_admin`, so a
   normal user who somehow reaches this route gets 403s rather than data. The
   role controls in the accounts table call the same guarded endpoint; the
   server re-checks the caller's stored role on every request and refuses
   self-demotion. */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Activity,
  Cpu,
  Database,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { adminApi, errorMessage } from '@/lib/api';
import type {
  AdminAIUsage,
  AdminEvent,
  AdminPage,
  AdminSystemHealth,
  AdminUsage,
  AdminUser,
} from '@/lib/authTypes';
import { useAuth } from '@/state/AuthContext';
import { Button, GlassCard } from '@/components/Primitives';
import { Field, FormAlert } from '@/components/AuthPrimitives';
import { cx, formatRelative } from '@/lib/utils';

const PAGE_SIZE = 20;

export function AdminDashboard() {
  const { user } = useAuth();

  return (
    <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-6 px-5 py-8 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">Administration</div>
          <h1 className="mt-2 text-[clamp(1.5rem,3.4vw,2rem)] font-extralight tracking-[-0.03em] gradient-platinum">
            Platform overview
          </h1>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-champagne/20 bg-champagne/[0.05] px-3.5 py-2">
          <ShieldCheck className="h-3.5 w-3.5 text-champagne" />
          <span className="font-mono text-3xs uppercase tracking-widest2 text-champagne">
            {user?.email ?? 'administrator'}
          </span>
        </div>
      </header>

      <UsagePanel />
      <AIUsagePanel />
      <SystemHealthPanel />
      <AccountsPanel />
      <EventFeedPanel />
    </div>
  );
}

/* ── Usage ────────────────────────────────────────────────────────── */

function UsagePanel() {
  const [usage, setUsage] = useState<AdminUsage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setUsage(await adminApi.usage());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const tiles = useMemo(
    () =>
      usage
        ? [
            { label: 'Accounts', value: usage.totalUsers },
            { label: 'Active', value: usage.activeUsers },
            { label: 'Admins', value: usage.adminUsers },
            { label: 'New · 7d', value: usage.newUsers7D },
            { label: 'Conversations', value: usage.totalConversations },
            { label: 'Messages', value: usage.totalMessages },
            { label: 'Live sessions', value: usage.activeSessions },
            { label: 'Auth events · 24h', value: usage.authEvents24H },
            { label: 'Failed logins · 24h', value: usage.failedLogins24H },
          ]
        : [],
    [usage],
  );

  return (
    <GlassCard className="p-6" interactive>
      <PanelHeading
        icon={<Activity className="h-3.5 w-3.5" />}
        title="Usage"
        onRefresh={load}
      />

      {error && (
        <div className="mt-5">
          <FormAlert tone="error">{error}</FormAlert>
        </div>
      )}

      {!usage && !error && <Loading label="Loading usage…" />}

      {usage && (
        <>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-3">
            {tiles.map((tile) => (
              <motion.div
                key={tile.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3.5"
              >
                <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                  {tile.label}
                </div>
                <div className="mt-1.5 text-[1.35rem] font-extralight text-platinum">
                  {tile.value.toLocaleString()}
                </div>
              </motion.div>
            ))}
          </div>

          {usage.usage.length > 0 && (
            <div className="mt-6">
              <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                Weekly series
              </div>
              <div className="mt-3 flex h-24 items-end gap-2">
                {usage.usage.map((bucket) => {
                  const max = Math.max(...usage.usage.map((b) => b.value), 1);
                  return (
                    <div key={bucket.label} className="flex flex-1 flex-col items-center gap-2">
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${Math.max(4, (bucket.value / max) * 100)}%` }}
                        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                        className="w-full rounded-t bg-gradient-to-t from-champagne/20 to-champagne/70"
                        title={`${bucket.label}: ${bucket.value}`}
                      />
                      <span className="font-mono text-3xs text-platinum-dim">
                        {bucket.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </GlassCard>
  );
}

/* ── AI usage (STEP 6) ───────────────────────────────────────────── */

function AIUsagePanel() {
  const [data, setData] = useState<AdminAIUsage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await adminApi.aiUsage(30));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const summary = data?.summary;
  const tiles = useMemo(
    () =>
      summary
        ? [
            { label: 'AI requests · 30d', value: summary.totalRequests.toLocaleString() },
            { label: 'Completed', value: summary.completedRequests.toLocaleString() },
            { label: 'Failed', value: summary.failedRequests.toLocaleString() },
            { label: 'Cancelled', value: summary.cancelledRequests.toLocaleString() },
            {
              label: 'Tokens',
              /* `null` means no provider reported usage — never render it as 0. */
              value: summary.totalTokens == null ? '—' : summary.totalTokens.toLocaleString(),
            },
            {
              label: 'Avg latency',
              value:
                summary.averageLatencyMs == null
                  ? '—'
                  : `${(summary.averageLatencyMs / 1000).toFixed(1)}s`,
            },
          ]
        : [],
    [summary],
  );

  return (
    <GlassCard className="p-6" interactive>
      <PanelHeading
        icon={<Cpu className="h-3.5 w-3.5" />}
        title="AI usage"
        onRefresh={load}
      />

      {error && (
        <div className="mt-5">
          <FormAlert tone="error">{error}</FormAlert>
        </div>
      )}

      {!data && !error && <Loading label="Loading AI usage…" />}

      {data && (
        <>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {tiles.map((tile) => (
              <motion.div
                key={tile.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3.5"
              >
                <div className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                  {tile.label}
                </div>
                <div className="mt-1.5 text-[1.35rem] font-extralight text-platinum">
                  {tile.value}
                </div>
              </motion.div>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {Object.entries(data.providersByUse).map(([provider, count]) => (
              <span
                key={provider}
                className="rounded-full border border-white/[0.09] bg-white/[0.03] px-3 py-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim"
              >
                {provider} · {count}
              </span>
            ))}
            {Object.entries(data.modelsByUse).map(([model, count]) => (
              <span
                key={model}
                className="rounded-full border border-champagne/20 bg-champagne/[0.05] px-3 py-1 font-mono text-3xs uppercase tracking-widest2 text-champagne"
              >
                {model} · {count}
              </span>
            ))}
          </div>
          <p className="mt-4 text-[12px] leading-relaxed text-platinum-dim/70">
            Aggregate counts only. Conversation content is never included here.
          </p>
        </>
      )}
    </GlassCard>
  );
}

/* ── System health ────────────────────────────────────────────────── */

function SystemHealthPanel() {
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setHealth(await adminApi.systemHealth());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = health
    ? [
        ['Status', health.status],
        ['Environment', health.environment],
        ['Version', health.version],
        ['Database', `${health.database} · ${health.databaseDialect}`],
        ['Supabase', health.supabase],
        ['Model provider', health.aiProvider],
        ['Password hashing', health.passwordHashing],
        ['Auth secret', health.authSecretConfigured ? 'configured' : 'missing'],
        ['Cookies', `${health.cookieSamesite} · ${health.cookieSecure ? 'secure' : 'insecure'}`],
        ['Access token', `${health.accessTokenMinutes} min`],
        ['Refresh token', `${health.refreshTokenDays} d`],
        ['Mail delivery', health.mailConfigured ? 'configured' : 'unconfigured'],
      ]
    : [];

  return (
    <GlassCard className="p-6" interactive>
      <PanelHeading
        icon={<Database className="h-3.5 w-3.5" />}
        title="System health"
        onRefresh={load}
      />

      {error && (
        <div className="mt-5">
          <FormAlert tone="error">{error}</FormAlert>
        </div>
      )}

      {!health && !error && <Loading label="Loading health…" />}

      {health && (
        <dl className="mt-5 grid grid-cols-1 gap-x-8 gap-y-2.5 sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div
              key={label}
              className="flex items-baseline justify-between gap-4 border-b border-white/[0.05] pb-2"
            >
              <dt className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                {label}
              </dt>
              <dd className="truncate text-right text-[12.5px] text-platinum-soft">{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </GlassCard>
  );
}

/* ── Accounts ─────────────────────────────────────────────────────── */

function AccountsPanel() {
  const { user: me } = useAuth();
  const [page, setPage] = useState<AdminPage<AdminUser> | null>(null);
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPage(await adminApi.users({ search: search || undefined, limit: PAGE_SIZE, offset }));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [search, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  const mutate = async (id: string, patch: { role?: string; isActive?: boolean }, label: string) => {
    setBusyId(id);
    setNotice(null);
    setError(null);
    try {
      await adminApi.updateUser(id, patch);
      await load();
      setNotice(label);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const total = page?.total ?? 0;
  const shown = page?.items.length ?? 0;

  return (
    <GlassCard className="p-6" interactive>
      <PanelHeading icon={<Users className="h-3.5 w-3.5" />} title="Accounts" onRefresh={load} />

      <div className="mt-5 flex flex-col gap-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-platinum-dim" />
          <Field
            label="Search"
            placeholder="Name or email"
            value={search}
            className="pl-10"
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </div>

        {error && <FormAlert tone="error">{error}</FormAlert>}
        {notice && <FormAlert tone="success">{notice}</FormAlert>}

        {!page && !error && <Loading label="Loading accounts…" />}

        {page && (
          <>
            <div className="flex flex-col gap-2">
              {page.items.map((account) => {
                const isSelf = account.id === me?.id;
                return (
                  <div
                    key={account.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-[13.5px] text-platinum-soft">
                          {account.fullName}
                        </span>
                        {isSelf && (
                          <span className="font-mono text-3xs uppercase tracking-widest2 text-champagne">
                            You
                          </span>
                        )}
                        {!account.isActive && (
                          <span className="font-mono text-3xs uppercase tracking-widest2 text-rose-300/80">
                            Disabled
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 truncate font-mono text-3xs tracking-wider text-platinum-dim">
                        {account.email}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim/80">
                        <span>{account.role}</span>
                        <span>{account.activeSessions} session(s)</span>
                        <span>
                          {account.lastLoginAt
                            ? `last login ${formatRelative(account.lastLoginAt)}`
                            : 'never signed in'}
                        </span>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      {busyId === account.id && (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-platinum-dim" />
                      )}
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={busyId === account.id}
                        onClick={() =>
                          mutate(
                            account.id,
                            { role: account.role === 'admin' ? 'user' : 'admin' },
                            `${account.fullName} is now ${
                              account.role === 'admin' ? 'a standard user' : 'an administrator'
                            }.`,
                          )
                        }
                      >
                        {account.role === 'admin' ? 'Revoke admin' : 'Make admin'}
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={busyId === account.id || isSelf}
                        title={isSelf ? 'You cannot deactivate your own account.' : undefined}
                        onClick={() =>
                          mutate(
                            account.id,
                            { isActive: !account.isActive },
                            `${account.fullName} is now ${
                              account.isActive ? 'disabled' : 'active'
                            }.`,
                          )
                        }
                      >
                        {account.isActive ? 'Disable' : 'Enable'}
                      </Button>
                    </div>
                  </div>
                );
              })}

              {shown === 0 && (
                <p className="py-4 text-center text-[13px] text-platinum-dim">
                  No accounts match that search.
                </p>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-white/[0.06] pt-4">
              <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                {shown === 0 ? 0 : offset + 1}–{offset + shown} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset((o) => o + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </GlassCard>
  );
}

/* ── Auth event feed ──────────────────────────────────────────────── */

const OUTCOME_TONE: Record<string, string> = {
  success: 'text-emerald-300/90',
  failure: 'text-rose-300/90',
  denied: 'text-champagne',
};

function EventFeedPanel() {
  const [events, setEvents] = useState<AdminEvent[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const feed = await adminApi.events({ limit: 25 });
      setEvents(feed.items);
      setCounts(feed.countsByType);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <GlassCard className="p-6" interactive>
      <PanelHeading
        icon={<ShieldCheck className="h-3.5 w-3.5" />}
        title="Authentication events"
        onRefresh={load}
      />

      <div className="mt-5 flex flex-col gap-4">
        {error && <FormAlert tone="error">{error}</FormAlert>}
        {!events && !error && <Loading label="Loading events…" />}

        {events && (
          <>
            {Object.keys(counts).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(counts).map(([type, count]) => (
                  <span
                    key={type}
                    className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim"
                  >
                    {type} · {count}
                  </span>
                ))}
              </div>
            )}

            <div className="flex flex-col">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between gap-4 border-b border-white/[0.05] py-2.5 last:border-0"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-mono text-3xs uppercase tracking-widest2 text-platinum-soft">
                        {event.eventType}
                      </span>
                      <span
                        className={cx(
                          'font-mono text-3xs uppercase tracking-widest2',
                          OUTCOME_TONE[event.outcome] ?? 'text-platinum-dim',
                        )}
                      >
                        {event.outcome}
                      </span>
                    </div>
                    {event.detail && (
                      <div className="mt-0.5 truncate text-[11.5px] text-platinum-dim">
                        {event.detail}
                      </div>
                    )}
                  </div>
                  <span className="shrink-0 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                    {formatRelative(event.occurredAt)}
                  </span>
                </div>
              ))}

              {events.length === 0 && (
                <p className="py-4 text-center text-[13px] text-platinum-dim">
                  No authentication events recorded.
                </p>
              )}
            </div>

            <p className="text-[11px] text-platinum-dim/70">
              Addresses and IPs are stored as one-way hashes; no passwords or tokens appear here.
            </p>
          </>
        )}
      </div>
    </GlassCard>
  );
}

/* ── Shared bits ──────────────────────────────────────────────────── */

function PanelHeading({
  icon,
  title,
  onRefresh,
}: {
  icon: React.ReactNode;
  title: string;
  onRefresh: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-2.5">
        <span className="text-champagne/80">{icon}</span>
        <h2 className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
          {title}
        </h2>
      </div>
      <Button type="button" variant="ghost" size="sm" onClick={onRefresh} aria-label={`Refresh ${title}`}>
        <RefreshCw className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

function Loading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2.5 py-4 text-[13px] text-platinum-dim">
      <Loader2 className="h-3.5 w-3.5 animate-spin" />
      {label}
    </div>
  );
}
