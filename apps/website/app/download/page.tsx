// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import type { Metadata } from "next";
import Link from "next/link";

import { PhaseNotice } from "@/components/PhaseNotice";
import { formatSize, getLatestRelease, type Platform } from "@/lib/releases";

export const metadata: Metadata = { title: "Download" };

const ORDER: Array<{ platform: Platform; title: string; note?: string }> = [
  {
    platform: "windows",
    title: "Windows 10/11 (64-bit)",
    note: "Not signed by a certificate authority, so SmartScreen warns on first run. Check the hash below against the file you downloaded.",
  },
  {
    platform: "linux",
    title: "Linux (x86-64 and ARM64)",
    note: "AppImage runs anywhere; the .deb is for Debian and Ubuntu. Needs WebKitGTK 4.1.",
  },
  {
    platform: "chromeos",
    title: "Chromebook",
    note: "Runs as a Linux app inside ChromeOS. See the note below the cards before you try it.",
  },
  { platform: "cli", title: "Command line (myai)" },
  {
    platform: "macos",
    title: "macOS",
    note: "Ad-hoc signed only, not notarised: right-click the app and choose Open the first time.",
  },
];

export default function DownloadPage() {
  const release = getLatestRelease();

  return (
    <div className="space-y-8 sm:space-y-10">
      <div>
        <h1 className="display text-4xl sm:text-5xl">Download</h1>
        <p className="mt-3 text-fg-muted">
          Builds are served from this site, and every file is listed with its SHA-256 so you can
          check what you got. The desktop app bundles the local AI service; nothing phones home.
        </p>
      </div>

      {release ? (
        <p className="text-sm text-fg-muted">
          Latest release <strong>v{release.version}</strong>
          {release.publishedAt && (
            <>
              {" · "}
              {new Date(release.publishedAt).toLocaleDateString("en", { dateStyle: "medium" })}
            </>
          )}
        </p>
      ) : (
        <PhaseNotice phase={1}>
          No release has been published yet, so there is nothing to link to. The release workflow
          builds Windows, Linux and macOS bundles and command-line archives, but none has been
          published to this site. When one is, it is listed here with its hash. Meanwhile the{" "}
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
          const files = release?.files.filter((f) => f.platform === entry.platform) ?? [];
          return (
            <div
              key={entry.platform}
              className="rounded-sharp border border-border bg-bg-elevated p-5 sm:p-6"
            >
              <h2 className="text-lg font-semibold">{entry.title}</h2>
              {entry.note && <p className="mt-1 text-xs text-fg-muted">{entry.note}</p>}
              {files.length === 0 ? (
                <p className="mt-4 text-sm text-fg-muted">Not available yet.</p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {files.map((f) => (
                    <li key={f.url} className="min-w-0">
                      <a className="text-accent underline" href={f.url} rel="noopener noreferrer">
                        {f.label}
                      </a>
                      <span className="block text-xs break-all text-fg-muted">
                        {f.fileName} · {formatSize(f.sizeBytes)}
                      </span>
                      {f.sha256 && (
                        <code className="mt-1 block text-[0.65rem] break-all text-fg-muted">
                          sha256 {f.sha256}
                        </code>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 sm:gap-6 md:grid-cols-2">
        <div role="note" className="border-l-2 border-border py-1 pl-5 text-sm text-fg-muted">
          <p className="datum uppercase">About Chromebooks</p>
          <div className="mt-2 space-y-2">
            <p>
              ChromeOS has no separate build. It runs the Linux one: turn on the Linux development
              environment in Settings, then install the <code>.deb</code> that matches your
              Chromebook&apos;s processor — ARM64 for most, x86-64 for Intel and AMD models.
            </p>
            <p>
              Be warned that this program&apos;s whole point is running a model on your own
              hardware, and most Chromebooks have little memory and no usable graphics card. It will
              install and it will talk to you; a model large enough to be interesting may not fit.
              The hardware page tells you what it found before you download anything.
            </p>
          </div>
        </div>
        <PhaseNotice phase={6}>
          <strong>Android and iOS</strong> apps are authenticated controllers for your desktop AI.
          They arrive after pairing works on real hardware, and will be listed on Google Play and
          the App Store here.
        </PhaseNotice>
      </div>
    </div>
  );
}
