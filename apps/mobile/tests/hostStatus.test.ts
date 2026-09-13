/**
 * Reading the host's status is parsing input from the network, so it is tested the way
 * parsers are: mostly with what it must not do. The rule throughout is that anything
 * unrecognised reads as unknown — never as working.
 */
import { describe, expect, it } from "vitest";

import { describeAvailability, parseStatus } from "../src/hostStatus";

const REAL = {
  service_version: "0.1.0",
  ai: "available",
  ai_detail: "A local model is set up and ready.",
  training: "not_configured",
  training_detail: "No skill has a practice set yet.",
  job: { kind: "training", progress: 0.25 },
  privacy_mode: "strict",
  cloud_uploads: 0,
};

describe("parseStatus", () => {
  it("reads what the host actually sends", () => {
    expect(parseStatus(REAL)).toEqual({
      serviceVersion: "0.1.0",
      ai: "available",
      aiDetail: "A local model is set up and ready.",
      training: "not_configured",
      trainingDetail: "No skill has a practice set yet.",
      jobLabel: "training",
      jobProgress: 0.25,
      privacyMode: "strict",
      cloudUploads: 0,
    });
  });

  it.each([
    ["a word we do not know", "brilliant"],
    ["a number", 1],
    ["nothing at all", undefined],
    ["null", null],
  ])("treats %s as unknown rather than as available", (_name, value) => {
    expect(parseStatus({ ...REAL, ai: value }).ai).toBe("unknown");
  });

  it.each([
    ["not an object", "status"],
    ["null", null],
    ["an array", []],
  ])("survives %s without inventing a working AI", (_name, body) => {
    const status = parseStatus(body);
    expect(status.ai).toBe("unknown");
    expect(status.training).toBe("unknown");
    expect(status.aiDetail).toMatch(/did not say/i);
  });

  it("ignores a progress figure that is not a fraction", () => {
    expect(parseStatus({ ...REAL, job: { kind: "x", progress: 7 } }).jobProgress).toBeNull();
    expect(parseStatus({ ...REAL, job: { kind: "x", progress: -1 } }).jobProgress).toBeNull();
    expect(parseStatus({ ...REAL, job: null }).jobLabel).toBeNull();
  });

  it("does not quietly zero an upload count the host reported", () => {
    expect(parseStatus({ ...REAL, cloud_uploads: 3 }).cloudUploads).toBe(3);
  });
});

describe("describeAvailability", () => {
  it("gives every state a face, and only 'available' a green one", () => {
    expect(describeAvailability("available").emoji).toBe("🟢");
    for (const state of ["unavailable", "not_configured", "unknown"] as const) {
      expect(describeAvailability(state).emoji).not.toBe("🟢");
      expect(describeAvailability(state).label).not.toBe("");
    }
  });
});
