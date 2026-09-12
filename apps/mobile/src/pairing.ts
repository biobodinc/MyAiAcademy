/**
 * Reading a pairing invite, and knowing what the phone may do with it (spec §52, §55).
 *
 * The QR code carries the host's address, the certificate fingerprint to pin, and a code
 * that works once. Parsing it is the first thing that happens after a scan, so it is
 * written to reject anything malformed loudly rather than to be generous: a QR code is
 * data from outside, and a "helpful" parser here would be a way in.
 *
 * The fingerprint is the part that matters. Once pinned, the phone accepts exactly one
 * certificate — this host's — and no certificate authority can change that.
 */

/** How long a scanned invite is worth trying, regardless of what it claims. */
export const MAX_INVITE_LIFETIME_MS = 15 * 60 * 1000;

export interface PairingInvite {
  version: number;
  hostName: string;
  addresses: string[];
  port: number;
  certificateFingerprint: string;
  code: string;
  expiresAt: Date;
}

export class InvalidInvite extends Error {}

const FINGERPRINT = /^[0-9a-f]{64}$/;
const CODE = /^\d{6,12}$/;

/** Parse the JSON payload from a scanned QR code. Throws {@link InvalidInvite}. */
export function parseInvite(raw: string, now: Date = new Date()): PairingInvite {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new InvalidInvite("That QR code is not a MyAI pairing code.");
  }
  if (typeof data !== "object" || data === null) {
    throw new InvalidInvite("That QR code is not a MyAI pairing code.");
  }
  const body = data as Record<string, unknown>;

  if (body.v !== 1) {
    throw new InvalidInvite(
      "This pairing code was made by a different version of MyAI Academy. Update both and try again.",
    );
  }
  const fingerprint = typeof body.fp === "string" ? body.fp.toLowerCase() : "";
  if (!FINGERPRINT.test(fingerprint)) {
    throw new InvalidInvite("That pairing code is missing the certificate to trust.");
  }
  const code = typeof body.code === "string" ? body.code.trim() : "";
  if (!CODE.test(code)) {
    throw new InvalidInvite("That pairing code is not readable.");
  }
  const port = typeof body.port === "number" ? body.port : NaN;
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new InvalidInvite("That pairing code does not say how to reach your computer.");
  }
  const addresses = Array.isArray(body.addresses)
    ? body.addresses.filter((a): a is string => typeof a === "string" && a.length > 0)
    : [];
  if (addresses.length === 0) {
    throw new InvalidInvite("That pairing code does not say how to reach your computer.");
  }
  const expiresAt = typeof body.exp === "string" ? new Date(body.exp) : new Date(NaN);
  if (Number.isNaN(expiresAt.getTime())) {
    throw new InvalidInvite("That pairing code does not say when it expires.");
  }
  if (expiresAt.getTime() <= now.getTime()) {
    throw new InvalidInvite("That pairing code has expired. Make a new one on your computer.");
  }
  if (expiresAt.getTime() - now.getTime() > MAX_INVITE_LIFETIME_MS) {
    // A code claiming to live for a week is not one we made.
    throw new InvalidInvite("That pairing code claims to last too long to be genuine.");
  }

  return {
    version: 1,
    hostName: typeof body.host === "string" && body.host ? body.host : "Your computer",
    addresses,
    port,
    certificateFingerprint: fingerprint,
    code,
    expiresAt,
  };
}

/** The addresses to try, in order: a phone is usually on the same network as the host. */
export function candidateUrls(invite: PairingInvite): string[] {
  return invite.addresses.map((address) => {
    const host = address.includes(":") ? `[${address}]` : address;
    return `https://${host}:${invite.port}/api`;
  });
}

/** Compare a certificate fingerprint with the pinned one, case- and format-insensitively. */
export function fingerprintMatches(pinned: string, seen: string): boolean {
  const normalise = (value: string) => value.replace(/[^0-9a-fA-F]/g, "").toLowerCase();
  const a = normalise(pinned);
  const b = normalise(seen);
  if (a.length !== 64 || b.length !== 64) return false;
  // Length-constant comparison: this is a security decision, not a string lookup.
  let difference = 0;
  for (let i = 0; i < a.length; i += 1) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
}
