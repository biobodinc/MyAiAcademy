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

/**
 * Where published builds come from.
 *
 * Nowhere, currently. The source repository is private, so there is no public releases feed
 * to read and this returns null rather than calling one that would only ever 404. The
 * classification helpers above stay because they describe what a release *is*, and whatever
 * hosts the first signed installer will need them.
 */
export async function fetchLatestRelease(): Promise<ReleaseInfo | null> {
  return null;
}

export function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
