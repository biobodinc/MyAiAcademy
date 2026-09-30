// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import type { Metadata } from "next";
import Link from "next/link";

import { PhaseNotice } from "@/components/PhaseNotice";
import { fetchLatestRelease, formatSize, type Platform } from "@/lib/releases";
import { SITE } from "@/lib/site";

export const metadata: Metadata = { title: "Download" };

const ORDER: Array<{ platform: Platform; title: string; note?: string }> = [
  {
    platform: "windows",
    title: "Windows 10/11 (64-bit)",
    note: "Not code-signed yet, so SmartScreen warns on first run until a certificate is in place.",
  },
  { platform: "cli", title: "Command line (myai)" },
  {
    platform: "macos",
    title: "macOS",
    note: "Architected for later; builds are unsigned until notarisation is set up.",
  },
  { platform: "linux", title: "Linux", note: "AppImage and .deb." },
];

export default async function DownloadPage() {
  const release = await fetchLatestRelease();

  return (
    <div className="space-y-8 sm:space-y-10">
      <div>
        <h1 className="display text-4xl sm:text-5xl">Download</h1>
        <p className="mt-3 text-fg-muted">
          This page reads the repository&apos;s public release feed directly, so whatever is listed
          here is whatever has actually been published. The desktop app bundles the local AI
          service; nothing phones home.
        </p>
      </div>

      {release ? (
        <p className="text-sm text-fg-muted">
          Latest release <strong>v{release.version}</strong> ·{" "}
          {new Date(release.publishedAt).toLocaleDateString("en", { dateStyle: "medium" })} ·{" "}
          <a className="underline" href={release.notesUrl} rel="noopener noreferrer">
            release notes
          </a>
        </p>
      ) : (
        <PhaseNotice phase={1}>
          No release has been published yet, so there is nothing to link to. The release workflow
          does build Windows, macOS and Linux bundles and command-line archives and attach them to a
          GitHub release, but every one so far is a draft: unsigned, and offered to nobody. This
          page reads the public release feed, so it will list them by itself once one is published.
          Meanwhile the{" "}
          <Link className="underline" href="/features">
            feature list
          </Link>{" "}
          says what the program does, and the{" "}
          <Link className="underline" href="/disclosures">
            disclosures
          </Link>{" "}
          say what is unfinished.
        </PhaseNotice>
      )}

      <div className="grid gap-4 sm:gap-6 md:grid-cols-2">
        {ORDER.map((entry) => {
          const assets = release?.assets.filter((a) => a.platform === entry.platform) ?? [];
          return (
            <div
              key={entry.platform}
              className="rounded-sharp border border-border bg-bg-elevated p-5 sm:p-6"
            >
              <h2 className="text-lg font-semibold">{entry.title}</h2>
              {entry.note && <p className="mt-1 text-xs text-fg-muted">{entry.note}</p>}
              {assets.length === 0 ? (
                <p className="mt-4 text-sm text-fg-muted">Not available yet.</p>
              ) : (
                <ul className="mt-4 space-y-2">
                  {assets.map((a) => (
                    <li key={a.url} className="min-w-0">
                      <a className="text-accent underline" href={a.url} rel="noopener noreferrer">
                        {a.label}
                      </a>
                      <span className="block text-xs break-all text-fg-muted">
                        {a.fileName} · {formatSize(a.sizeBytes)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 sm:gap-6 md:grid-cols-2">
        <PhaseNotice phase={6}>
          <strong>Android and iOS</strong> apps are authenticated controllers for your desktop AI.
          They arrive after accounts and device pairing exist, and will be listed on Google Play and
          the App Store here.
        </PhaseNotice>
        <div role="note" className="border-l-2 border-border py-1 pl-5 text-sm text-fg-muted">
          <p className="datum uppercase">Available now</p>
          <div className="mt-2">
            <strong className="text-fg">Build it yourself.</strong> The source is public under{" "}
            {SITE.license}, so a signed installer is not the only way to run this. Clone{" "}
            <a className="underline" href={SITE.repoUrl} rel="noopener noreferrer" target="_blank">
              the repository
            </a>{" "}
            and build the desktop app or the command line from it.
          </div>
        </div>
      </div>
    </div>
  );
}
