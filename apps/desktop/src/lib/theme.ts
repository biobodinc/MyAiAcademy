// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import type { Theme } from "@myai/api-client";

/** Apply the user's theme preference to <html data-theme>. "system" removes the attribute. */
export function applyTheme(theme: Theme | undefined): void {
  const root = document.documentElement;
  if (!theme || theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}
