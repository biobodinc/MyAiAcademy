"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";

import { storedToken } from "@/lib/account";
import { SIGN_IN } from "@/lib/nav";

/**
 * "Sign in" or "Your account", depending on whether this browser holds a session.
 *
 * The site is statically rendered, so the server cannot know which to show.
 * `useSyncExternalStore` is the right shape for this: it renders the signed-out label on
 * the server (`getServerSnapshot`), reads the real value on the client, and — because the
 * subscription is the `storage` event — signing out in one tab updates the others rather
 * than leaving them showing a link to an account they can no longer reach.
 */
function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

export function AccountLink({
  className,
  onNavigate,
}: {
  className: string;
  onNavigate?: () => void;
}) {
  const token = useSyncExternalStore(
    subscribe,
    () => storedToken(),
    () => null,
  );
  const signedIn = token !== null;

  return (
    <Link href={signedIn ? "/account" : SIGN_IN.href} className={className} onClick={onNavigate}>
      {signedIn ? "Your account" : SIGN_IN.label}
    </Link>
  );
}
