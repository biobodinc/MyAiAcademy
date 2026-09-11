/**
 * What a phone needs from the document itself: a real viewport that still allows zoom,
 * a manifest whose icons exist, and navigation links that point at pages that exist.
 */
import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";

import manifest from "../app/manifest";
import { NAV_LINKS, SIGN_IN } from "../lib/nav";

vi.mock("next/link", () => ({ default: () => null }));
vi.mock("@/components/SiteHeader", () => ({ SiteHeader: () => null }));
vi.mock("@/components/SiteFooter", () => ({ SiteFooter: () => null }));

const { viewport, metadata } = await import("../app/layout");
const websiteRoot = join(import.meta.dirname, "..");

describe("viewport", () => {
  it("uses the device width and never blocks pinch-zoom", () => {
    expect(viewport.width).toBe("device-width");
    expect(viewport.initialScale).toBe(1);
    // Locking the scale would fail accessibility guidance; assert it stays unset.
    expect(viewport.maximumScale).toBeUndefined();
    expect(viewport.userScalable).toBeUndefined();
  });

  it("colours the browser chrome for both themes", () => {
    const themes = viewport.themeColor;
    expect(Array.isArray(themes)).toBe(true);
    const media = (Array.isArray(themes) ? themes : []).map((t) => t.media);
    expect(media).toEqual(["(prefers-color-scheme: light)", "(prefers-color-scheme: dark)"]);
  });
});

describe("metadata", () => {
  it("links the manifest and allows adding to an iOS home screen", () => {
    expect(metadata.manifest).toBe("/manifest.webmanifest");
    expect(metadata.appleWebApp).toMatchObject({ capable: true });
    expect(existsSync(join(websiteRoot, "app", "apple-icon.png"))).toBe(true);
    expect(existsSync(join(websiteRoot, "app", "icon.svg"))).toBe(true);
  });
});

describe("manifest", () => {
  const m = manifest();

  it("is installable: standalone, scoped, with a start url", () => {
    expect(m.display).toBe("standalone");
    expect(m.start_url).toBe("/");
    expect(m.scope).toBe("/");
    expect(m.short_name && m.short_name.length).toBeLessThanOrEqual(12);
  });

  it("ships the icon sizes Android asks for, including a maskable one", () => {
    const icons = m.icons ?? [];
    expect(icons.map((i) => i.sizes)).toEqual(expect.arrayContaining(["192x192", "512x512"]));
    expect(icons.some((i) => i.purpose === "maskable")).toBe(true);
  });

  it("points only at icon files that exist", () => {
    for (const icon of m.icons ?? []) {
      expect(existsSync(join(websiteRoot, "public", icon.src))).toBe(true);
    }
  });
});

describe("navigation", () => {
  it("only links to pages that exist", () => {
    for (const link of [...NAV_LINKS, SIGN_IN]) {
      expect(existsSync(join(websiteRoot, "app", link.href, "page.tsx"))).toBe(true);
    }
  });
});
