import type { Metadata } from "next";

import { PhaseNotice } from "@/components/PhaseNotice";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Sign in</h1>
      <PhaseNotice phase={5}>
        There is no account to sign in to. Not a form that does nothing, and not a stub: this build
        has no account server and no code path that would send anything to one. When sign-in ships
        it will use OAuth 2.0 / OpenID Connect with PKCE — the desktop app opens this website in
        your system browser, you authenticate here, and a short-lived result is handed back through
        a secure callback, so your password never reaches the app and is never stored by it.
      </PhaseNotice>
      <p className="text-sm text-fg-muted">
        Today you do not need an account, because there is not one: your AI runs entirely on your
        own computer and nothing about it depends on us. When accounts arrive they are planned to be
        how you get installers and how you sign in on more than one device; pairing and optional
        encrypted sync build on them. They will never receive your conversations, memories or
        documents.
      </p>
      <p className="text-sm text-fg-muted">
        What exists today is local: each program you allow to act as your AI holds its own
        credential that you can revoke on its own, and the service only listens on your own machine.
      </p>
    </div>
  );
}
