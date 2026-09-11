import Link from "next/link";

import { SITE } from "@/lib/site";

const links = [
  { href: "/download", label: "Download" },
  { href: "/privacy", label: "Privacy" },
  { href: "/security", label: "Security" },
];

export function SiteHeader() {
  return (
    <header className="border-b border-border bg-bg-elevated/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-bold tracking-tight">
          {SITE.name}
        </Link>
        <nav className="flex items-center gap-6 text-sm" aria-label="Main">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="text-fg-muted hover:text-fg">
              {l.label}
            </Link>
          ))}
          <Link
            href="/sign-in"
            className="rounded-full bg-accent px-4 py-1.5 font-medium text-accent-fg hover:brightness-110"
          >
            Sign in
          </Link>
        </nav>
      </div>
    </header>
  );
}
