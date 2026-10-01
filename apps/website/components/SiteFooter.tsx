// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import Link from "next/link";

import { SITE } from "../lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-border">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-8 text-sm text-fg-muted sm:flex-row sm:items-baseline sm:justify-between sm:px-6">
        <div>
          <p className="display text-base text-fg">
            Private by default. Local by design. Sharing by choice.
          </p>
          <nav className="mt-2 flex flex-wrap gap-x-4 gap-y-1" aria-label="Legal">
            <Link className="underline underline-offset-4 hover:text-fg" href="/legal/terms">
              Terms of Service
            </Link>
            <Link className="underline underline-offset-4 hover:text-fg" href="/legal/privacy">
              Privacy Policy
            </Link>
            <Link className="underline underline-offset-4 hover:text-fg" href="/disclosures">
              Disclosures
            </Link>
          </nav>
        </div>
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
            href={SITE.licenseUrl}
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
