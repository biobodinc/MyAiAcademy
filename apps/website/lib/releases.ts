// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
/**
 * What the download page offers, and where the bytes come from.
 *
 * This used to read GitHub's public Releases API. The repository is private, so that feed
 * would answer 404 forever and the page would claim there was nothing to download while
 * installers existed. Builds are published to the site's own storage instead, and the list of
 * what was published is committed here as a manifest: no API, no token, no runtime dependency
 * on anything outside this deployment.
 *
 * The manifest holds names, sizes and hashes; it does not hold URLs. The host is one
 * environment variable, so moving the files does not mean rewriting a release record, and a
 * deployment with no host configured says so rather than rendering links that 404.
 */
import manifest from "./release-manifest.json";

export type Platform = "windows" | "macos" | "linux" | "chromeos" | "android" | "ios" | "cli";

export interface DownloadFile {
  platform: Platform;
  label: string;
  fileName: string;
  sizeBytes: number;
  /** Hex SHA-256 of the file as published, so an unsigned installer is still checkable. */
  sha256: string;
  url: string;
}

export interface ReleaseInfo {
  version: string;
  publishedAt: string;
  files: DownloadFile[];
}

interface ManifestFile {
  fileName: string;
  sizeBytes: number;
  sha256: string;
  /** Set only to override the filename-based guess. */
  platform?: Platform;
  label?: string;
}

interface Manifest {
  version: string;
  publishedAt: string;
  files: ManifestFile[];
}

/**
 * Filename to platform. The release workflow names its own artifacts, so this stays the one
 * place that decides which card a file belongs on, and the manifest only overrides it for a
 * file whose name cannot say (an .AppImage built for a Chromebook is still an .AppImage).
 */
const RULES: Array<{ test: RegExp; platform: Platform; label: string }> = [
  { test: /-setup\.exe$/i, platform: "windows", label: "Windows installer (.exe)" },
  { test: /\.msi$/i, platform: "windows", label: "Windows installer (.msi)" },
  { test: /\.dmg$/i, platform: "macos", label: "macOS disk image (.dmg)" },
  {
    test: /_arm64\.AppImage$|-aarch64\.AppImage$/i,
    platform: "linux",
    label: "Linux AppImage (ARM64)",
  },
  { test: /\.AppImage$/i, platform: "linux", label: "Linux AppImage (x86-64)" },
  { test: /_arm64\.deb$/i, platform: "linux", label: "Debian / Ubuntu package (.deb, ARM64)" },
  { test: /\.deb$/i, platform: "linux", label: "Debian / Ubuntu package (.deb, x86-64)" },
  { test: /\.rpm$/i, platform: "linux", label: "Fedora / RHEL package (.rpm)" },
  { test: /\.apk$/i, platform: "android", label: "Android package (.apk)" },
  { test: /^myai-cli-.*\.(zip|tar\.gz)$/i, platform: "cli", label: "Command-line interface" },
  { test: /^myai_cli-.*\.whl$/i, platform: "cli", label: "Command-line interface (Python wheel)" },
];

export function classifyFile(fileName: string): { platform: Platform; label: string } | null {
  const rule = RULES.find((r) => r.test.test(fileName));
  return rule ? { platform: rule.platform, label: rule.label } : null;
}

/** Where published builds are served from, without a trailing slash. */
export function downloadBase(): string | null {
  const base = process.env.NEXT_PUBLIC_DOWNLOAD_BASE?.trim();
  return base ? base.replace(/\/+$/, "") : null;
}

export function toReleaseInfo(data: Manifest, base: string): ReleaseInfo | null {
  if (!data.version.trim()) return null;
  const files: DownloadFile[] = [];
  for (const file of data.files) {
    const guess = classifyFile(file.fileName);
    const platform = file.platform ?? guess?.platform;
    const label = file.label ?? guess?.label;
    if (!platform || !label) continue;
    files.push({
      platform,
      label,
      fileName: file.fileName,
      sizeBytes: file.sizeBytes,
      sha256: file.sha256,
      url: `${base}/${encodeURIComponent(data.version)}/${encodeURIComponent(file.fileName)}`,
    });
  }
  return { version: data.version, publishedAt: data.publishedAt, files };
}

/**
 * The published release, or null when there is nothing to offer — either because no release
 * has been recorded or because this deployment has no download host configured. Both read the
 * same way on the page, which is the honest answer: there is no file you can fetch.
 */
export function getLatestRelease(): ReleaseInfo | null {
  const base = downloadBase();
  if (!base) return null;
  return toReleaseInfo(manifest as Manifest, base);
}

export function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
