import type { Metadata } from "next";

import { DISCLOSURES, DISCLOSURES_UPDATED } from "@/lib/disclosures";
import { SITE } from "@/lib/site";

export const metadata: Metadata = { title: "Disclosures" };

export default function DisclosuresPage() {
  return (
    <article className="max-w-3xl">
      <h1 className="text-4xl font-bold tracking-tight">Disclosures</h1>
      <p className="mt-4 text-lg text-fg-muted">
        What is and is not verified in the current build. These statements hold until this page is
        updated. Last updated {DISCLOSURES_UPDATED}.
      </p>
      <ol className="mt-8 space-y-5">
        {DISCLOSURES.map((d, i) => (
          <li key={d.title} className="rounded-2xl border border-border bg-bg-elevated p-5">
            <h2 className="font-semibold">
              <span className="mr-2 text-fg-muted">{i + 1}.</span>
              {d.title}
            </h2>
            <p className="mt-2 text-sm text-fg-muted">{d.body}</p>
          </li>
        ))}
      </ol>
      <p className="mt-8 text-sm text-fg-muted">
        The same list lives in the repository README so the two cannot drift silently:{" "}
        <a
          className="underline"
          href={`https://github.com/${SITE.githubRepo}#disclosures`}
          rel="noopener noreferrer"
        >
          github.com/{SITE.githubRepo}
        </a>
        .
      </p>
    </article>
  );
}
