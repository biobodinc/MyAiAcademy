/**
 * Reading the host's `/status` into what the phone shows (spec §6, §52).
 *
 * The host answers with an availability word per capability and a sentence explaining it.
 * The phone repeats the host's own sentence rather than inventing its own: the desktop, the
 * CLI and the phone should all give the same answer to "why can't it do that", and the one
 * that is furthest from the machine is the one least entitled to guess.
 *
 * Anything the phone cannot make sense of reads as unknown, never as working.
 */

export type Availability = "available" | "unavailable" | "not_configured" | "unknown";

export interface HostStatus {
  serviceVersion: string;
  ai: Availability;
  aiDetail: string;
  training: Availability;
  trainingDetail: string;
  /** The background job in progress, if any. */
  jobLabel: string | null;
  jobProgress: number | null;
  privacyMode: string;
  cloudUploads: number;
}

const KNOWN: readonly Availability[] = ["available", "unavailable", "not_configured", "unknown"];

function availability(value: unknown): Availability {
  return typeof value === "string" && (KNOWN as readonly string[]).includes(value)
    ? (value as Availability)
    : "unknown";
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" && value ? value : fallback;
}

export function parseStatus(body: unknown): HostStatus {
  const data = (typeof body === "object" && body !== null ? body : {}) as Record<string, unknown>;
  const job = (typeof data.job === "object" && data.job !== null ? data.job : {}) as Record<
    string,
    unknown
  >;
  const progress = typeof job.progress === "number" ? job.progress : null;

  return {
    serviceVersion: text(data.service_version, "unknown"),
    ai: availability(data.ai),
    aiDetail: text(data.ai_detail, "Your computer did not say."),
    training: availability(data.training),
    trainingDetail: text(data.training_detail, "Your computer did not say."),
    jobLabel: text(job.kind) || null,
    jobProgress: progress !== null && progress >= 0 && progress <= 1 ? progress : null,
    privacyMode: text(data.privacy_mode, "unknown"),
    cloudUploads: typeof data.cloud_uploads === "number" ? data.cloud_uploads : 0,
  };
}

/** A dot and a phrase for an availability, for a screen that has one line to say it in. */
export function describeAvailability(value: Availability): { emoji: string; label: string } {
  switch (value) {
    case "available":
      return { emoji: "🟢", label: "Ready" };
    case "unavailable":
      return { emoji: "🔴", label: "Not available" };
    case "not_configured":
      return { emoji: "⚪", label: "Not set up yet" };
    case "unknown":
      return { emoji: "🟡", label: "Unknown" };
  }
}
