// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
/**
 * Maps GitHub Release assets to download cards. Uses the public, unauthenticated
 * Releases API (no secret required). Cached with ISR so the site never hammers GitHub.
 */

export type Platform = "windows" | "macos" | "linux" | "android" | "ios" | "cli";

export interface DownloadAsset {
  platform: Platform;
  label: string;
  url: string;
  sizeBytes: number;
  fileName: string;
}

export interface ReleaseInfo {
  version: string;
  publishedAt: string;
  notesUrl: string;
  assets: DownloadAsset[];
}

interface GitHubAsset {
  name: string;
  browser_download_url: string;
  size: number;
}

interface GitHubRelease {
  tag_name: string;
  published_at: string;
  html_url: string;
  draft: boolean;
  prerelease: boolean;
  assets: GitHubAsset[];
}

const RULES: Array<{ test: RegExp; platform: Platform; label: string }> = [
  { test: /-setup\.exe$/i, platform: "windows", label: "Windows installer (.exe)" },
  { test: /\.msi$/i, platform: "windows", label: "Windows installer (.msi)" },
  { test: /\.dmg$/i, platform: "macos", label: "macOS disk image (.dmg)" },
  { test: /\.AppImage$/i, platform: "linux", label: "Linux AppImage" },
  { test: /\.deb$/i, platform: "linux", label: "Debian / Ubuntu package (.deb)" },
  { test: /\.rpm$/i, platform: "linux", label: "Fedora / RHEL package (.rpm)" },
  { test: /\.apk$/i, platform: "android", label: "Android package (.apk)" },
  { test: /^myai-cli-.*\.(zip|tar\.gz)$/i, platform: "cli", label: "Command-line interface" },
  { test: /^myai_cli-.*\.whl$/i, platform: "cli", label: "Command-line interface (Python wheel)" },
];

export function classifyAsset(asset: GitHubAsset): DownloadAsset | null {
  const rule = RULES.find((r) => r.test.test(asset.name));
  if (!rule) return null;
  return {
    platform: rule.platform,
    label: rule.label,
    url: asset.browser_download_url,
    sizeBytes: asset.size,
    fileName: asset.name,
  };
}

export function toReleaseInfo(release: GitHubRelease): ReleaseInfo {
  return {
    version: release.tag_name.replace(/^v/, ""),
    publishedAt: release.published_at,
    notesUrl: release.html_url,
    assets: release.assets.map(classifyAsset).filter((a): a is DownloadAsset => a !== null),
  };
}

/** The public repository whose Releases feed the download page reads. */
const REPO = "biobodinc/MyAiAcademy";

/** GitHub can answer with an error object, so the shape is checked before it is trusted. */
export function isGitHubRelease(value: unknown): value is GitHubRelease {
  if (typeof value !== "object" || value === null) return false;
  const r = value as Record<string, unknown>;
  return (
    typeof r["tag_name"] === "string" &&
    typeof r["published_at"] === "string" &&
    typeof r["html_url"] === "string" &&
    Array.isArray(r["assets"])
  );
}

/**
 * Reads the newest published release from GitHub's public Releases API. No token: the
 * repository is public, and `releases/latest` already skips drafts and prereleases, which is
 * exactly the behaviour this page wants — a build is offered here only once it has really
 * been published, so the page fills itself in when that happens instead of needing an edit.
 *
 * Revalidated hourly, so a burst of visitors cannot become a burst of API calls. Every
 * failure — no release yet, rate limit, GitHub down, an unexpected body — degrades to the
 * same honest empty state rather than breaking the page.
 */
export async function fetchLatestRelease(): Promise<ReleaseInfo | null> {
  try {
    const response = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
      headers: { Accept: "application/vnd.github+json" },
      next: { revalidate: 3600 },
    });
    if (!response.ok) return null;
    const payload: unknown = await response.json();
    if (!isGitHubRelease(payload) || payload.draft || payload.prerelease) return null;
    return toReleaseInfo(payload);
  } catch {
    return null;
  }
}

export function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
