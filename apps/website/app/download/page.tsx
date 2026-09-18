import type { Metadata } from "next";
import Link from "next/link";

import { PhaseNotice } from "@/components/PhaseNotice";
import { fetchLatestRelease, formatSize, type Platform } from "@/lib/releases";

export const metadata: Metadata = { title: "Download" };

const ORDER: Array<{ platform: Platform; title: string; note?: string }> = [
  { platform: "windows", title: "Windows 10/11 (64-bit)" },
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
          Signed checksums will accompany every build. The desktop app bundles the local AI service;
          nothing phones home.
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
          No public release has been published yet, and there is no download to link to. Where
          builds will be hosted is not decided; this page will carry them when it is. The{" "}
          <Link className="underline" href="/cli">
            command-line interface
          </Link>{" "}
          describes what it will do, and the{" "}
          <Link className="underline" href="/disclosures">
            disclosures
          </Link>{" "}
          say what else is unfinished.
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
        <PhaseNotice phase={1}>
          <strong>No source checkout.</strong> Development happens in a private repository, so
          building it yourself is not an option today. Everything here will arrive as a signed build
          instead.
        </PhaseNotice>
      </div>
    </div>
  );
}
