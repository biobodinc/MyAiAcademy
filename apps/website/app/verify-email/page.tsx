import type { Metadata } from "next";
import { Suspense } from "react";

import { NoAccountServer } from "@/components/Form";
import { accountsAvailable } from "@/lib/account";

import { VerifyEmail } from "./VerifyEmail";

export const metadata: Metadata = { title: "Confirm your email" };

export default function VerifyEmailPage() {
  return (
    <div className="mx-auto max-w-md space-y-8">
      <h1 className="display text-4xl sm:text-5xl">Confirm your email</h1>
      {accountsAvailable() ? (
        // `useSearchParams` reads the token, and a statically rendered page has no query
        // string until it reaches the browser — hence the boundary.
        <Suspense fallback={<p className="text-fg-muted">Checking your link…</p>}>
          <VerifyEmail />
        </Suspense>
      ) : (
        <NoAccountServer />
      )}
    </div>
  );
}
