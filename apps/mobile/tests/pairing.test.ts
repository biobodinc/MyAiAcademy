/**
 * A scanned QR code is data from outside the app, so the parser is tested the way an
 * input parser should be: mostly with the things it must refuse.
 */
import { describe, expect, it } from "vitest";

import {
  candidateUrls,
  fingerprintGroups,
  fingerprintMatches,
  InvalidInvite,
  parseInvite,
  type PairingInvite,
} from "../src/pairing";

const FINGERPRINT = "a".repeat(64);
/** base64 of a 32-byte digest: 43 characters and one '='. */
const KEY_PIN = `sha256/${"B".repeat(43)}=`;
const NOW = new Date("2026-09-12T12:00:00Z");

function payload(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    v: 1,
    host: "Studio PC",
    addresses: ["192.168.1.24"],
    port: 41338,
    fp: FINGERPRINT,
    spki: KEY_PIN,
    code: "12345678",
    exp: new Date(NOW.getTime() + 5 * 60 * 1000).toISOString(),
    ...overrides,
  });
}

describe("parseInvite", () => {
  it("reads a genuine invite", () => {
    const invite = parseInvite(payload(), NOW);
    expect(invite).toMatchObject<Partial<PairingInvite>>({
      version: 1,
      hostName: "Studio PC",
      port: 41338,
      code: "12345678",
      certificateFingerprint: FINGERPRINT,
      publicKeyPin: KEY_PIN,
    });
    expect(invite.addresses).toEqual(["192.168.1.24"]);
    expect(invite.expiresAt.getTime()).toBeGreaterThan(NOW.getTime());
  });

  it("accepts an upper-case fingerprint, since people retype them", () => {
    expect(
      parseInvite(payload({ fp: FINGERPRINT.toUpperCase() }), NOW).certificateFingerprint,
    ).toBe(FINGERPRINT);
  });

  it.each([
    ["not JSON at all", "hello there"],
    ["a JSON value that is not an object", "42"],
    ["a payload from another version", payload({ v: 2 })],
    ["no fingerprint", payload({ fp: undefined })],
    ["a fingerprint that is the wrong length", payload({ fp: "abc" })],
    ["a fingerprint that is not hexadecimal", payload({ fp: "z".repeat(64) })],
    ["no key pin", payload({ spki: undefined })],
    ["a key pin under another hash", payload({ spki: `sha1/${"B".repeat(43)}=` })],
    ["a key pin of the wrong length", payload({ spki: `sha256/${"B".repeat(20)}=` })],
    ["a bare key pin with no algorithm", payload({ spki: `${"B".repeat(43)}=` })],
    ["no code", payload({ code: undefined })],
    ["a code that is not digits", payload({ code: "letmein" })],
    ["no address", payload({ addresses: [] })],
    ["a port out of range", payload({ port: 99999 })],
    ["a port that is not a number", payload({ port: "41338" })],
    ["no expiry", payload({ exp: undefined })],
    ["an expiry that is not a date", payload({ exp: "soon" })],
  ])("refuses %s", (_name, raw) => {
    expect(() => parseInvite(raw, NOW)).toThrow(InvalidInvite);
  });

  it("refuses an invite that has already expired", () => {
    const expired = payload({ exp: new Date(NOW.getTime() - 1000).toISOString() });
    expect(() => parseInvite(expired, NOW)).toThrow(/expired/i);
  });

  it("refuses an invite claiming to last far longer than we ever issue", () => {
    const forever = payload({ exp: new Date(NOW.getTime() + 7 * 24 * 3600 * 1000).toISOString() });
    expect(() => parseInvite(forever, NOW)).toThrow(/genuine/i);
  });

  it("falls back to a neutral host name rather than failing", () => {
    expect(parseInvite(payload({ host: undefined }), NOW).hostName).toBe("Your computer");
  });
});

describe("candidateUrls", () => {
  it("builds an HTTPS URL per address, never plain HTTP", () => {
    const invite = parseInvite(payload({ addresses: ["192.168.1.24", "10.0.0.5"] }), NOW);
    expect(candidateUrls(invite)).toEqual([
      "https://192.168.1.24:41338/api",
      "https://10.0.0.5:41338/api",
    ]);
  });

  it("brackets an IPv6 address so the port is still readable", () => {
    const invite = parseInvite(payload({ addresses: ["fe80::1"] }), NOW);
    expect(candidateUrls(invite)).toEqual(["https://[fe80::1]:41338/api"]);
  });
});

describe("fingerprintGroups", () => {
  it("groups the fingerprint exactly as the desktop shows it, so the two can be compared", () => {
    const groups = fingerprintGroups(FINGERPRINT).split(" ");
    expect(groups).toHaveLength(16);
    expect(groups.every((g) => g.length === 4)).toBe(true);
    expect(groups.join("").toLowerCase()).toBe(FINGERPRINT);
  });
});

describe("fingerprintMatches", () => {
  it("matches the same fingerprint however it is written", () => {
    const spaced = "AAAA AAAA ".repeat(8).trim().replace(/\s+$/, "");
    expect(fingerprintMatches(FINGERPRINT, FINGERPRINT.toUpperCase())).toBe(true);
    expect(fingerprintMatches(FINGERPRINT, spaced.replace(/\s/g, ""))).toBe(true);
  });

  it("rejects a different certificate, including one that differs by a single character", () => {
    expect(fingerprintMatches(FINGERPRINT, "b" + "a".repeat(63))).toBe(false);
    expect(fingerprintMatches(FINGERPRINT, "a".repeat(63))).toBe(false);
    expect(fingerprintMatches("", FINGERPRINT)).toBe(false);
  });
});
