import type { Metadata } from "next";

import { SITE } from "@/lib/site";

export const metadata: Metadata = { title: "Security" };

export default function SecurityPage() {
  return (
    <article className="max-w-3xl">
      <h1 className="text-4xl font-bold tracking-tight">Security</h1>
      <p className="mt-4 text-lg text-fg-muted">
        Whenever convenience conflicts with security, we choose security.
      </p>
      <h2 className="mt-10 text-2xl font-semibold">How the desktop app protects itself</h2>
      <ul className="mt-3 list-disc space-y-2 pl-6">
        <li>
          The local AI service binds to 127.0.0.1 only. There is no setting to expose it on a
          network.
        </li>
        <li>
          Every request carries a per-installation token stored with owner-only permissions. The
          desktop shell reads it from disk; it is never embedded in the user interface code.
        </li>
        <li>
          Browser origins are allow-listed and the Host header is validated, so a malicious web page
          cannot reach the service through your browser.
        </li>
        <li>
          The webview runs under a strict Content Security Policy and least-privilege capabilities.
        </li>
        <li>Security-relevant events are recorded in a local activity log you can inspect.</li>
      </ul>
      <h2 className="mt-10 text-2xl font-semibold">Planned</h2>
      <ul className="mt-3 list-disc space-y-2 pl-6">
        <li>OAuth 2.0 / OpenID Connect with PKCE for sign-in through this website (Phase 5).</li>
        <li>Per-device identities with revocation and scoped permissions (Phase 5–6).</li>
        <li>
          QR pairing using short-lived challenges and established cryptographic protocols (Phase 6).
        </li>
        <li>
          End-to-end encrypted sync with user-controlled keys and a published threat model (Phase
          7).
        </li>
      </ul>
      <h2 className="mt-10 text-2xl font-semibold">Reporting a vulnerability</h2>
      <p className="mt-3">
        Please open a private security advisory on{" "}
        <a
          className="underline"
          href={`https://github.com/${SITE.githubRepo}/security/advisories/new`}
          rel="noopener noreferrer"
        >
          GitHub
        </a>
        . Do not file public issues for security problems.
      </p>
    </article>
  );
}
