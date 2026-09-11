export function PhaseNotice({ phase, children }: { phase: number; children: React.ReactNode }) {
  return (
    <div
      role="note"
      className="rounded-2xl border border-dashed border-border bg-bg-elevated p-6 text-sm text-fg-muted"
    >
      <span className="mr-2 rounded-md bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">
        Planned · Phase {phase}
      </span>
      {children}
    </div>
  );
}
