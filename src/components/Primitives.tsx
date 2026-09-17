import { motion, useReducedMotion, type HTMLMotionProps } from 'framer-motion';
import { forwardRef, useCallback, useRef, useState, type ReactNode } from 'react';
import { cx, rgba } from '@/lib/utils';

/* ── GlassCard ──────────────────────────────────────────────────── */

interface GlassCardProps extends HTMLMotionProps<'div'> {
  children: ReactNode;
  /** Depth of the glass stack. */
  layer?: 'flat' | 'raised' | 'floating';
  /** Ambient aura colour as "r g b" — drives border + hover illumination. */
  aura?: string;
  /** Adds a perspective tilt that follows the pointer. */
  interactive?: boolean;
  className?: string;
}

/**
 * The core surface primitive. Glass, hairline edge light, and an ambient
 * border that illuminates toward the pointer on hover.
 */
export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  function GlassCard(
    { children, layer = 'raised', aura = '110 168 255', interactive = false, className, ...rest },
    ref,
  ) {
    const reduced = useReducedMotion();
    const localRef = useRef<HTMLDivElement | null>(null);
    const [glow, setGlow] = useState({ x: 50, y: 0, active: false });

    const onMove = useCallback(
      (e: React.PointerEvent<HTMLDivElement>) => {
        if (!interactive || reduced) return;
        const el = localRef.current;
        if (!el) return;
        const rect = el.getBoundingClientRect();
        setGlow({
          x: ((e.clientX - rect.left) / rect.width) * 100,
          y: ((e.clientY - rect.top) / rect.height) * 100,
          active: true,
        });
      },
      [interactive, reduced],
    );

    const shadow =
      layer === 'floating'
        ? 'shadow-glass-lg'
        : layer === 'raised'
          ? 'shadow-glass'
          : 'shadow-none';

    return (
      <motion.div
        ref={(node) => {
          localRef.current = node;
          if (typeof ref === 'function') ref(node);
          else if (ref) ref.current = node;
        }}
        onPointerMove={onMove}
        onPointerLeave={() => setGlow((g) => ({ ...g, active: false }))}
        className={cx(
          'group/card relative overflow-hidden rounded-[18px]',
          layer === 'flat' ? 'glass-soft' : 'glass',
          shadow,
          'edge-light',
          interactive && 'transition-transform duration-500 ease-cinematic',
          className,
        )}
        style={{ transformStyle: 'preserve-3d' }}
        {...rest}
      >
        {/* Pointer-tracked ambient illumination */}
        {interactive && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500"
            style={{
              opacity: glow.active ? 1 : 0,
              background: `radial-gradient(420px circle at ${glow.x}% ${glow.y}%, ${rgba(
                aura,
                0.13,
              )}, transparent 62%)`,
            }}
          />
        )}
        {/* Champagne hairline that warms the top edge on hover */}
        {interactive && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-6 top-0 h-px opacity-0 transition-opacity duration-500 group-hover/card:opacity-100"
            style={{
              background:
                'linear-gradient(90deg, transparent, rgba(216,195,154,0.6), transparent)',
            }}
          />
        )}
        {children}
      </motion.div>
    );
  },
);

/* ── Button ──────────────────────────────────────────────────────── */

interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'ref'> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'gold';
  size?: 'sm' | 'md' | 'lg';
  aura?: string;
  children: ReactNode;
  magnetic?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    aura = '110 168 255',
    magnetic = true,
    className,
    children,
    onPointerMove,
    ...rest
  },
  ref,
) {
  const reduced = useReducedMotion();
  const internalRef = useRef<HTMLButtonElement | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  const handleMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    onPointerMove?.(e);
    if (!magnetic || reduced) return;
    const el = internalRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const dx = (e.clientX - (rect.left + rect.width / 2)) / rect.width;
    const dy = (e.clientY - (rect.top + rect.height / 2)) / rect.height;
    setOffset({ x: dx * 6, y: dy * 5 });
  };

  const sizes: Record<string, string> = {
    sm: 'h-8 px-3.5 text-[11px] tracking-[0.14em]',
    md: 'h-11 px-6 text-[12px] tracking-[0.16em]',
    lg: 'h-14 px-8 text-[13px] tracking-[0.18em]',
  };

  const variants: Record<string, string> = {
    primary:
      'border border-white/10 bg-white/[0.07] text-platinum hover:bg-white/[0.11] hover:border-white/20',
    secondary:
      'border border-white/[0.07] bg-transparent text-platinum-dim hover:text-platinum hover:border-white/15',
    ghost: 'border border-transparent bg-transparent text-platinum-dim hover:text-platinum',
    gold: 'border border-champagne/30 bg-champagne/[0.08] text-champagne-bright hover:bg-champagne/[0.14] hover:border-champagne/45',
  };

  return (
    <motion.button
      ref={(node) => {
        internalRef.current = node;
        if (typeof ref === 'function') ref(node);
        else if (ref) ref.current = node;
      }}
      onPointerMove={handleMove}
      onPointerLeave={() => setOffset({ x: 0, y: 0 })}
      animate={{ x: offset.x, y: offset.y }}
      transition={{ type: 'spring', stiffness: 260, damping: 22, mass: 0.5 }}
      whileTap={{ scale: 0.975 }}
      className={cx(
        'relative inline-flex items-center justify-center gap-2.5 overflow-hidden rounded-full',
        'font-mono uppercase transition-colors duration-400 ease-silk',
        'disabled:pointer-events-none disabled:opacity-35',
        sizes[size],
        variants[variant],
        className,
      )}
      style={{ '--aura': aura } as React.CSSProperties}
      {...rest}
    >
      {/* Light reflection sweep on hover */}
      <span
        aria-hidden
        className="absolute inset-0 -translate-x-full opacity-0 transition-opacity duration-300 group-hover:opacity-100"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/[0.13] to-transparent opacity-0 transition-all duration-700 ease-cinematic hover:left-[110%] hover:opacity-100"
      />
      {children}
    </motion.button>
  );
});

/* ── Status pill ─────────────────────────────────────────────────── */

export function StatusPill({
  label,
  tone = 'aura',
  aura = '110 168 255',
  pulse = true,
  className,
}: {
  label: string;
  tone?: 'aura' | 'gold' | 'muted';
  aura?: string;
  pulse?: boolean;
  className?: string;
}) {
  const toneColor = tone === 'gold' ? '216 195 154' : tone === 'muted' ? '139 147 163' : aura;
  return (
    <span
      className={cx(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-3xs uppercase tracking-widest2',
        className,
      )}
      style={{
        borderColor: rgba(toneColor, 0.24),
        background: rgba(toneColor, 0.06),
        color: rgba(toneColor, 0.95),
      }}
    >
      <span className="relative flex h-1.5 w-1.5">
        {pulse && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
            style={{ background: rgba(toneColor, 0.8) }}
          />
        )}
        <span
          className="relative inline-flex h-1.5 w-1.5 rounded-full"
          style={{ background: rgba(toneColor, 1) }}
        />
      </span>
      {label}
    </span>
  );
}

/* ─ Section label ───────────────────────────────────────────────── */

export function SectionLabel({
  children,
  trailing,
  className,
}: {
  children: ReactNode;
  trailing?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx('flex items-center justify-between gap-4', className)}>
      <span className="eyebrow flex items-center gap-3">
        <span className="h-px w-6 bg-white/20" />
        {children}
      </span>
      {trailing}
    </div>
  );
}

/* ─ Divider ─────────────────────────────────────────────────────── */

export function Divider({ className }: { className?: string }) {
  return <div className={cx('hairline', className)} />;
}

/* ── Toggle ──────────────────────────────────────────────────────── */

export function Toggle({
  checked,
  onChange,
  label,
  aura = '110 168 255',
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  aura?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="relative h-6 w-11 shrink-0 rounded-full border transition-colors duration-400 ease-silk"
      style={{
        borderColor: checked ? rgba(aura, 0.4) : 'rgba(255,255,255,0.1)',
        background: checked ? rgba(aura, 0.16) : 'rgba(255,255,255,0.03)',
      }}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 460, damping: 32 }}
        className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full"
        style={{
          left: checked ? 25 : 3,
          background: checked ? rgba(aura, 0.95) : 'rgba(255,255,255,0.4)',
          boxShadow: checked ? `0 0 12px ${rgba(aura, 0.75)}` : 'none',
        }}
      />
    </button>
  );
}