import type { Metadata } from "next";
import Link from "next/link";

import { PhaseNotice } from "@/components/PhaseNotice";
import { SITE } from "@/lib/site";

export const metadata: Metadata = { title: "Command line" };

const STEPS = [
  `git clone https://github.com/${SITE.githubRepo}.git`,
  "cd MyAiAcademy",
  "uv sync --all-packages --all-groups --all-extras",
  "uv run myai serve        # terminal 1: the local service, 127.0.0.1 only",
  "uv run myai status       # terminal 2",
  "uv run myai profile create --name Nova",
  "uv run myai storage set-root ~/MyAI",
  "uv run myai models list",
  "uv run myai models download qwen2.5-1.5b-instruct-q4km",
  "uv run myai chat",
];

const COMMANDS: Array<[string, string]> = [
  ["myai status", "AI, internet and training availability"],
  ["myai hardware", "detected hardware and capability tier"],
  ["myai storage show | set-root <path>", "where models and data live"],
  ["myai profile show | create | set", "your AI's name and personality"],
  ["myai models list | show | download | use | remove", "catalog, licences, downloads"],
  ["myai chat [message]", "streaming chat; interactive when no message is given"],
  ["myai memory list | add | forget | clear", "what your AI remembers (explicit only)"],
  ["myai knowledge add | list | search | remove", "documents it can retrieve from"],
  ['myai run "/hardware"', "run any slash command"],
  ["myai audit", "local security activity"],
];

export default function CliPage() {
  return (
    <article className="max-w-3xl">
      <h1 className="text-4xl font-bold tracking-tight">Command line</h1>
      <p className="mt-4 text-lg text-fg-muted">
        Until installers are published, the supported way to use MyAI Academy is the{" "}
        <code className="rounded bg-bg-elevated px-1">myai</code> command line run from a source
        checkout. It exposes everything the desktop app does today, against the same local service.
      </p>
      <div className="mt-6">
        <PhaseNotice phase={1}>
          Temporary interface, until further notice. When signed installers exist the{" "}
          <Link className="underline" href="/download">
            download page
          </Link>{" "}
          becomes the main path and this page becomes a reference.
        </PhaseNotice>
      </div>

      <h2 className="mt-10 text-2xl font-semibold">Requirements</h2>
      <ul className="mt-3 list-disc space-y-1 pl-6">
        <li>
          Python 3.11 or newer and{" "}
          <a className="underline" href="https://docs.astral.sh/uv/" rel="noopener noreferrer">
            uv
          </a>
        </li>
        <li>
          CMake and a C++ compiler (the local inference runtime is built from source unless a
          prebuilt wheel matches your platform)
        </li>
        <li>Roughly 1 to 5 GB of disk per model you download</li>
      </ul>

      <h2 className="mt-10 text-2xl font-semibold">Get running</h2>
      <pre className="mt-3 overflow-x-auto rounded-2xl border border-border bg-bg-elevated p-4 text-sm">
        {STEPS.join("\n")}
      </pre>
      <p className="mt-3 text-sm text-fg-muted">
        The download step shows the model licence and asks before fetching anything. The service
        listens on 127.0.0.1 only and authenticates every request with a per-install token.
      </p>

      <h2 className="mt-10 text-2xl font-semibold">Commands</h2>
      <table className="mt-3 w-full text-sm">
        <tbody>
          {COMMANDS.map(([cmd, what]) => (
            <tr key={cmd} className="border-t border-border">
              <td className="py-2 pr-4 font-mono whitespace-nowrap">{cmd}</td>
              <td className="py-2 text-fg-muted">{what}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
