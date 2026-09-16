import type { NextConfig } from "next";

/**
 * Security headers for the public site.
 *
 * `connect-src` is the one directive that has to move with configuration. The account
 * server (`packages/myai-server`) is a separate origin, so the account pages cannot reach
 * it unless it is named here — a browser blocks the fetch before it is sent, which is what
 * a CSP is for. Only the *origin* of `NEXT_PUBLIC_ACCOUNT_API` is added, and only when it
 * is set, so a deployment without accounts keeps the tighter policy rather than inheriting
 * a hole it does not need.
 *
 * Fonts stay on `'self'`: `next/font` downloads them at build time and serves them from
 * this origin, so nothing is fetched from Google at runtime.
 */
function accountApiOrigin(): string | null {
  const configured = process.env.NEXT_PUBLIC_ACCOUNT_API?.trim();
  if (!configured) return null;
  try {
    // Parsing rather than string-concatenating: a value carrying a path, credentials or
    // whitespace must not widen the directive beyond one origin.
    return new URL(configured).origin;
  } catch {
    throw new Error(
      `NEXT_PUBLIC_ACCOUNT_API is not a valid URL: ${configured}. ` +
        "Expected something like https://accounts.example.com",
    );
  }
}

const connectSrc = ["'self'", "https://api.github.com", accountApiOrigin()].filter(Boolean);

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https://avatars.githubusercontent.com",
      "font-src 'self'",
      `connect-src ${connectSrc.join(" ")}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
