"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice } from "@/components/Form";
import { ApiError, api, storeToken } from "@/lib/account";

/**
 * Where a provider sign-in lands.
 *
 * The URL carries a handoff, not a session: this posts it back once, in a request body, and
 * gets the real token. That is why the address bar, browser history and any referrer never
 * hold anything worth stealing for longer than the couple of minutes a handoff lives.
 */
export function Finish() {
  const router = useRouter();
  const params = useSearchParams();
  const handoff = params.get("handoff");
  const providerError = params.get("error");
  const [error, setError] = useState<string | null>(() => providerError);

  useEffect(() => {
    if (!handoff) return;
    let cancelled = false;
    api
      .redeemHandoff(handoff)
      .then((result) => {
        if (cancelled) return;
        storeToken(result.token);
        router.replace("/account");
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(
          caught instanceof ApiError ? caught.message : "That sign-in could not be finished.",
        );
      });
    return () => {
      // A handoff is single use, so a second attempt would fail and report a false problem.
      cancelled = true;
    };
  }, [handoff, router]);

  if (error) {
    return (
      <div className="space-y-5">
        <Notice kind="error">{error}</Notice>
        <Link
          href="/sign-in"
          className="rounded-sharp inline-block bg-fg px-6 py-3 font-medium text-bg transition-opacity hover:opacity-85"
        >
          Back to sign in
        </Link>
      </div>
    );
  }

  return <p className="text-fg-muted">Finishing your sign-in…</p>;
}
