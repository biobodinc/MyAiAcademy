# @myai/website

Public website: product information, downloads (read from GitHub Releases, no secrets), the
privacy promise, and the sign-in entry point (Phase 5).

Deploy on Vercel with the project **Root Directory** set to `apps/website`. All
configuration is public `NEXT_PUBLIC_*`; server-side secrets (Phase 5 OIDC) are set in the
Vercel dashboard, never committed.

```
pnpm --filter @myai/website dev
```

## Mobile support

The site is built for phones first and verified at four widths (360, 390, 768, 1280):

- **Navigation** below `md` is a `<details>` menu (`components/MobileNav.tsx`), so it
  still opens without JavaScript. The client component only adds what a static element
  cannot do: close on tap, on Escape (returning focus to the toggle), and after
  back/forward navigation.
- **Layout** uses one gutter set on the page shell, stacked hero buttons, stacking
  status rows, and a definition list for the CLI commands so no column is pushed off the
  side. Code blocks are the only horizontally scrollable element, which is intended.
- **Targets** are at least 24px tall for pointers and 44px in the phone menu; inline
  links inside sentences are exempt per WCAG 2.5.8.
- **Home screen**: `app/manifest.ts` makes the site installable (standalone, maskable
  icon) and `app/apple-icon.png` covers iOS. The viewport allows pinch-zoom on purpose.

Icons are generated from one vector definition, so re-run this after changing the mark:

```
uv run python scripts/generate_web_icons.py
```

`pnpm --filter @myai/website test` covers the menu behaviour, the manifest (including
that every icon file it names exists) and that the viewport never disables zoom.
