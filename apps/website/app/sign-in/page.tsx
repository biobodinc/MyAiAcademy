import type { Metadata } from "next";

import { PhaseNotice } from "@/components/PhaseNotice";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-4xl font-bold tracking-tight">Sign in</h1>
      <PhaseNotice phase={5}>
        Accounts are not available yet, and we will not show a form that does nothing. When sign-in
        ships it will use OAuth 2.0 / OpenID Connect with PKCE: the desktop app opens this website
        in your system browser, you authenticate here, and a short-lived result is handed back to
        the app through a secure callback. Your password never reaches the app and is never stored
        by it.
      </PhaseNotice>
      <p className="text-sm text-fg-muted">
        You do not need an account to use MyAI Academy. Accounts only add device pairing and
        optional encrypted sync.
      </p>
    </div>
  );
}
