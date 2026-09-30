// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import type { Metadata } from "next";
import Link from "next/link";

import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Everything MyAI Academy does today, grouped by what it is for, with the limits of each capability stated next to it.",
};

/**
 * The feature list, grouped the way the app is grouped rather than by phase. Each entry may
 * carry a `gap`, which is the honest half of the entry: what this capability does not do yet.
 * A feature with no gap is finished. Nothing here describes a capability that does not exist
 * in the repository, which is why several entries are shorter than a marketing page would
 * like them to be.
 */
const groups: Array<{
  title: string;
  blurb: string;
  items: Array<{ name: string; body: string; gap?: string }>;
}> = [
  {
    title: "Your AI",
    blurb: "One AI that belongs to you, with a memory you control and work you can group.",
    items: [
      {
        name: "Profile",
        body: "Name your AI and set its personality. Every surface — desktop, phone, command line — calls it what you called it.",
      },
      {
        name: "Chat",
        body: "Streaming conversation with the model on your own machine. Rename conversations, change generation settings, and cancel mid-reply — the partial answer is kept and the model is released.",
      },
      {
        name: "Memory",
        body: "It remembers what you explicitly tell it to remember, and nothing else. You can list, add, forget and clear.",
      },
      {
        name: "Knowledge",
        body: "Add documents and it retrieves passages from them when you ask something related.",
        gap: "Retrieval is keyword-based (BM25 over SQLite full-text search), not semantic. Embedding search is planned and will be labelled when it ships.",
      },
      {
        name: "Projects",
        body: "Group conversations and knowledge into a project. Deleting one asks what to do with the contents instead of guessing.",
      },
    ],
  },
  {
    title: "Skills and training",
    blurb:
      "Skills are measured, not asserted. A level comes from a benchmark score, and nothing is graded by asking a model whether it liked the answer.",
    items: [
      {
        name: "Nine skills, six of them learnable",
        body: "Conversation, Writing, Coding, Research, Science and Games each have a real instruction package, a benchmark and a practice set. Every benchmark task is proven solvable by a reference answer, and a test asserts that a wrong answer fails.",
        gap: "Images, Video and Music have a provider interface and an honest report of what they would need, and cannot be learned or trained.",
      },
      {
        name: "/learn",
        body: "Runs the skill's benchmark and assigns a level from the score it actually measured. Shows what it will cost in time before it starts, and asks.",
      },
      {
        name: "/train",
        body: "Searches for better instructions for one skill — rules from its package, rules your AI writes after a mistake, worked examples — and keeps a change only when it scores higher on practice tasks the benchmark never uses.",
        gap: "This does not change your model's weights. Fine-tuning a quantised local model is not something this program can honestly do on the hardware it targets, so it does not claim to.",
      },
      {
        name: "Levels, history and checkpoints",
        body: "Every learning and training run is recorded with its score, and a training run can be undone from its checkpoint.",
      },
      {
        name: "Job control",
        body: "The running learning, benchmark or training job can be paused, resumed and stopped, and says which it is.",
      },
    ],
  },
  {
    title: "Models and hardware",
    blurb: "It runs on the computer in front of you, on the terms you set.",
    items: [
      {
        name: "Model catalog",
        body: "A curated set of GGUF models. The licence is shown and the download is confirmed before a byte is fetched.",
      },
      {
        name: "Bring your own model",
        body: "Import a GGUF file you already have, and the provider list shows what it found.",
      },
      {
        name: "Download verification",
        body: "A download is failed when it disagrees with a hash the publisher actually promises.",
        gap: "Where no published hash exists the file is checked for completeness only, and the model is labelled “unverified” rather than implying it was checked.",
      },
      {
        name: "Hardware detection and benchmark",
        body: "Detects your CPU, memory and graphics card, puts the machine in a capability tier, and can benchmark it so the tier is measured rather than assumed.",
      },
      {
        name: "Storage",
        body: "Choose where models and data live, see what is using the space, and clean up what you no longer need.",
      },
      {
        name: "Compute controls",
        body: "Decide how much of the machine your AI may use, including while a training job is running.",
      },
    ],
  },
  {
    title: "Privacy and security",
    blurb: "The promise is only worth what the controls enforce, so the controls are the feature.",
    items: [
      {
        name: "Local by default",
        body: "The service listens on 127.0.0.1 and nothing else can reach it. Every request is authenticated with a token created at install.",
      },
      {
        name: "Privacy Center",
        body: "Export everything the installation holds, or erase all of it. Only the installation itself can do either.",
      },
      {
        name: "Audit log",
        body: "Local security activity — pairing, revocation, network access going on and off, export and erase — recorded and filterable.",
      },
      {
        name: "Per-client credentials",
        body: "Each program or device that may act as your AI holds its own credential, revocable on its own. Credentials are stored as SHA-256 hashes and shown to you exactly once.",
      },
      {
        name: "Network access is opt-in",
        body: "If you allow devices in, a second listener starts that is HTTPS only, with a certificate your device pins when it pairs — so the device trusts that one computer and no other, with no certificate authority involved. This installation's own token is refused over the network.",
      },
    ],
  },
  {
    title: "Across your devices",
    blurb: "Sharing by choice: nothing leaves one machine for another unless you set that up.",
    items: [
      {
        name: "Device pairing",
        body: "A pairing code and a QR that carries the certificate fingerprint, so the device can compare it before trusting anything.",
      },
      {
        name: "Direct sync",
        body: "Two installations sync over the same pinned listener, with change tracking that cannot be forgotten and conflicts that never silently lose an edit.",
        gap: "The encrypted relay — for two machines that cannot see each other on a network — has no server running. The envelope it would carry is built and tested; the relay is not deployed.",
      },
      {
        name: "Portable .myai",
        body: "Export your AI to a single file, carry it to another machine or an external drive, and import it there with a compatibility verdict and a new install id. Optional encryption uses Argon2id and AES-GCM.",
        gap: "Backups are manual. There is no scheduled backup yet.",
      },
      {
        name: "Phone app",
        body: "The computer side of pairing is built and tested against a real pinned TLS listener, and the app reports its connection state truthfully.",
        gap: "The phone cannot finish pairing yet: pinning a self-signed certificate in React Native needs a native module and a development build, and a connection that has never been made on real hardware is not one to ship.",
      },
    ],
  },
  {
    title: "Ways in",
    blurb: "The same local service, reached three ways.",
    items: [
      {
        name: "Desktop app",
        body: "Seventeen screens over the local service: dashboard, chat, console, models, memory, knowledge, projects, skills, your AI, hardware, storage, Privacy Center, security, sync, portable, activity and settings.",
      },
      {
        name: "Command line",
        body: "A single executable with no Python to install. It exposes everything the desktop app does, against the same service.",
      },
      {
        name: "Local API",
        body: "Other programs on your machine can be granted scoped capabilities, and only the ones you granted.",
        gap: "Authorising a website against your own installation is not built yet.",
      },
    ],
  },
];

export default function FeaturesPage() {
  return (
    <div>
      <header className="max-w-3xl">
        <h1 className="display text-4xl sm:text-5xl">Features</h1>
        <p className="mt-4 text-base text-fg-muted sm:text-lg">
          Everything the program does today. Where a capability is unfinished, the limit is printed
          next to it rather than left for you to discover — the{" "}
          <Link className="underline underline-offset-4 hover:text-fg" href="/disclosures">
            disclosures
          </Link>{" "}
          collect those in one place, and the{" "}
          <a
            className="underline underline-offset-4 hover:text-fg"
            href={SITE.repoUrl}
            rel="noopener noreferrer"
            target="_blank"
          >
            source
          </a>{" "}
          is public under {SITE.license}, so none of it has to be taken on trust.
        </p>
      </header>

      {groups.map((group, gi) => (
        <section key={group.title} className="mt-16 sm:mt-20">
          <div className="flex items-baseline gap-4 border-b border-fg pb-3">
            <span className="datum text-fg-muted">{String(gi + 1).padStart(2, "0")}</span>
            <div>
              <h2 className="display text-2xl sm:text-3xl">{group.title}</h2>
              <p className="mt-1 max-w-2xl text-sm text-fg-muted">{group.blurb}</p>
            </div>
          </div>

          <dl>
            {group.items.map((item) => (
              <div
                key={item.name}
                className="grid gap-x-6 gap-y-2 border-b border-border py-6 sm:grid-cols-12"
              >
                <dt className="font-semibold sm:col-span-4">{item.name}</dt>
                <dd className="text-fg-muted sm:col-span-8">
                  <p>{item.body}</p>
                  {item.gap && (
                    <p className="mt-3 border-l-2 border-accent pl-4 text-sm">
                      <span className="datum text-accent uppercase">Not yet</span>
                      <span className="mt-1 block">{item.gap}</span>
                    </p>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}

      <p className="mt-14 max-w-2xl text-sm text-fg-muted">
        Phase by phase, what is finished and what is not is tracked on the{" "}
        <Link className="underline underline-offset-4 hover:text-fg" href="/">
          home page
        </Link>
        . What you can install right now is on the{" "}
        <Link className="underline underline-offset-4 hover:text-fg" href="/download">
          download page
        </Link>
        .
      </p>
    </div>
  );
}
