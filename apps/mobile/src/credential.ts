/**
 * The credential this device holds for one host, and where it is kept (spec §55).
 *
 * What is stored is deliberately small: the address to reach, the pins to verify, and a
 * token that belongs to this device alone. The installation's owner token is never here —
 * the host refuses it over the network, and a phone is never given one. Revoking this device
 * on the desktop makes the token below useless without touching any other device.
 *
 * What comes back out of the keychain is treated as input, not as something we wrote. A
 * value that does not parse is discarded and the device simply reads as unpaired, which is
 * recoverable by pairing again; trusting a half-valid credential would not be.
 */

import type { Pin } from "./transport";

export interface DeviceCredential {
  hostName: string;
  /** The base URL that answered during pairing, e.g. `https://192.168.1.24:41338/api`. */
  baseUrl: string;
  pin: Pin;
  deviceId: string;
  /** This device's own bearer token. Never the installation's owner token. */
  token: string;
  pairedAt: string;
}

/** Where a credential lives between launches. The app uses the keychain; tests use memory. */
export interface CredentialStore {
  read(): Promise<DeviceCredential | null>;
  write(credential: DeviceCredential): Promise<void>;
  clear(): Promise<void>;
}

const FINGERPRINT = /^[0-9a-f]{64}$/;
const PUBLIC_KEY_PIN = /^sha256\/[A-Za-z0-9+/]{43}=$/;

/** Parse a stored credential, returning null for anything that is not wholly intact. */
export function parseCredential(raw: string | null): DeviceCredential | null {
  if (!raw) return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) return null;
  const body = data as Record<string, unknown>;
  const pin = (body.pin ?? {}) as Record<string, unknown>;

  const text = (value: unknown): string => (typeof value === "string" ? value : "");
  const credential: DeviceCredential = {
    hostName: text(body.hostName),
    baseUrl: text(body.baseUrl),
    pin: {
      certificateFingerprint: text(pin.certificateFingerprint).toLowerCase(),
      publicKeyPin: text(pin.publicKeyPin),
    },
    deviceId: text(body.deviceId),
    token: text(body.token),
    pairedAt: text(body.pairedAt),
  };

  const usable =
    credential.hostName !== "" &&
    credential.baseUrl.startsWith("https://") &&
    FINGERPRINT.test(credential.pin.certificateFingerprint) &&
    PUBLIC_KEY_PIN.test(credential.pin.publicKeyPin) &&
    credential.deviceId !== "" &&
    credential.token !== "";
  return usable ? credential : null;
}

export function serialiseCredential(credential: DeviceCredential): string {
  return JSON.stringify(credential);
}

/** An in-memory store, for tests and for a build with no secure storage available. */
export function memoryStore(initial: DeviceCredential | null = null): CredentialStore {
  let held = initial;
  return {
    read: () => Promise.resolve(held),
    write: (credential) => {
      held = credential;
      return Promise.resolve();
    },
    clear: () => {
      held = null;
      return Promise.resolve();
    },
  };
}
