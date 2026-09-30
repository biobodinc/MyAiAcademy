// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
export function PhaseNotice({ phase, children }: { phase: number; children: React.ReactNode }) {
  return (
    <div role="note" className="border-l-2 border-accent py-1 pl-5 text-sm text-fg-muted">
      <p className="datum text-accent uppercase">Planned · Phase {phase}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}
