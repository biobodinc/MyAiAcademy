# @myai/website

Public website: product information, downloads (read from GitHub Releases, no secrets), the
privacy promise, and the sign-in entry point (Phase 5).

Deploy on Vercel with the project **Root Directory** set to `apps/website`. All
configuration is public `NEXT_PUBLIC_*`; server-side secrets (Phase 5 OIDC) are set in the
Vercel dashboard, never committed.

```
pnpm --filter @myai/website dev
```
