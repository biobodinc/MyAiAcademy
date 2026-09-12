/**
 * Small, dependency-free UI primitives. Kept in one file on purpose: they are tiny and
 * they define the design language (cards, pills, badges, bars) used by every screen.
 */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

import { cx } from "../lib/cx";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const buttonVariants: Record<Variant, string> = {
  primary: "bg-accent text-accent-fg hover:brightness-110 shadow-sm",
  secondary: "bg-bg-muted text-fg hover:bg-border",
  ghost: "text-fg-muted hover:bg-bg-muted hover:text-fg",
  danger: "bg-danger text-white hover:brightness-110",
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "h-8 px-3 text-sm", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-base" };
  return (
    <button
      type="button"
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition",
        "disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-accent",
        buttonVariants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}

export function Card({
  children,
  className,
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section
      className={cx(
        "animate-rise rounded-card border border-border bg-bg-elevated p-5 shadow-card",
        className,
      )}
    >
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          {title && (
            <h2 className="text-sm font-semibold tracking-wide text-fg-muted uppercase">{title}</h2>
          )}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function ProgressBar({
  value,
  max = 100,
  label,
  tone = "accent",
}: {
  value: number;
  max?: number;
  label?: string;
  tone?: "accent" | "success" | "warning" | "danger";
}) {
  const fraction = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  const tones = {
    accent: "bg-accent",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
  };
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(fraction * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className="h-2.5 w-full overflow-hidden rounded-full bg-bg-muted"
    >
      <div
        className={cx("h-full rounded-full transition-[width] duration-500", tones[tone])}
        style={{ width: `${fraction * 100}%` }}
      />
    </div>
  );
}

export function LevelBadge({ level, size = "md" }: { level: number; size?: "sm" | "md" | "lg" }) {
  const sizes = {
    sm: "h-7 min-w-7 px-1.5 text-xs",
    md: "h-9 min-w-9 px-2 text-sm",
    lg: "h-16 min-w-16 px-3 text-2xl",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center justify-center rounded-full font-bold tabular-nums",
        level > 0 ? "bg-accent text-accent-fg" : "bg-bg-muted text-fg-muted",
        sizes[size],
      )}
      aria-label={`Level ${level}`}
    >
      {level}
    </span>
  );
}

export type Tone = "success" | "warning" | "danger" | "info" | "muted";

export function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }) {
  const dot: Record<Tone, string> = {
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    info: "bg-info",
    muted: "bg-fg-muted",
  };
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-bg-muted px-3 py-1 text-xs font-medium">
      <span className={cx("h-2 w-2 rounded-full", dot[tone])} aria-hidden />
      {children}
    </span>
  );
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="rounded-xl bg-bg-muted px-4 py-3">
      <div className="text-xs font-medium text-fg-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-fg-muted">{hint}</div>}
    </div>
  );
}

export function Alert({
  tone,
  title,
  children,
}: {
  tone: "info" | "warning" | "danger" | "success";
  title?: string;
  children: ReactNode;
}) {
  const tones = {
    info: "border-info/40 bg-info/10",
    warning: "border-warning/40 bg-warning/10",
    danger: "border-danger/40 bg-danger/10",
    success: "border-success/40 bg-success/10",
  };
  return (
    <div role="alert" className={cx("rounded-xl border px-4 py-3 text-sm", tones[tone])}>
      {title && <div className="font-semibold">{title}</div>}
      <div className={cx(title && "mt-1", "text-fg")}>{children}</div>
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="block">
      <span className="text-sm font-medium">{label}</span>
      {hint && <span className="block text-xs text-fg-muted">{hint}</span>}
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cx(
        "h-10 w-full rounded-xl border border-border bg-bg px-3 text-sm outline-none",
        "focus:border-accent focus:ring-2 focus:ring-accent/30",
        className,
      )}
      {...props}
    />
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-fg-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center">
      <div className="text-4xl" aria-hidden>
        {icon}
      </div>
      <div className="font-semibold">{title}</div>
      {children && <div className="max-w-md text-sm text-fg-muted">{children}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-fg-muted">
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-accent"
        aria-hidden
      />
      {label}
    </div>
  );
}

export function PhaseTag({ phase }: { phase: number }) {
  return (
    <span className="rounded-md bg-bg-muted px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-fg-muted uppercase">
      Phase {phase}
    </span>
  );
}

/** A label/value line inside a definition list. Shared by the pages that explain things. */
export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[6rem_1fr] gap-2">
      <dt className="text-fg-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}
