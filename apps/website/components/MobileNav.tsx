"use client";

/**
 * The navigation menu shown below the `md` breakpoint.
 *
 * It is a `<details>` element rather than a button with React state so the menu still
 * opens when JavaScript has not loaded or is blocked; the client component only adds the
 * niceties a static element cannot do by itself: close after navigating, and close on
 * Escape with focus returned to the toggle.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { NAV_LINKS, SIGN_IN } from "@/lib/nav";

export function MobileNav() {
  const pathname = usePathname();
  const details = useRef<HTMLDetailsElement>(null);

  const close = () => {
    if (details.current) details.current.open = false;
  };

  useEffect(() => {
    // Client-side navigation keeps this element mounted, so close it by hand. Tapping a
    // link closes it immediately (below); this also covers back/forward navigation.
    close();
  }, [pathname]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !details.current?.open) return;
      details.current.open = false;
      details.current.querySelector("summary")?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  return (
    <details ref={details} className="relative md:hidden">
      <summary
        aria-label="Menu"
        className="flex h-11 w-11 cursor-pointer list-none items-center justify-center rounded-xl border border-border text-fg-muted marker:content-none hover:text-fg focus-visible:outline-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M3 5h14M3 10h14M3 15h14" />
        </svg>
      </summary>
      <nav
        aria-label="Main"
        className="absolute right-0 z-50 mt-2 w-56 rounded-2xl border border-border bg-bg-elevated p-2 shadow-lg"
      >
        <ul className="flex flex-col">
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                onClick={close}
                aria-current={pathname === link.href ? "page" : undefined}
                className="block rounded-xl px-3 py-3 text-fg-muted hover:bg-bg hover:text-fg aria-[current=page]:text-fg"
              >
                {link.label}
              </Link>
            </li>
          ))}
          <li className="mt-1 border-t border-border pt-2">
            <Link
              href={SIGN_IN.href}
              onClick={close}
              className="block rounded-xl bg-accent px-3 py-3 text-center font-medium text-accent-fg"
            >
              {SIGN_IN.label}
            </Link>
          </li>
        </ul>
      </nav>
    </details>
  );
}
