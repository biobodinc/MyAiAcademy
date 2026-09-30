// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import { SITE } from "../lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-border">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-8 text-sm text-fg-muted sm:flex-row sm:items-baseline sm:justify-between sm:px-6">
        <p className="display text-base text-fg">
          Private by default. Local by design. Sharing by choice.
        </p>
        <p className="datum">
          Created by{" "}
          <a
            className="underline underline-offset-4 hover:text-fg"
            href={SITE.authorUrl}
            rel="author noopener noreferrer"
            target="_blank"
          >
            {SITE.author}
          </a>{" "}
          · ©&nbsp;2026 ·{" "}
          <a
            className="underline underline-offset-4 hover:text-fg"
            href={SITE.repoUrl}
            rel="noopener noreferrer"
            target="_blank"
          >
            {SITE.license}
          </a>
        </p>
      </div>
    </footer>
  );
}
