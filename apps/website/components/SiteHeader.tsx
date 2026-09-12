import Link from "next/link";

import { MobileNav } from "@/components/MobileNav";
import { NAV_LINKS, SIGN_IN } from "@/lib/nav";
import { SITE } from "@/lib/site";

export function SiteHeader() {
  return (
    <header className="border-b border-border bg-bg-elevated/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4">
        <Link href="/" className="text-base font-bold tracking-tight sm:text-lg">
          {SITE.name}
        </Link>
        <nav className="hidden items-center gap-6 text-sm md:flex" aria-label="Main">
          {NAV_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="py-2 text-fg-muted hover:text-fg">
              {link.label}
            </Link>
          ))}
          <Link
            href={SIGN_IN.href}
            className="rounded-full bg-accent px-4 py-2 font-medium text-accent-fg hover:brightness-110"
          >
            {SIGN_IN.label}
          </Link>
        </nav>
        <MobileNav />
      </div>
    </header>
  );
}
