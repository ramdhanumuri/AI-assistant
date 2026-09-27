/* Password-reset foundation.

   The backend issues a single-use, short-lived token and never returns it in
   the response body — it hands it to the mailer. Until a mail provider is
   configured (`MAIL_*`), `delivery` comes back as "unconfigured" and the token
   is only recorded server-side.

   So this screen is honest about that: it confirms the request in the same
   words regardless of whether the address exists (the backend's response is
   identical, deliberately), and when delivery is unconfigured it tells the
   operator where the token went instead of pretending an email was sent.

   `/reset-password#token=…` is the link target the mailer emits. The fragment
   keeps the token out of the request line, so it never reaches server access
   logs. */

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, CheckCircle2, Loader2, MailCheck } from 'lucide-react';
import { authApi, errorMessage } from '@/lib/api';
import { Button } from '@/components/Primitives';
import {
  Field,
  FormAlert,
  PasswordChecklist,
  isStrongPassword,
  looksLikeEmail,
} from '@/components/AuthPrimitives';
import { Link, useRouter } from '@/lib/router';
import { AuthShell } from '@/features/auth/AuthShell';

/* ── Request a reset link ─────────────────────────────────────────── */

export function ForgotPasswordScreen() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState<{ message: string; delivery: string } | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;

    const trimmed = email.trim();
    if (!trimmed) {
      setError('Enter your email address.');
      return;
    }
    if (!looksLikeEmail(trimmed)) {
      setError('Enter a valid email address.');
      return;
    }

    setError(null);
    setFormError(null);
    setSubmitting(true);
    try {
      const result = await authApi.forgotPassword(trimmed);
      setSent({ message: result.message, delivery: result.delivery });
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (sent) {
    return (
      <AuthShell
        eyebrow="Password reset"
        title="Check your inbox"
        subtitle="If an account exists for that address, a reset link is on its way."
        footer={
          <Link to="/login" className="text-champagne hover:text-champagne-bright">
            Back to sign in
          </Link>
        }
      >
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-3">
            <MailCheck className="h-5 w-5 text-champagne" />
            <p className="text-[13.5px] text-platinum-soft">{sent.message}</p>
          </div>

          {sent.delivery !== 'sent' && (
            <FormAlert tone="info">
              Email delivery is not configured on this deployment, so no message was sent. The
              reset token was recorded server-side — an operator can retrieve it, or set{' '}
              <span className="font-mono text-3xs">MAIL_*</span> to enable delivery.
            </FormAlert>
          )}

          <Link
            to="/login"
            className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors hover:text-platinum"
          >
            Return to sign in
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      eyebrow="Password reset"
      title="Forgot your password?"
      subtitle="We will send a single-use link to reset it. The link expires shortly after it is issued."
      footer={
        <Link to="/login" className="text-champagne hover:text-champagne-bright">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {formError && <FormAlert tone="error">{formError}</FormAlert>}

        <Field
          label="Email"
          type="email"
          name="email"
          autoComplete="username"
          inputMode="email"
          placeholder="you@example.com"
          value={email}
          error={error}
          onChange={(e) => {
            setEmail(e.target.value);
            if (error) setError(null);
          }}
        />

        <Button
          type="submit"
          size="lg"
          disabled={submitting}
          aria-busy={submitting}
          className="w-full"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Sending
            </>
          ) : (
            <>
              Send reset link
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </form>
    </AuthShell>
  );
}

/* ── Consume a reset token ────────────────────────────────────────── */

function readTokenFromHash(): string {
  if (typeof window === 'undefined') return '';
  const match = window.location.hash.match(/token=([^&]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

export function ResetPasswordScreen() {
  const { navigate } = useRouter();
  const [token] = useState(readTokenFromHash);

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<{ password?: string; confirmPassword?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const passwordRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (window.matchMedia('(min-width: 768px)').matches) passwordRef.current?.focus();
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;

    const next: { password?: string; confirmPassword?: string } = {};
    if (!password) next.password = 'Choose a new password.';
    else if (!isStrongPassword(password)) {
      next.password = 'Password does not meet the requirements below.';
    }
    if (!confirmPassword) next.confirmPassword = 'Confirm your new password.';
    else if (confirmPassword !== password) next.confirmPassword = 'Passwords do not match.';

    setErrors(next);
    setFormError(null);
    if (Object.keys(next).length) return;

    setSubmitting(true);
    try {
      await authApi.resetPassword({ token, password, confirmPassword });
      setDone(true);
      window.history.replaceState(null, '', '/reset-password');
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  /* No token in the fragment: the user opened the page directly. */
  if (!token) {
    return (
      <AuthShell
        eyebrow="Password reset"
        title="Link incomplete"
        subtitle="This page needs the link from your reset email."
        footer={
          <Link to="/forgot-password" className="text-champagne hover:text-champagne-bright">
            Request a new link
          </Link>
        }
      >
        <FormAlert tone="error">
          The reset token is missing from this URL. Open the link from your reset email, or
          request a new one.
        </FormAlert>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell
        eyebrow="Password reset"
        title="Password updated"
        subtitle="Every other session for this account has been signed out."
      >
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            <p className="text-[13.5px] text-platinum-soft">
              Your password has been reset. Sign in with your new password.
            </p>
          </div>
          <Button size="lg" className="w-full" onClick={() => navigate('/login')}>
            Continue to sign in
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      eyebrow="Password reset"
      title="Choose a new password"
      subtitle="This link is single-use and expires shortly after it was issued."
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {formError && <FormAlert tone="error">{formError}</FormAlert>}

        <div>
          <Field
            ref={passwordRef}
            label="New password"
            name="new-password"
            autoComplete="new-password"
            reveal
            placeholder="••••••••••"
            value={password}
            error={errors.password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors((p) => ({ ...p, password: undefined }));
            }}
          />
          <PasswordChecklist password={password} />
        </div>

        <Field
          label="Confirm new password"
          name="confirm-password"
          autoComplete="new-password"
          reveal
          placeholder="••••••••••"
          value={confirmPassword}
          error={errors.confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            if (errors.confirmPassword) setErrors((p) => ({ ...p, confirmPassword: undefined }));
          }}
        />

        <Button
          type="submit"
          size="lg"
          disabled={submitting}
          aria-busy={submitting}
          className="w-full"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Resetting
            </>
          ) : (
            <>
              Reset password
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
