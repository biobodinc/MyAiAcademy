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
    note: "Not notarised by Apple, so Gatekeeper refuses it on first launch. See First run below.",
  },
];

/**
 * What each operating system actually does on first launch, and the click-path out of it.
 *
 * This section exists because no amount of signing we can do removes these prompts. A
 * self-signed certificate does not chain to a root Windows trusts, so Windows reports the
 * signature as untrusted and SmartScreen warns regardless; Gatekeeper accepts only an
 * Apple-issued Developer ID certificate with notarisation. Telling someone exactly which
 * dialog to expect is worth more than a signature that does not change the dialog.
 */
const FIRST_RUN: Array<{ os: string; sees: string; does: string }> = [
  {
    os: "Windows",
    sees: "“Windows protected your PC” from SmartScreen, because this installer has no reputation with Microsoft yet.",
    does: "Click More info, check that the publisher and file name match what is listed above, then Run anyway. If Defender quarantines the file instead, that is a heuristic match on the bundled Python runtime rather than a detection of anything in it — the hash above is what you should check.",
  },
  {
    os: "macOS",
    sees: "“Apple could not verify that this app is free of malware”, because the app is not notarised by Apple.",
    does: "Open it once and let it be refused, then go to System Settings, Privacy & Security, scroll to the message about MyAI Academy and choose Open Anyway. On macOS 14 and earlier you can right-click the app and choose Open instead; Apple removed that shortcut in macOS 15.",
  },
  {
    os: "Linux and ChromeOS",
    sees: "Nothing. There is no gatekeeper to get past.",
    does: "Install the .deb with your package manager, or mark the AppImage executable and run it. Check the hash first if you care to; nothing else will check it for you.",
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

      <section>
        <h2 className="display text-2xl sm:text-3xl">First run</h2>
        <p className="mt-2 max-w-2xl text-sm text-fg-muted">
          None of these builds is signed by a certificate authority, so two of the three systems
          will stop you the first time. Signing them ourselves would not change that — Windows
          treats a self-signed signature as untrusted, and Gatekeeper accepts only Apple&apos;s own.
          So here is the prompt you will get and what to do with it.
        </p>
        <dl className="mt-6">
          {FIRST_RUN.map((entry) => (
            <div
              key={entry.os}
              className="grid gap-x-6 gap-y-2 border-b border-border py-5 sm:grid-cols-12"
            >
              <dt className="font-semibold sm:col-span-3">{entry.os}</dt>
              <dd className="space-y-2 text-sm text-fg-muted sm:col-span-9">
                <p>
                  <span className="datum text-accent uppercase">You see</span>{" "}
                  <span className="mt-1 block">{entry.sees}</span>
                </p>
                <p>
                  <span className="datum uppercase">You do</span>{" "}
                  <span className="mt-1 block">{entry.does}</span>
                </p>
              </dd>
            </div>
          ))}
        </dl>
      </section>

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
