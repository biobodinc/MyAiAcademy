import Link from "next/link";

import { SITE } from "@/lib/site";

/**
 * Four claims, deliberately not four equal cards. Real features are lopsided — the first
 * two are what the project *is*, the second two are what it does — so they are set as an
 * indexed list with rules rather than a grid of identical boxes.
 */
const pillars = [
  {
    title: "Your AI",
    body: "Name it, give it a personality, and watch it level up skills you chose.",
  },
  {
    title: "Your hardware",
    body: "It runs and trains on your own computer. You decide how much power it may use.",
  },
  {
    title: "Your data",
    body: "Conversations, memories, files and model weights stay on your devices by default.",
  },
  {
    title: "Your skills",
    body: "Learn coding, writing, video, music and more, one measurable level at a time.",
  },
];

/**
 * The most unusual thing on this site is that it says what is not finished. Set as a
 * spec sheet in monospace, so a state reads as a measurement rather than a promise.
 */
const status = [
  { label: "Desktop app (Windows first)", phase: "1", state: "done" },
  { label: "Local chat, memory and knowledge", phase: "2", state: "done, see disclosures" },
  { label: "Skills, /learn, benchmarks and levels", phase: "3", state: "done" },
  { label: "/train, training jobs and checkpoints", phase: "4", state: "done" },
  { label: "Accounts, device pairing, mobile", phase: "5–6", state: "in progress" },
  { label: "Encrypted sync and portable .myai export", phase: "7–8", state: "in progress" },
];

export default function HomePage() {
  return (
    <div>
      {/* Hero. Left-aligned and asymmetric: the claim takes the wide column, the caveat
          sits beside it rather than under it, so the page opens with both at once. */}
      <section className="grid gap-10 md:grid-cols-12 md:gap-8">
        <div className="md:col-span-8">
          <p className="datum text-accent uppercase">{SITE.tagline}</p>
          <h1 className="display mt-5 text-[2.75rem] sm:text-6xl md:text-7xl">
            A personal AI you
            <br />
            actually own.
          </h1>
          <p className="mt-6 max-w-xl text-lg text-fg-muted">{SITE.description}</p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/download"
              className="rounded-sharp bg-fg px-6 py-3 text-center font-medium text-bg transition-opacity hover:opacity-85"
            >
              Download
            </Link>
            <Link
              href="/privacy"
              className="rounded-sharp border border-fg px-6 py-3 text-center font-medium transition-colors hover:bg-fg hover:text-bg"
            >
              Read the privacy promise
            </Link>
          </div>
        </div>

        <aside className="border-accent border-l-2 pl-5 md:col-span-4 md:pt-2">
          <p className="datum text-fg-muted uppercase">Read first</p>
          <p className="mt-3 text-sm text-fg-muted">
            Installers are not published yet, no catalog model has been run on consumer hardware by
            the authors, and the mobile app is a skeleton.
          </p>
          <Link
            href="/disclosures"
            className="mt-3 inline-block text-sm text-accent underline underline-offset-4"
          >
            The full list of what is not finished
          </Link>
        </aside>
      </section>

      {/* An indexed list, not a card grid. The rules carry the structure. */}
      <section className="mt-20 border-t border-border sm:mt-28">
        <dl>
          {pillars.map((p, i) => (
            <div
              key={p.title}
              className="grid items-baseline gap-x-6 gap-y-2 border-b border-border py-6 sm:grid-cols-12 sm:py-7"
            >
              <dt className="flex items-baseline gap-4 sm:col-span-4">
                <span className="datum text-fg-muted">{String(i + 1).padStart(2, "0")}</span>
                <span className="display text-2xl sm:text-3xl">{p.title}</span>
              </dt>
              <dd className="text-fg-muted sm:col-span-8 sm:text-lg">{p.body}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-24 sm:mt-32">
        <div className="max-w-2xl">
          <h2 className="display text-3xl sm:text-4xl">Where the project is</h2>
          <p className="mt-4 text-fg-muted">
            MyAI Academy is built in the open, phase by phase. We say what works today and what does
            not yet — on this page, in the README, and in the app itself.
          </p>
        </div>

        <table className="mt-10 w-full border-collapse text-left">
          <caption className="sr-only">Build status by phase</caption>
          <thead>
            <tr className="border-b border-fg">
              <th scope="col" className="datum py-2 pr-4 font-medium text-fg-muted uppercase">
                Phase
              </th>
              <th scope="col" className="datum py-2 pr-4 font-medium text-fg-muted uppercase">
                Capability
              </th>
              <th scope="col" className="datum py-2 text-right font-medium text-fg-muted uppercase">
                State
              </th>
            </tr>
          </thead>
          <tbody>
            {status.map((s) => (
              <tr key={s.label} className="border-b border-border align-baseline">
                <td className="datum py-4 pr-4 text-fg-muted whitespace-nowrap">{s.phase}</td>
                <td className="py-4 pr-4">{s.label}</td>
                <td className="datum py-4 text-right">
                  <span className={s.state === "done" ? "text-fg-muted" : "text-accent"}>
                    {s.state}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
