import { describe, expect, it } from "vitest";

import { headline } from "./model";

const base = {
  service_version: "0.1.0",
  started_at: "2026-09-11T00:00:00Z",
  uptime_seconds: 1,
  internet: "available",
  internet_checked_at: null,
  ai: "not_configured",
  ai_detail: "",
  active_model_id: null,
  loaded_model_id: null,
  training: "unavailable",
  training_detail: "",
  profile_exists: true,
  storage_configured: true,
  onboarding_completed: true,
  privacy_mode: "private",
  cloud_uploads: 0,
  job: null,
} as const;

describe("dashboard headline", () => {
  it("never claims readiness without a model", () => {
    expect(headline(undefined).text).toBe("Checking…");
    expect(headline({ ...base }).text).toBe("No model installed yet");
    expect(headline({ ...base, storage_configured: false }).text).toBe("Storage not set up");
    expect(headline({ ...base, ai: "unavailable" }).tone).toBe("danger");
    expect(headline({ ...base, ai: "available", active_model_id: "qwen" }).text).toBe(
      "Ready · qwen",
    );
    expect(
      headline({
        ...base,
        job: {
          id: "j",
          kind: "learn",
          skill_id: "coding",
          status: "running",
          progress_percent: 40,
        },
      }).text,
    ).toBe("Learning coding · 40%");
  });
});
