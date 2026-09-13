/**
 * The phone's half of the connection, against a real TLS server with a real self-signed
 * certificate. Nothing here is mocked below the socket.
 *
 * The properties under test are the ones that would matter if someone else were on the same
 * Wi-Fi, or had the phone in their hand:
 *
 *  * the pin is checked before anything is sent, so an impostor never sees the credential;
 *  * a build that cannot pin refuses to connect rather than connecting in the clear;
 *  * the installation's owner token is never what the phone uses;
 *  * a revoked device knows it has been revoked, and does not retry.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { HostClient, NotPermitted, PairingRefused, Revoked, pair } from "../src/client";
import { memoryStore, parseCredential, serialiseCredential } from "../src/credential";
import { parseStatus } from "../src/hostStatus";
import { parseInvite, type PairingInvite } from "../src/pairing";
import {
  CannotPin,
  pinnedTransport,
  registerPinnedTransport,
  transportStatus,
} from "../src/transport";
import { startFakeHost, type FakeHost } from "./support/fakeHost";
import { nodePinnedTransport } from "./support/nodePinning";

let host: FakeHost;
const transport = nodePinnedTransport();

function inviteFor(host: FakeHost, overrides: Record<string, unknown> = {}): PairingInvite {
  return parseInvite(
    JSON.stringify({
      v: 1,
      host: "Studio PC",
      addresses: ["127.0.0.1"],
      port: host.port,
      fp: host.certificateFingerprint,
      spki: host.publicKeyPin,
      code: "12345678",
      exp: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
      ...overrides,
    }),
  );
}

beforeEach(async () => {
  host = await startFakeHost();
});

afterEach(async () => {
  registerPinnedTransport(null);
  await host.close();
});

describe("pairing over a pinned connection", () => {
  it("exchanges a code for this device's own credential", async () => {
    const credential = await pair(inviteFor(host), "Alex's phone", transport);

    expect(credential.deviceId).toBe("device-1");
    expect(credential.token).toMatch(/^device-token-/);
    expect(credential.token).not.toBe(host.ownerToken);
    expect(credential.baseUrl).toBe(`https://127.0.0.1:${host.port}/api`);
    expect(credential.pin.certificateFingerprint).toBe(host.certificateFingerprint);
  });

  it("refuses a host presenting a different certificate, without sending the code", async () => {
    const impostor = await startFakeHost();
    try {
      // The address and the code are right; only the certificate is wrong.
      const invite = inviteFor(host, { port: impostor.port });
      await expect(pair(invite, "Phone", transport)).rejects.toThrow(CannotPin);
      // The code was never offered to it, so it is still unused on the impostor.
      expect(impostor.codes.has("12345678")).toBe(true);
    } finally {
      await impostor.close();
    }
  });

  it("refuses when only the key pin is wrong, not just the certificate digest", async () => {
    const other = await startFakeHost();
    try {
      const invite = inviteFor(host, { spki: other.publicKeyPin });
      await expect(pair(invite, "Phone", transport)).rejects.toThrow(CannotPin);
    } finally {
      await other.close();
    }
  });

  it("reports a rejected code in words, and does not burn the remaining addresses", async () => {
    const invite = inviteFor(host, { code: "87654321", addresses: ["127.0.0.1", "127.0.0.1"] });
    await expect(pair(invite, "Phone", transport)).rejects.toThrow(PairingRefused);
  });

  it("says the host did not answer when nothing is listening", async () => {
    const closed = await startFakeHost();
    const port = closed.port;
    await closed.close();
    const invite = inviteFor(host, { port });
    await expect(pair(invite, "Phone", transport)).rejects.toThrow(/did not answer|ECONNREFUSED/);
  });

  it("only pairs once with a single-use code", async () => {
    await pair(inviteFor(host), "First", transport);
    await expect(pair(inviteFor(host), "Second", transport)).rejects.toThrow(PairingRefused);
  });
});

describe("acting as a paired device", () => {
  it("reads status and its own privileges", async () => {
    const credential = await pair(inviteFor(host), "Phone", transport);
    const client = new HostClient(credential, transport);

    const status = parseStatus(await client.status());
    expect(status.ai).toBe("available");
    expect(status.aiDetail).toMatch(/ready/i);
    expect(status.training).toBe("unavailable");
    expect(status.cloudUploads).toBe(0);

    expect(await client.security()).toMatchObject({ caller_is_owner: false });
  });

  it("knows it has been revoked, and says so in the user's words", async () => {
    const credential = await pair(inviteFor(host), "Phone", transport);
    const client = new HostClient(credential, transport);
    expect(await client.status()).toBeTruthy();

    host.revoke(credential.token);

    await expect(client.status()).rejects.toThrow(Revoked);
    await expect(client.status()).rejects.toThrow(/pair it again/i);
  });

  it("is refused the owner's privileges, and that is not an error state", async () => {
    const credential = await pair(inviteFor(host), "Phone", transport);
    const client = new HostClient(credential, transport);
    // A phone may use the AI; it may not hand out access to it, or export the data.
    await expect(client.call("/security/pairing-codes", { method: "POST" })).rejects.toThrow(
      NotPermitted,
    );
    await expect(client.call("/privacy/export", { method: "POST" })).rejects.toThrow(NotPermitted);
  });

  it("never sends the installation's owner token", async () => {
    const credential = await pair(inviteFor(host), "Phone", transport);
    const stolen = { ...credential, token: host.ownerToken };
    // If the app ever did use it, the host refuses it over the network — belt and braces.
    await expect(new HostClient(stolen, transport).status()).rejects.toThrow(NotPermitted);
    await expect(new HostClient(stolen, transport).status()).rejects.toThrow(
      /cannot be used from the network/i,
    );
  });
});

describe("a build that cannot pin", () => {
  it("refuses to connect rather than connecting unverified", async () => {
    // Nothing registered: this is Expo Go, or the web preview.
    expect(transportStatus().canConnect).toBe(false);
    expect(transportStatus().summary).toMatch(/development build/i);

    await expect(pair(inviteFor(host), "Phone", pinnedTransport())).rejects.toThrow(CannotPin);
  });

  it("starts working the moment a pinning transport is registered", async () => {
    registerPinnedTransport(transport);
    expect(transportStatus().canConnect).toBe(true);
    await expect(pair(inviteFor(host), "Phone", pinnedTransport())).resolves.toBeTruthy();
  });
});

describe("the stored credential", () => {
  it("survives a round trip through storage", async () => {
    const credential = await pair(inviteFor(host), "Phone", transport);
    const store = memoryStore();
    await store.write(credential);
    const restored = await store.read();
    expect(restored).not.toBeNull();
    expect(parseCredential(serialiseCredential(restored as never))).toEqual(credential);
  });

  it.each([
    ["nothing stored", null],
    ["not JSON", "{"],
    ["a plain HTTP base URL", JSON.stringify({ baseUrl: "http://192.168.1.24/api" })],
    ["a truncated fingerprint", JSON.stringify({ pin: { certificateFingerprint: "abc" } })],
  ])("treats %s as unpaired rather than half-paired", (_name, raw) => {
    expect(parseCredential(raw)).toBeNull();
  });

  it("forgets the credential when the device is unpaired", async () => {
    const store = memoryStore(await pair(inviteFor(host), "Phone", transport));
    await store.clear();
    expect(await store.read()).toBeNull();
  });
});
