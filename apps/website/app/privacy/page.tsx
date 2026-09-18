import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy" };

const stays = [
  "Conversations and memories",
  "Personal files and knowledge documents",
  "Training datasets you add",
  "Model weights, adapters and checkpoints",
  "Personality configuration and projects",
  "API keys for any external provider you choose to add",
];

const may = [
  "Software updates and public skill or model metadata (downloads, not uploads)",
  "Account authentication, if you choose to sign in (Phase 5)",
  "Device registration and pairing coordination (Phase 5–6)",
  "End-to-end encrypted synchronisation blobs the service cannot read (Phase 7, opt-in)",
  "Community contributions you explicitly select, category by category (opt-in, revocable)",
];

export default function PrivacyPage() {
  return (
    <article className="prose max-w-3xl">
      <h1 className="display text-4xl sm:text-5xl">Privacy promise</h1>
      <p className="mt-4 text-base text-fg-muted sm:text-lg">
        If you do not opt into sharing, MyAI Academy does not intentionally transmit your private AI
        data to MyAI Academy servers. External services you choose to connect are a separate matter
        and are always disclosed.
      </p>

      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">
        Stays on your devices by default
      </h2>
      <ul className="mt-3 list-disc space-y-1 pl-6">
        {stays.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>

      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">
        What the cloud may ever handle
      </h2>
      <ul className="mt-3 list-disc space-y-1 pl-6">
        {may.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>

      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">Today, concretely</h2>
      <p className="mt-3">
        The current desktop build contains no account, sync or upload code paths. Its only outbound
        network activity is a reachability check (a TCP connection with no payload) used to display
        online/offline status. The app shows this in its Privacy Center and records
        security-relevant events in a local activity log.
      </p>

      <h2 className="display mt-10 text-2xl sm:mt-12 sm:text-3xl">Honest limits</h2>
      <p className="mt-3">
        Anonymisation is never a guarantee of perfect privacy, which is why contribution is off by
        default and granular when on. If our servers disappear, your local AI keeps working; only
        cloud-dependent features stop.
      </p>
    </article>
  );
}
