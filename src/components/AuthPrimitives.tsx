/* Form primitives shared by the auth and admin screens.

   The password checks mirror `backend/app/core/security.py`
   (`validate_password_strength`) so the form can explain the policy before a
   round trip. The backend remains the authority — this is a courtesy, not a
   substitute, and every rule below is re-enforced server-side. */

import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Check, Eye, EyeOff } from 'lucide-react';
import { cx } from '@/lib/utils';

/* ── Policy (mirrors the backend) ─────────────────────────────────── */

export const PASSWORD_MIN_LENGTH = 10;
export const PASSWORD_MAX_LENGTH = 128;
export const FULL_NAME_MAX_LENGTH = 80;

const COMMON_PASSWORDS = ['password', 'qwerty', 'letmein', 'welcome', 'admin123'];

export interface PasswordRule {
  id: string;
  label: string;
  met: boolean;
}

export function passwordRules(password: string): PasswordRule[] {
  const classes = [
    /[a-z]/.test(password),
    /[A-Z]/.test(password),
    /[0-9]/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length;

  const lowered = password.toLowerCase();

  return [
    {
      id: 'length',
      label: `At least ${PASSWORD_MIN_LENGTH} characters`,
      met: password.length >= PASSWORD_MIN_LENGTH && password.length <= PASSWORD_MAX_LENGTH,
    },
    {
      id: 'classes',
      label: 'Two of: lowercase, uppercase, digits, symbols',
      met: classes >= 2,
    },
    {
      id: 'distinct',
      label: 'At least 4 distinct characters',
      met: password.length > 0 && new Set(password).size >= 4,
    },
    {
      id: 'common',
      label: 'Not a commonly used password',
      met: password.length > 0 && !COMMON_PASSWORDS.some((c) => lowered.includes(c)),
    },
  ];
}

export function isStrongPassword(password: string): boolean {
  return passwordRules(password).every((rule) => rule.met);
}

/* Deliberately permissive: the backend's EmailStr is the real validator. This
   only catches obvious typos so the user is not sent on a round trip. */
export function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

/* ── Field ────────────────────────────────────────────────────────── */

interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string;
  error?: string | null;
  hint?: ReactNode;
  /* Renders a reveal toggle and forces the autocomplete a password manager
     expects. */
  reveal?: boolean;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, error, hint, reveal = false, type = 'text', className, ...rest },
  ref,
) {
  const id = useId();
  const [shown, setShown] = useState(false);
  const inputType = reveal ? (shown ? 'text' : 'password') : type;
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        className="font-mono text-3xs uppercase tracking-widest2 text-platinum-dim"
      >
        {label}
      </label>

      <div className="relative">
        <input
          id={id}
          ref={ref}
          type={inputType}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cx(
            'h-12 w-full rounded-xl border bg-white/[0.03] px-4 text-[14px] text-platinum',
            'placeholder:text-platinum-dim/45',
            'transition-colors duration-300 ease-silk',
            'focus:bg-white/[0.055] focus:outline-none',
            error
              ? 'border-rose-400/45 focus:border-rose-400/70'
              : 'border-white/[0.09] focus:border-white/25',
            reveal && 'pr-12',
            className,
          )}
          {...rest}
        />

        {reveal && (
          <button
            type="button"
            onClick={() => setShown((s) => !s)}
            aria-label={shown ? 'Hide password' : 'Show password'}
            className={cx(
              'absolute right-1 top-1 flex h-10 w-10 items-center justify-center rounded-lg',
              'text-platinum-dim transition-colors duration-300 hover:text-platinum',
            )}
          >
            {shown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>

      <AnimatePresence initial={false}>
        {error ? (
          <motion.p
            key="error"
            id={`${id}-error`}
            role="alert"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="text-[12px] text-rose-300/90"
          >
            {error}
          </motion.p>
        ) : hint ? (
          <motion.div
            key="hint"
            id={`${id}-hint`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-[12px] text-platinum-dim"
          >
            {hint}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
});

/* ── Password requirement checklist ───────────────────────────────── */

export function PasswordChecklist({ password }: { password: string }) {
  /* Nothing typed yet: showing four unmet rules reads as four errors. */
  if (!password) return null;
  const rules = passwordRules(password);

  return (
    <ul className="mt-1 flex list-none flex-col gap-1.5" aria-label="Password requirements">
      {rules.map((rule) => (
        <li key={rule.id} className="flex items-center gap-2 text-[11.5px]">
          <span
            aria-hidden
            className={cx(
              'flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border',
              rule.met
                ? 'border-emerald-400/40 bg-emerald-400/15 text-emerald-300'
                : 'border-white/15 text-transparent',
            )}
          >
            <Check className="h-2.5 w-2.5" strokeWidth={3} />
          </span>
          <span className={rule.met ? 'text-platinum-dim' : 'text-platinum-dim/70'}>
            {rule.label}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ── Alert ────────────────────────────────────────────────────────── */

export function FormAlert({
  tone = 'error',
  children,
}: {
  tone?: 'error' | 'success' | 'info';
  children: ReactNode;
}) {
  const tones = {
    error: 'border-rose-400/25 bg-rose-400/[0.07] text-rose-200/95',
    success: 'border-emerald-400/25 bg-emerald-400/[0.07] text-emerald-200/95',
    info: 'border-white/12 bg-white/[0.04] text-platinum-soft',
  } as const;

  return (
    <motion.div
      role={tone === 'error' ? 'alert' : 'status'}
      initial={{ opacity: 0, y: -6, filter: 'blur(6px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className={cx(
        'flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-[12.5px] leading-relaxed',
        tones[tone],
      )}
    >
      {tone === 'error' && <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
      <span>{children}</span>
    </motion.div>
  );
}
