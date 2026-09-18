import type { Metadata } from "next";
import { Suspense } from "react";

import { Finish } from "./Finish";

export const metadata: Metadata = { title: "Signing you in" };

export default function OAuthFinishPage() {
  return (
    <div className="mx-auto max-w-md space-y-8">
      <h1 className="display text-4xl sm:text-5xl">Signing you in</h1>
      <Suspense fallback={<p className="text-fg-muted">Finishing your sign-in…</p>}>
        <Finish />
      </Suspense>
    </div>
  );
}
