/**
 * A pinning transport for Node, so the client can be tested against a real TLS socket.
 *
 * This is the test-suite counterpart of the native module the phone still needs, and it is
 * written to do the same two things in the same order: trust nothing the platform says, and
 * check the presented certificate against the pin *before* the request is written. Nothing
 * here ships in the app — React Native has no `node:tls` — but everything the app does above
 * the socket is exercised through it.
 *
 * It deliberately does not use `ca: [pem]`. Trusting the host certificate as a root would
 * also pass, and would prove nothing about the pin: the point is to verify the digest the
 * QR code carried, which is what a phone will have and a copy of the certificate is not.
 */

import { createHash, X509Certificate } from "node:crypto";
import { request as httpsRequest } from "node:https";
import { connect as tlsConnect, type TLSSocket } from "node:tls";

import {
  CannotPin,
  HostUnreachable,
  type Pin,
  type PinnedRequest,
  type PinnedResponse,
  type PinnedTransport,
} from "../../src/transport";

const IP_ADDRESS = /^[\d.]+$|:/;

/** Constant-time comparison: a pin check is a security decision, not a string lookup. */
function sameDigest(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i += 1) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
}

function verifiedSocket(target: URL, pin: Pin): Promise<TLSSocket> {
  return new Promise((resolve, reject) => {
    const socket = tlsConnect({
      host: target.hostname,
      port: Number(target.port),
      // The platform's own verdict is not used: a self-signed certificate would fail chain
      // validation, which is exactly why pinning has to be done by hand here.
      rejectUnauthorized: false,
      ...(IP_ADDRESS.test(target.hostname) ? {} : { servername: target.hostname }),
    });

    socket.once("secureConnect", () => {
      const der = socket.getPeerCertificate()?.raw;
      if (!der?.length) {
        socket.destroy();
        reject(new CannotPin("Your computer did not present a certificate."));
        return;
      }
      const certificateFingerprint = createHash("sha256").update(der).digest("hex");
      const spki = new X509Certificate(der).publicKey.export({ type: "spki", format: "der" });
      const publicKeyPin = `sha256/${createHash("sha256").update(spki).digest("base64")}`;

      const matches =
        sameDigest(certificateFingerprint, pin.certificateFingerprint) &&
        sameDigest(publicKeyPin, pin.publicKeyPin);
      if (!matches) {
        // Nothing has been written to this socket yet, which is the property that matters:
        // an impostor never sees the credential.
        socket.destroy();
        reject(
          new CannotPin(
            "That is not the computer you paired with. Nothing was sent to it. If you " +
              "reset the certificate on your computer, pair this device again.",
          ),
        );
        return;
      }
      resolve(socket);
    });

    socket.once("error", (error: Error) => reject(new HostUnreachable(error.message)));
  });
}

export function nodePinnedTransport(): PinnedTransport {
  return {
    id: "node-test",
    summary: "Verifies the certificate digest by hand, as a native module would.",
    async request(url, pin, init: PinnedRequest = {}): Promise<PinnedResponse> {
      const target = new URL(url);
      const socket = await verifiedSocket(target, pin);

      return new Promise<PinnedResponse>((resolve, reject) => {
        const req = httpsRequest(
          {
            createConnection: () => socket,
            host: target.hostname,
            port: target.port,
            path: `${target.pathname}${target.search}`,
            method: init.method ?? "GET",
            headers: init.headers ?? {},
          },
          (res) => {
            const chunks: Buffer[] = [];
            res.on("data", (chunk: Buffer) => chunks.push(chunk));
            res.on("end", () => {
              const text = Buffer.concat(chunks).toString("utf8");
              let body: unknown = null;
              try {
                body = text ? JSON.parse(text) : null;
              } catch {
                body = null;
              }
              resolve({ status: res.statusCode ?? 0, body });
            });
          },
        );
        req.once("error", (error: Error) => reject(new HostUnreachable(error.message)));
        if (init.body !== undefined) req.write(init.body);
        req.end();
      });
    },
  };
}
