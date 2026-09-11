import type { MetadataRoute } from "next";

import { SITE } from "@/lib/site";

/**
 * Web app manifest, so the site can be added to a phone's home screen and opens
 * standalone. It describes the *website*; the Android and iOS apps are separate and
 * arrive in Phase 6 (see the download page).
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE.name,
    short_name: "MyAI",
    description: SITE.description,
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    background_color: "#0e1016",
    theme_color: "#6d4aff",
    categories: ["productivity", "utilities"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
