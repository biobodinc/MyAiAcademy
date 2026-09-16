"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice } from "@/components/Form";
import { ApiError, api } from "@/lib/account";

type State =
  | { kind: "working" }
  | { kind: "done"; email: string | null }
  | { kind: "failed"; message: string };

export function VerifyEmail() {
  const token = useSearchParams().get("token");
  // A link with no token is not an asynchronous outcome — it is knowable at render — so it
  // is the initial state rather than something an effect discovers and sets.
  const [state, setState] = useState<State>(() =>
    token
      ? { kind: "working" }
      : { kind: "failed", message: "That link is missing its confirmation code." },
  );

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .verifyEmail(token)
      .then((account) => {
        if (!cancelled) setState({ kind: "done", email: account.email });
      })
      .catch((caught) => {
        if (cancelled) return;
        setState({
          kind: "failed",
          message: caught instanceof ApiError ? caught.message : "Something went wrong. Try again.",
        });
      });
    return () => {
      // The link is single use, so a second run — React's development double-effect, or a
      // fast unmount and remount — would spend the token and report failure on the retry.
      cancelled = true;
    };
  }, [token]);

  if (state.kind === "working") {
    return <p className="text-fg-muted">Checking your link…</p>;
  }

  if (state.kind === "failed") {
    return (
      <div className="space-y-5">
        <Notice kind="error">{state.message}</Notice>
        <p className="text-sm text-fg-muted">
          You can ask for a new link from{" "}
          <Link href="/account" className="text-accent underline underline-offset-4">
            your account settings
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Notice kind="info">
        {state.email ? `${state.email} is confirmed.` : "Your address is confirmed."}
      </Notice>
      <Link
        href="/account"
        className="rounded-sharp inline-block bg-fg px-6 py-3 font-medium text-bg transition-opacity hover:opacity-85"
      >
        Go to your account
      </Link>
    </div>
  );
}
