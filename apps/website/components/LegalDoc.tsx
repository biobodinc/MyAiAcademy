// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import type { ReactNode } from "react";

import { LEGAL } from "@/lib/legal";

/**
 * Marks a value that has not been decided yet. Legal drafts carry bracketed placeholders for
 * exactly this reason, and it reads as unfinished on purpose rather than as a quiet fiction.
 */
export function Unset({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-sharp border border-accent px-1.5 py-0.5 text-sm text-accent">
      [{children}]
    </span>
  );
}

export interface Clause {
  heading: string;
  body: ReactNode;
}

/**
 * Shared frame for the legal documents: numbered clauses, the dates that make a version
 * citable, and the unreviewed-draft notice. Numbering matters more than it looks — a clause
 * someone can point at by number is a clause that can be discussed.
 */
export function LegalDoc({
  title,
  summary,
  clauses,
}: {
  title: string;
  summary: ReactNode;
  clauses: Clause[];
}) {
  return (
    <article className="max-w-3xl">
      <h1 className="display text-4xl sm:text-5xl">{title}</h1>
      <p className="datum mt-4 text-fg-muted uppercase">
        Effective {LEGAL.effectiveDate} · Last updated {LEGAL.lastUpdated}
      </p>

      {!LEGAL.reviewed && (
        <div role="note" className="mt-6 border-l-2 border-accent py-1 pl-5 text-sm">
          <p className="datum text-accent uppercase">Draft</p>
          <p className="mt-2 text-fg-muted">
            No lawyer has reviewed this document. It was drafted to describe accurately what this
            software does, which is the part that can be got right by reading the code — but whether
            it protects anyone, and whether it is enforceable where you live, is a question for
            someone qualified to answer it. Treat it as a statement of intent.
          </p>
        </div>
      )}

      <p className="mt-6 text-base text-fg-muted sm:text-lg">{summary}</p>

      <ol className="mt-10 space-y-10">
        {clauses.map((clause, i) => (
          <li key={clause.heading} id={`clause-${String(i + 1)}`}>
            <h2 className="display flex items-baseline gap-3 text-2xl sm:text-3xl">
              <span className="datum text-fg-muted">{String(i + 1).padStart(2, "0")}</span>
              {clause.heading}
            </h2>
            <div className="mt-3 space-y-3 text-fg-muted">{clause.body}</div>
          </li>
        ))}
      </ol>
    </article>
  );
}
