import Link from "next/link";

import { SITE } from "@/lib/site";

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

const status = [
  { label: "Desktop app (Windows first)", state: "Phase 1 · done" },
  { label: "Local chat, memory and knowledge", state: "Phase 2 · done, see disclosures" },
  { label: "Skills, /learn and /train", state: "Phases 3–4" },
  { label: "Accounts, device pairing, mobile", state: "Phases 5–6" },
  { label: "Encrypted sync and portable .myai export", state: "Phases 7–8" },
];

export default function HomePage() {
  return (
    <div className="space-y-20">
      <section className="text-center">
        <p className="text-sm font-semibold tracking-widest text-accent uppercase">
          {SITE.tagline}
        </p>
        <h1 className="mt-4 text-5xl font-bold tracking-tight">A personal AI you actually own.</h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-fg-muted">{SITE.description}</p>
        <div className="mt-8 flex justify-center gap-3">
          <Link
            href="/download"
            className="rounded-full bg-accent px-6 py-3 font-medium text-accent-fg"
          >
            Download
          </Link>
          <Link href="/privacy" className="rounded-full border border-border px-6 py-3 font-medium">
            Read the privacy promise
          </Link>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        {pillars.map((p) => (
          <div key={p.title} className="rounded-2xl border border-border bg-bg-elevated p-6">
            <h2 className="text-xl font-semibold">{p.title}</h2>
            <p className="mt-2 text-fg-muted">{p.body}</p>
          </div>
        ))}
      </section>

      <section className="rounded-2xl border border-dashed border-border bg-bg-elevated p-6">
        <h2 className="text-xl font-semibold">Read first</h2>
        <p className="mt-2 text-fg-muted">
          Installers are not published yet, local chat has not been confirmed end to end by the
          authors, and the mobile app is a skeleton. The full list is on the{" "}
          <Link href="/disclosures" className="underline">
            disclosures page
          </Link>
          ; the same list is in the repository README.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold">Where the project is</h2>
        <p className="mt-2 text-fg-muted">
          MyAI Academy is built in the open, phase by phase. We say what works today and what does
          not yet.
        </p>
        <ul className="mt-6 divide-y divide-border rounded-2xl border border-border bg-bg-elevated">
          {status.map((s) => (
            <li key={s.label} className="flex items-center justify-between px-6 py-4">
              <span>{s.label}</span>
              <span className="text-sm text-fg-muted">{s.state}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
