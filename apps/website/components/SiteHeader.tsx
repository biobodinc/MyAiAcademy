import Link from "next/link";

import { MobileNav } from "@/components/MobileNav";
import { NAV_LINKS, SIGN_IN } from "@/lib/nav";
import { SITE } from "@/lib/site";

export function SiteHeader() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
        {/* When the logo mark arrives it goes here, to the left of the wordmark, at about
            24px square. The wordmark stays: a mark alone is not recognisable yet. */}
        <Link href="/" className="display text-xl sm:text-2xl">
          {SITE.name}
        </Link>
        <nav className="hidden items-center gap-7 md:flex" aria-label="Main">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="py-2 text-sm text-fg-muted transition-colors hover:text-fg"
            >
              {link.label}
            </Link>
          ))}
          <Link
            href={SIGN_IN.href}
            className="rounded-sharp bg-fg px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-85"
          >
            {SIGN_IN.label}
          </Link>
        </nav>
        <MobileNav />
      </div>
    </header>
  );
}
