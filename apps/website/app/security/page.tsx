import type { Metadata } from "next";

export const metadata: Metadata = { title: "Security" };

export default function SecurityPage() {
  return (
    <article className="max-w-3xl">
      <h1 className="display text-4xl sm:text-5xl">Security</h1>
      <p className="mt-4 text-base text-fg-muted sm:text-lg">
        Whenever convenience conflicts with security, we choose security.
      </p>
      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">
        How the desktop app protects itself
      </h2>
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
      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">Planned</h2>
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
      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">Reporting a vulnerability</h2>
      <p className="mt-3">
        There is no published channel for reporting one yet, and rather than point you at an address
        nobody is reading, this says so. A contact route will be published here before there are
        installers for anyone to attack.
      </p>
    </article>
  );
}
