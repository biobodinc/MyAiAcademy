/**
 * Talking to the host: pairing once, then acting as this device (spec §52, §55).
 *
 * Every request goes through a {@link PinnedTransport}, so there is no path through this
 * file that reaches the network without the host being verified first. That is the point of
 * routing it this way rather than calling `fetch` here: an unpinned request is not something
 * a later edit can add by accident.
 *
 * The failures are modelled separately because they mean different things to the person
 * holding the phone. A revoked credential is not a network problem and must not be retried;
 * being refused a privilege is not a bug, it is the owner boundary working.
 */

import type { PairingInvite } from "./pairing";
import { candidateUrls } from "./pairing";
import type { DeviceCredential } from "./credential";
import {
  CannotPin,
  HostUnreachable,
  type Pin,
  type PinnedRequest,
  type PinnedTransport,
} from "./transport";

/** The device's credential is no longer valid: revoked on the desktop, or the host reset. */
export class Revoked extends Error {
  constructor() {
    super("This device is no longer paired. Pair it again from your computer.");
    this.name = "Revoked";
  }
}

/** The host understood, and said no. A phone is a client, not the owner of the install. */
export class NotPermitted extends Error {
  constructor(detail: string) {
    super(detail || "Your computer did not allow that from this device.");
    this.name = "NotPermitted";
  }
}

/** Pairing itself failed — a wrong, used or expired code. */
export class PairingRefused extends Error {
  constructor(detail: string) {
    super(detail || "Your computer refused that pairing code.");
    this.name = "PairingRefused";
  }
}

function detailOf(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null) {
    const detail = (body as Record<string, unknown>).detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return fallback;
}

/**
 * Exchange a scanned invite for this device's own credential.
 *
 * The invite may list several addresses (a machine can be on Wi-Fi and Ethernet at once), so
 * each is tried in turn. A host that cannot be verified is not "tried harder": {@link
 * CannotPin} stops the whole attempt, because every remaining address would be reached by
 * the same unverifiable means.
 */
export async function pair(
  invite: PairingInvite,
  deviceName: string,
  transport: PinnedTransport,
): Promise<DeviceCredential> {
  const pin: Pin = {
    certificateFingerprint: invite.certificateFingerprint,
    publicKeyPin: invite.publicKeyPin,
  };
  let lastUnreachable: Error | null = null;

  for (const baseUrl of candidateUrls(invite)) {
    let response;
    try {
      response = await transport.request(`${baseUrl}/security/pair`, pin, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: invite.code, name: deviceName, kind: "mobile" }),
      });
    } catch (error) {
      if (error instanceof CannotPin) throw error;
      lastUnreachable = error instanceof Error ? error : new HostUnreachable(String(error));
      continue;
    }

    if (response.status === 201) {
      const body = (response.body ?? {}) as Record<string, unknown>;
      const device = (body.device ?? {}) as Record<string, unknown>;
      const token = typeof body.token === "string" ? body.token : "";
      const deviceId = typeof device.id === "string" ? device.id : "";
      if (!token || !deviceId) {
        throw new PairingRefused("Your computer's reply to pairing was not readable.");
      }
      return {
        hostName: invite.hostName,
        baseUrl,
        pin,
        deviceId,
        token,
        pairedAt: new Date().toISOString(),
      };
    }
    // The host answered, so the address is right. A refusal here is final: the code is
    // single-use, and trying the next address would only burn it against a host that
    // already said no.
    throw new PairingRefused(detailOf(response.body, "That pairing code was not accepted."));
  }

  throw (
    lastUnreachable ??
    new HostUnreachable(
      `${invite.hostName} did not answer. Check both devices are on the same network.`,
    )
  );
}

/** An authenticated connection to one host, as one device. */
export class HostClient {
  constructor(
    private readonly credential: DeviceCredential,
    private readonly transport: PinnedTransport,
  ) {}

  /** What the AI is doing right now. */
  status(): Promise<unknown> {
    return this.call("/status");
  }

  /** What this device is allowed to do, as the host sees it. */
  security(): Promise<unknown> {
    return this.call("/security");
  }

  /**
   * Any endpoint, authenticated as this device and pinned to this host.
   *
   * The narrower methods above are the ones screens use; this is what they are built from,
   * and the seam through which later phases add endpoints without reopening the pinning
   * question. Owner-only endpoints raise {@link NotPermitted} here, which is the boundary
   * working rather than a failure to handle.
   */
  async call(path: string, init: PinnedRequest = { method: "GET" }): Promise<unknown> {
    const response = await this.transport.request(`${this.credential.baseUrl}${path}`, this.pin, {
      ...init,
      headers: { ...init.headers, Authorization: `Bearer ${this.credential.token}` },
    });
    if (response.status === 401) throw new Revoked();
    if (response.status === 403) throw new NotPermitted(detailOf(response.body, ""));
    if (response.status >= 400) {
      throw new HostUnreachable(detailOf(response.body, `Your computer returned an error.`));
    }
    return response.body;
  }

  private get pin(): Pin {
    return this.credential.pin;
  }
}
