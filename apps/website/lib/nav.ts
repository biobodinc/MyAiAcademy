// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
/** One source of navigation links, shared by the desktop row and the mobile menu. */
export interface NavLink {
  href: string;
  label: string;
}

export const NAV_LINKS: readonly NavLink[] = [
  { href: "/features", label: "Features" },
  { href: "/download", label: "Download" },
  { href: "/cli", label: "Command line" },
  { href: "/disclosures", label: "Disclosures" },
  { href: "/privacy", label: "Privacy" },
  { href: "/security", label: "Security" },
] as const;

export const SIGN_IN: NavLink = { href: "/sign-in", label: "Sign in" };
