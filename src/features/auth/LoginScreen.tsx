/* Login screen.

   Talks to the backend exclusively through `useAuth()`; it never calls the API
   directly. Error copy comes from the server's safe message, so a wrong
   password and an unknown address produce the same "Invalid email or password."
   — the screen must not help an attacker distinguish the two. */

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Loader2, ShieldCheck } from 'lucide-react';
import { useAuth } from '@/state/AuthContext';
import { ApiError, errorMessage } from '@/lib/api';
import { Button } from '@/components/Primitives';
import { Field, FormAlert, looksLikeEmail } from '@/components/AuthPrimitives';
import { Link, useRouter } from '@/lib/router';
import { AuthShell } from '@/features/auth/AuthShell';

export function LoginScreen() {
  const { login, status, endedReason, clearEndedReason } = useAuth();
  const { navigate } = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const emailRef = useRef<HTMLInputElement | null>(null);

  /* Autofocus is a courtesy, but on mobile it forces the keyboard open over a
     form the user has not looked at yet. */
  useEffect(() => {
    if (window.matchMedia('(min-width: 768px)').matches) emailRef.current?.focus();
  }, []);

  /* Already signed in: skip the form rather than render a dead end. */
  useEffect(() => {
    if (status === 'authenticated') navigate('/chat', { replace: true });
  }, [status, navigate]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;

    const trimmedEmail = email.trim();
    const nextErrors: { email?: string; password?: string } = {};
    if (!trimmedEmail) nextErrors.email = 'Enter your email address.';
    else if (!looksLikeEmail(trimmedEmail)) nextErrors.email = 'Enter a valid email address.';
    if (!password) nextErrors.password = 'Enter your password.';

    setFieldErrors(nextErrors);
    setFormError(null);
    if (Object.keys(nextErrors).length) return;

    setSubmitting(true);
    try {
      await login({ email: trimmedEmail, password });
      clearEndedReason();
      navigate('/chat', { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'validation') {
        setFieldErrors({ email: error.message });
      } else {
        setFormError(errorMessage(error));
      }
      setPassword('');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Authentication"
      title="Welcome back"
      subtitle="Sign in to resume your private intelligence workspace."
      footer={
        <>
          No account yet?{' '}
          <Link to="/register" className="text-champagne hover:text-champagne-bright">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {endedReason && !formError && <FormAlert tone="info">{endedReason}</FormAlert>}
        {formError && <FormAlert tone="error">{formError}</FormAlert>}

        <Field
          ref={emailRef}
          label="Email"
          type="email"
          name="email"
          autoComplete="username"
          inputMode="email"
          placeholder="you@example.com"
          value={email}
          error={fieldErrors.email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: undefined }));
          }}
        />

        <Field
          label="Password"
          name="password"
          autoComplete="current-password"
          reveal
          placeholder="••••••••••"
          value={password}
          error={fieldErrors.password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: undefined }));
          }}
        />

        <div className="flex justify-end">
          <Link
            to="/forgot-password"
            className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim transition-colors hover:text-platinum"
          >
            Forgot password?
          </Link>
        </div>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          disabled={submitting}
          aria-busy={submitting}
          className="w-full"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Signing in
            </>
          ) : (
            <>
              Sign in
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>

        <div className="flex items-center justify-center gap-2 pt-1 text-platinum-dim">
          <ShieldCheck className="h-3 w-3 text-champagne/70" />
          <span className="font-mono text-3xs uppercase tracking-widest2">
            Argon2id · HttpOnly session
          </span>
        </div>
      </form>
    </AuthShell>
  );
}
