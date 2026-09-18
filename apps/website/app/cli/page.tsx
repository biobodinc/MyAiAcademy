import type { Metadata } from "next";
import Link from "next/link";

import { PhaseNotice } from "@/components/PhaseNotice";

export const metadata: Metadata = { title: "Command line" };

const STEPS = [
  "myai serve        # terminal 1: the local service, 127.0.0.1 only",
  "myai status       # terminal 2",
  "myai profile create --name Nova",
  "myai storage set-root ~/MyAI",
  "myai models list",
  "myai models download qwen2.5-1.5b-instruct-q4km",
  "myai chat",
];

const COMMANDS: Array<[string, string]> = [
  ["myai status", "AI, internet and training availability"],
  ["myai hardware", "detected hardware and capability tier"],
  ["myai storage show | set-root <path>", "where models and data live"],
  ["myai profile show | create | set", "your AI's name and personality"],
  ["myai models list | show | download | use | remove", "catalog, licences, downloads"],
  ["myai chat [message]", "streaming chat; interactive when no message is given"],
  ["myai memory list | add | forget | clear", "what your AI remembers (explicit only)"],
  [
    "myai projects list | new | archive | delete",
    "group work together; delete asks what to do with the contents",
  ],
  ["myai knowledge add | list | search | remove", "documents it can retrieve from"],
  ["myai learn <skill> | evaluate | history", "skill packages, benchmarks and levels"],
  ["myai train <skill> | training <skill>", "practise a learned skill; runs and undo"],
  ["myai jobs list | pause | resume | stop", "the running learning, benchmark or training job"],
  ['myai ask "what is training?"', "the built-in guide (not your AI model)"],
  ['myai run "/hardware"', "run any slash command"],
  ["myai security show | clients | pairing-code | pair | revoke", "who may act as your AI"],
  ["myai security network | invite", "let devices on your network in, and pair them"],
  ["myai security export | erase", "take your data out, or delete all of it"],
  ["myai audit", "local security activity"],
];

export default function CliPage() {
  return (
    <article className="max-w-3xl">
      <h1 className="display text-4xl sm:text-5xl">Command line</h1>
      <p className="mt-4 text-base text-fg-muted sm:text-lg">
        <code className="rounded bg-bg-elevated px-1">myai</code> is a single executable with no
        Python to install: put it on your PATH and it works from any directory. It exposes
        everything the desktop app does today, against the same local service.
      </p>
      <div className="mt-6">
        <PhaseNotice phase={1}>
          There is nothing to download yet — see the{" "}
          <Link className="underline" href="/download">
            download page
          </Link>
          . This describes what the command does once there is, and the development repository is
          private, so there is no source checkout to build it from in the meantime.
        </PhaseNotice>
      </div>

      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">Requirements</h2>
      <ul className="mt-3 list-disc space-y-1 pl-6">
        <li>No Python, and nothing else to install: the runtime is inside the executable</li>
        <li>Roughly 1 to 5 GB of disk per model you download</li>
      </ul>

      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">Get running</h2>
      <pre className="mt-3 overflow-x-auto rounded-sharp border border-border bg-bg-elevated p-4 text-xs sm:text-sm">
        {STEPS.join("\n")}
      </pre>
      <p className="mt-3 text-sm text-fg-muted">
        The download step shows the model licence and asks before fetching anything. The service
        listens on 127.0.0.1 only and authenticates every request with a per-install token.
      </p>

      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">Commands</h2>
      {/* A definition list rather than a table: on a phone the command and what it does
          stack, instead of the second column disappearing off the side. */}
      <dl className="mt-3 divide-y divide-border text-sm">
        {COMMANDS.map(([cmd, what]) => (
          <div key={cmd} className="grid gap-0.5 py-3 sm:grid-cols-[minmax(0,19rem)_1fr] sm:gap-4">
            <dt className="font-mono break-words">{cmd}</dt>
            <dd className="text-fg-muted">{what}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-6 text-sm text-fg-muted">
        Before relying on it, read the{" "}
        <Link className="underline" href="/disclosures">
          disclosures
        </Link>
        .
      </p>
    </article>
  );
}
