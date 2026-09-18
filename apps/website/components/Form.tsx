/** Form primitives in the site's own language: squared, ruled, no pills. */

import type { InputHTMLAttributes, ReactNode } from "react";

export function Field({
  label,
  hint,
  ...props
}: { label: string; hint?: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="datum text-fg-muted uppercase">{label}</span>
      <input
        {...props}
        className="rounded-sharp mt-2 block w-full border border-border bg-bg-elevated px-3 py-2.5 text-fg outline-none focus:border-fg"
      />
      {hint ? <span className="mt-1.5 block text-sm text-fg-muted">{hint}</span> : null}
    </label>
  );
}

export function SubmitButton({ children, busy }: { children: ReactNode; busy?: boolean }) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="rounded-sharp w-full bg-fg px-6 py-3 font-medium text-bg transition-opacity hover:opacity-85 disabled:opacity-50"
    >
      {busy ? "Working…" : children}
    </button>
  );
}

/**
 * `role="alert"` on the error so a screen reader announces a refusal the moment it appears;
 * a success note is not urgent enough to interrupt, so it gets `status`.
 */
export function Notice({ kind, children }: { kind: "error" | "info"; children: ReactNode }) {
  return (
    <p
      role={kind === "error" ? "alert" : "status"}
      className={`border-l-2 py-1 pl-4 text-sm ${
        kind === "error" ? "border-accent text-fg" : "border-border text-fg-muted"
      }`}
    >
      {children}
    </p>
  );
}

/** Shown wherever a page would otherwise offer a form that cannot work. */
export function NoAccountServer() {
  return (
    <div role="note" className="border-l-2 border-accent py-1 pl-5 text-sm text-fg-muted">
      <p className="datum text-accent uppercase">No account server</p>
      <div className="mt-2 space-y-3">
        <p>
          This build has no account server configured, so there is nothing to sign in to. Not a form
          that does nothing — there is no code path here that would send your details anywhere.
        </p>
        <p>
          You do not need an account to use MyAI Academy. Your AI runs entirely on your own
          computer. Accounts are how you will get installers and sign in on more than one device;
          they will never receive your conversations, memories or documents.
        </p>
      </div>
    </div>
  );
}
