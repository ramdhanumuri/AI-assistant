/* Registration screen.

   Registration always produces a normal user: the request carries no role
   field and the backend hard-codes `ROLE_USER`, so there is no path from this
   form to an administrator account. Administrator provisioning is a deliberate
   operator action (`python -m app.cli.create_admin`). */

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Loader2, ShieldCheck } from 'lucide-react';
import { useAuth } from '@/state/AuthContext';
import { ApiError, errorMessage } from '@/lib/api';
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

interface Errors {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

export function RegisterScreen() {
  const { register, status } = useAuth();
  const { navigate } = useRouter();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const nameRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (window.matchMedia('(min-width: 768px)').matches) nameRef.current?.focus();
  }, []);

  useEffect(() => {
    if (status === 'authenticated') navigate('/chat', { replace: true });
  }, [status, navigate]);

  const validate = (): Errors => {
    const next: Errors = {};
    if (!fullName.trim()) next.fullName = 'Enter your full name.';

    const trimmedEmail = email.trim();
    if (!trimmedEmail) next.email = 'Enter your email address.';
    else if (!looksLikeEmail(trimmedEmail)) next.email = 'Enter a valid email address.';

    if (!password) next.password = 'Choose a password.';
    else if (!isStrongPassword(password)) {
      next.password = 'Password does not meet the requirements below.';
    }

    if (!confirmPassword) next.confirmPassword = 'Confirm your password.';
    else if (confirmPassword !== password) next.confirmPassword = 'Passwords do not match.';

    return next;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;

    const next = validate();
    setErrors(next);
    setFormError(null);
    if (Object.keys(next).length) return;

    setSubmitting(true);
    try {
      await register({
        fullName: fullName.trim(),
        email: email.trim(),
        password,
        confirmPassword,
      });
      navigate('/chat', { replace: true });
    } catch (error) {
      /* A duplicate address is a 409 with a safe message. A 422 names the
         field it rejected, so the copy lands on the right input instead of
         being blamed on the password unconditionally. */
      if (error instanceof ApiError && error.kind === 'conflict') {
        setErrors({ email: error.displayMessage });
      } else if (error instanceof ApiError && error.kind === 'validation') {
        const field = error.field;
        const message = error.displayMessage;
        if (field === 'email') setErrors({ email: message });
        else if (field === 'full_name' || field === 'fullName') setErrors({ fullName: message });
        else if (field === 'confirm_password' || field === 'confirmPassword')
          setErrors({ confirmPassword: message });
        else if (field) setErrors({ password: message });
        else setFormError(message);
      } else {
        setFormError(errorMessage(error));
      }
      setPassword('');
      setConfirmPassword('');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Registration"
      title="Create your account"
      subtitle="One private workspace for everything you ask the intelligence layer to hold."
      wide
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="text-champagne hover:text-champagne-bright">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {formError && <FormAlert tone="error">{formError}</FormAlert>}

        <Field
          ref={nameRef}
          label="Full name"
          name="name"
          autoComplete="name"
          placeholder="Ada Lovelace"
          maxLength={80}
          value={fullName}
          error={errors.fullName}
          onChange={(e) => {
            setFullName(e.target.value);
            if (errors.fullName) setErrors((p) => ({ ...p, fullName: undefined }));
          }}
        />

        <Field
          label="Email"
          type="email"
          name="email"
          autoComplete="username"
          inputMode="email"
          placeholder="you@example.com"
          value={email}
          error={errors.email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (errors.email) setErrors((p) => ({ ...p, email: undefined }));
          }}
        />

        <div>
          <Field
            label="Password"
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
          label="Confirm password"
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
          variant="gold"
          size="lg"
          disabled={submitting}
          aria-busy={submitting}
          className="w-full"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating account
            </>
          ) : (
            <>
              Create account
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>

        <div className="flex items-center justify-center gap-2 pt-1 text-platinum-dim">
          <ShieldCheck className="h-3 w-3 text-champagne/70" />
          <span className="font-mono text-3xs uppercase tracking-widest2">
            Accounts are always created as standard users
          </span>
        </div>
      </form>
    </AuthShell>
  );
}
