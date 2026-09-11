import type { ServiceStatus } from "@myai/api-client";

import type { Tone } from "../../components/ui";

/** The single headline the spec asks for ("Current status: 🟢 Ready"), derived honestly. */
export function headline(status: ServiceStatus | undefined): { tone: Tone; text: string } {
  if (!status) return { tone: "muted", text: "Checking…" };
  if (status.job) {
    const verb = status.job.kind === "learn" ? "Learning" : "Evaluating";
    return {
      tone: status.job.status === "paused" ? "warning" : "info",
      text: `${verb} ${status.job.skill_id} · ${status.job.progress_percent}%`,
    };
  }
  if (status.ai === "available") {
    return { tone: "success", text: `Ready · ${status.active_model_id ?? "model installed"}` };
  }
  if (status.ai === "unavailable") return { tone: "danger", text: "Inference runtime missing" };
  if (!status.storage_configured) return { tone: "warning", text: "Storage not set up" };
  return { tone: "warning", text: "No model installed yet" };
}
