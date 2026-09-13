/**
 * A stand-in for the desktop host, over real TLS with a real self-signed certificate.
 *
 * It answers the handful of endpoints the phone uses, with the same status codes the Python
 * service returns — those codes are the contract the client maps onto user-visible states,
 * and they are pinned on the other side by `test_network_access.py`, which drives the real
 * service. What is tested here is the phone's half: that it pins before it speaks, uses its
 * own credential, and reads a revocation for what it is.
 *
 * The certificate is generated per test run and never written to the repository.
 */

import { createHash, X509Certificate } from "node:crypto";
import { createServer, type Server } from "node:https";
import type { AddressInfo } from "node:net";
import selfsigned from "selfsigned";

export interface FakeHost {
  port: number;
  certificateFingerprint: string;
  publicKeyPin: string;
  /** The installation's owner token. The host must refuse this over the network. */
  ownerToken: string;
  /** Codes that have not been used yet. Pairing consumes one. */
  codes: Set<string>;
  /** Tokens issued to devices, and whether each is still valid. */
  revoke(token: string): void;
  close(): Promise<void>;
}

const OWNER_TOKEN = "owner-token-never-leaves-the-desktop";

export async function startFakeHost(): Promise<FakeHost> {
  // P-256 and SHA-256, matching what the host actually mints, so the pin being verified
  // here is computed over the same shape of key.
  const notBefore = new Date();
  const notAfter = new Date(notBefore.getTime() + 24 * 60 * 60 * 1000);
  const pems = await selfsigned.generate([{ name: "commonName", value: "myai-test-host" }], {
    notBeforeDate: notBefore,
    notAfterDate: notAfter,
    keyType: "ec",
    curve: "P-256",
    algorithm: "sha256",
    extensions: [
      { name: "basicConstraints", cA: false },
      {
        name: "subjectAltName",
        altNames: [
          { type: 2, value: "localhost" },
          { type: 7, ip: "127.0.0.1" },
        ],
      },
    ],
  });

  const certificate = new X509Certificate(pems.cert);
  const certificateFingerprint = createHash("sha256").update(certificate.raw).digest("hex");
  const spki = certificate.publicKey.export({ type: "spki", format: "der" });
  const publicKeyPin = `sha256/${createHash("sha256").update(spki).digest("base64")}`;

  const codes = new Set<string>(["12345678"]);
  const issued = new Map<string, { id: string; revoked: boolean }>();
  let nextDevice = 1;

  const server: Server = createServer({ key: pems.private, cert: pems.cert }, (req, res) => {
    const send = (status: number, body: unknown): void => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(body));
    };
    const bearer = (req.headers.authorization ?? "").replace(/^Bearer\s+/i, "");
    const path = (req.url ?? "").split("?")[0] ?? "";

    if (req.method === "POST" && path === "/api/security/pair") {
      const chunks: Buffer[] = [];
      req.on("data", (chunk: Buffer) => chunks.push(chunk));
      req.on("end", () => {
        let body: Record<string, unknown> = {};
        try {
          body = JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<string, unknown>;
        } catch {
          send(400, { detail: "That pairing code is not readable." });
          return;
        }
        const code = String(body.code ?? "");
        if (!codes.delete(code)) {
          send(400, { detail: "That code is wrong, already used, or has expired." });
          return;
        }
        const id = `device-${nextDevice++}`;
        const token = `device-token-${id}`;
        issued.set(token, { id, revoked: false });
        send(201, { device: { id, name: body.name, kind: body.kind }, token });
      });
      return;
    }

    // Everything below needs a credential.
    if (bearer === OWNER_TOKEN) {
      send(403, {
        detail:
          "This installation's own token cannot be used from the network. Pair this device " +
          "for a credential of its own.",
      });
      return;
    }
    const device = issued.get(bearer);
    if (!device || device.revoked) {
      send(401, { detail: "Not authenticated." });
      return;
    }

    if (req.method === "GET" && path === "/api/status") {
      // The same field names `ServiceStatus` serialises, so the client's parsing is
      // exercised against the real shape rather than a convenient one.
      send(200, {
        service_version: "0.1.0",
        ai: "available",
        ai_detail: "A local model is set up and ready.",
        training: "unavailable",
        training_detail: "No skill is being trained.",
        job: null,
        privacy_mode: "strict",
        cloud_uploads: 0,
      });
      return;
    }
    if (req.method === "GET" && path === "/api/security") {
      send(200, { caller_is_owner: false, caller_name: "Phone", active_clients: 1 });
      return;
    }
    // Owner-only surfaces stay owner-only, whoever is asking.
    if (path.startsWith("/api/security/") || path.startsWith("/api/privacy/")) {
      send(403, { detail: "Only this installation's owner can do that." });
      return;
    }
    send(404, { detail: "No such endpoint." });
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));

  return {
    port: (server.address() as AddressInfo).port,
    certificateFingerprint,
    publicKeyPin,
    ownerToken: OWNER_TOKEN,
    codes,
    revoke(token: string) {
      const entry = issued.get(token);
      if (entry) entry.revoked = true;
    },
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}
