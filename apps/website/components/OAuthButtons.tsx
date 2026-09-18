"use client";

import { useEffect, useState } from "react";

import { type OAuthProvider, api, oauthStartUrl } from "@/lib/account";

/**
 * One button per provider the server can actually use.
 *
 * The list comes from the server rather than being hard-coded, so a provider that is only
 * half configured — a client id with no secret — never appears as a button that leads to an
 * error. If none are set up, this renders nothing and the password form stands alone.
 */
export function OAuthButtons() {
  const [providers, setProviders] = useState<OAuthProvider[]>([]);

  useEffect(() => {
    api
      .oauthProviders()
      .then(setProviders)
      .catch(() => setProviders([]));
  }, []);

  if (providers.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {providers.map((provider) => (
          <a
            key={provider.name}
            href={oauthStartUrl(provider.name)}
            className="rounded-sharp block border border-fg px-6 py-3 text-center font-medium transition-colors hover:bg-fg hover:text-bg"
          >
            Continue with {provider.label}
          </a>
        ))}
      </div>
      <div className="flex items-center gap-4" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />
        <span className="datum text-fg-muted uppercase">or</span>
        <span className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}
