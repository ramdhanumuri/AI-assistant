/* Profile and security settings for the signed-in user.

   Two things this screen deliberately cannot do:

   * Change the account's role. The update request carries only `fullName` /
     `avatarUrl`, and the backend schema is `extra="forbid"`, so a smuggled
     `role` is rejected outright rather than silently ignored.
   * Read or display anything token-shaped. Sessions are listed by id, agent
     and timestamps only. */

import { useEffect, useState, type FormEvent } from 'react';
import { motion } from 'framer-motion';
import {
  CheckCircle2,
  Clock,
  KeyRound,
  Loader2,
  MonitorSmartphone,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { useAuth } from '@/state/AuthContext';
import { ApiError, authApi, errorMessage } from '@/lib/api';
import type { AuthSession } from '@/lib/authTypes';
import { Button, GlassCard } from '@/components/Primitives';
import { Field, FormAlert, PasswordChecklist, isStrongPassword } from '@/components/AuthPrimitives';
import { cx, formatRelative } from '@/lib/utils';

export function ProfileScreen() {
  const { user, updateProfile, reload } = useAuth();

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col gap-6 px-5 py-8 lg:px-8">
      <header>
        <div className="eyebrow">Account</div>
        <h1 className="mt-2 text-[clamp(1.5rem,3.4vw,2rem)] font-extralight tracking-[-0.03em] gradient-platinum">
          Profile & security
        </h1>
      </header>

      <IdentityCard
        fullName={user?.fullName ?? ''}
        email={user?.email ?? ''}
        role={user?.role ?? 'user'}
        onSave={updateProfile}
      />

      <ChangePasswordCard onChanged={reload} />

      <SessionsCard />
    </div>
  );
}

/* ── Identity ─────────────────────────────────────────────────────── */

function IdentityCard({
  fullName,
  email,
  role,
  onSave,
}: {
  fullName: string;
  email: string;
  role: string;
  onSave: (patch: { fullName?: string }) => Promise<void>;
}) {
  const [name, setName] = useState(fullName);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => setName(fullName), [fullName]);

  const dirty = name.trim() !== fullName && name.trim().length > 0;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!dirty || saving) return;
    if (!name.trim()) {
      setError('Your name cannot be empty.');
      return;
    }

    setError(null);
    setSaving(true);
    try {
      /* Only the name is sent. Role and password live on separate, guarded
         endpoints and are not reachable from a profile update. */
      await onSave({ fullName: name.trim() });
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2600);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <GlassCard className="p-6" interactive>
      <SectionHeading icon={<UserRound className="h-3.5 w-3.5" />} title="Identity" />

      <form onSubmit={onSubmit} noValidate className="mt-5 flex flex-col gap-4">
        {error && <FormAlert tone="error">{error}</FormAlert>}
        {saved && <FormAlert tone="success">Profile updated.</FormAlert>}

        <Field
          label="Full name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
        />

        <div className="flex flex-col gap-2">
          <label className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
            Email
          </label>
          <div className="flex h-12 items-center rounded-xl border border-white/[0.06] bg-white/[0.015] px-4 text-[14px] text-platinum-dim">
            {email}
          </div>
          <p className="text-[11.5px] text-platinum-dim/80">
            Email changes require re-verification and are not available here.
          </p>
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-white/[0.06] pt-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5 text-champagne/80" />
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
              Role: {role} · server-assigned
            </span>
          </div>
          <Button type="submit" size="sm" disabled={!dirty || saving} aria-busy={saving}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Save'}
          </Button>
        </div>
      </form>
    </GlassCard>
  );
}

/* ── Change password ──────────────────────────────────────────────── */

function ChangePasswordCard({ onChanged }: { onChanged: () => Promise<void> }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (saving) return;

    const found: Record<string, string | undefined> = {};
    if (!current) found.current = 'Enter your current password.';
    if (!next) found.next = 'Choose a new password.';
    else if (!isStrongPassword(next)) found.next = 'Password does not meet the requirements.';
    else if (next === current) found.next = 'New password must differ from the current one.';
    if (!confirm) found.confirm = 'Confirm your new password.';
    else if (confirm !== next) found.confirm = 'Passwords do not match.';

    setErrors(found);
    setFormError(null);
    setDone(null);
    if (Object.keys(found).length) return;

    setSaving(true);
    try {
      const result = await authApi.changePassword({
        currentPassword: current,
        newPassword: next,
        confirmPassword: confirm,
      });
      setDone(result.message);
      setCurrent('');
      setNext('');
      setConfirm('');
      /* The change revokes every other session, so re-read the identity to
         confirm the current one survived. */
      await onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.kind === 'unauthorized') {
        setErrors({ current: err.message });
      } else {
        setFormError(errorMessage(err));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <GlassCard className="p-6" interactive>
      <SectionHeading icon={<KeyRound className="h-3.5 w-3.5" />} title="Password" />

      <form onSubmit={onSubmit} noValidate className="mt-5 flex flex-col gap-4">
        {formError && <FormAlert tone="error">{formError}</FormAlert>}
        {done && (
          <FormAlert tone="success">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {done} Other sessions have been signed out.
            </span>
          </FormAlert>
        )}

        <Field
          label="Current password"
          autoComplete="current-password"
          reveal
          value={current}
          error={errors.current}
          onChange={(e) => setCurrent(e.target.value)}
        />

        <div>
          <Field
            label="New password"
            autoComplete="new-password"
            reveal
            value={next}
            error={errors.next}
            onChange={(e) => setNext(e.target.value)}
          />
          <PasswordChecklist password={next} />
        </div>

        <Field
          label="Confirm new password"
          autoComplete="new-password"
          reveal
          value={confirm}
          error={errors.confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />

        <div className="flex justify-end border-t border-white/[0.06] pt-4">
          <Button type="submit" size="sm" disabled={saving} aria-busy={saving}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Update password'}
          </Button>
        </div>
      </form>
    </GlassCard>
  );
}

/* ── Sessions ─────────────────────────────────────────────────────── */

function SessionsCard() {
  const [sessions, setSessions] = useState<AuthSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState(false);

  const load = async () => {
    try {
      setSessions(await authApi.sessions());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const revokeAll = async () => {
    setRevoking(true);
    try {
      await authApi.revokeAllSessions();
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRevoking(false);
    }
  };

  return (
    <GlassCard className="p-6" interactive>
      <SectionHeading
        icon={<MonitorSmartphone className="h-3.5 w-3.5" />}
        title="Active sessions"
      />

      <div className="mt-5 flex flex-col gap-3">
        {error && <FormAlert tone="error">{error}</FormAlert>}

        {sessions === null && !error && (
          <p className="text-[13px] text-platinum-dim">Loading sessions…</p>
        )}

        {sessions?.length === 0 && (
          <p className="text-[13px] text-platinum-dim">No active sessions recorded.</p>
        )}

        {sessions?.map((session) => (
          <motion.div
            key={session.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={cx(
              'flex items-center justify-between gap-4 rounded-xl border px-4 py-3',
              session.current
                ? 'border-champagne/25 bg-champagne/[0.05]'
                : 'border-white/[0.07] bg-white/[0.02]',
            )}
          >
            <div className="min-w-0">
              <div className="truncate text-[13px] text-platinum-soft">
                {session.userAgent ?? 'Unknown client'}
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">
                <Clock className="h-2.5 w-2.5" />
                {session.lastUsedAt
                  ? `used ${formatRelative(session.lastUsedAt)}`
                  : `started ${formatRelative(session.createdAt)}`}
              </div>
            </div>
            {session.current && (
              <span className="shrink-0 font-mono text-3xs uppercase tracking-widest2 text-champagne">
                This device
              </span>
            )}
          </motion.div>
        ))}

        <div className="flex justify-end border-t border-white/[0.06] pt-4">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={revokeAll}
            disabled={revoking || !sessions?.length}
            aria-busy={revoking}
          >
            {revoking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Sign out everywhere'}
          </Button>
        </div>
      </div>
    </GlassCard>
  );
}

function SectionHeading({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="text-champagne/80">{icon}</span>
      <h2 className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim">{title}</h2>
    </div>
  );
}
