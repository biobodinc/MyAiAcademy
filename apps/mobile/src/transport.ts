/**
 * The one place that decides whether this phone may open a connection at all (spec §52, §55).
 *
 * Why this file exists
 * --------------------
 *
 * The host presents a certificate it signed itself, and the phone is supposed to pin it. On
 * a phone, neither half of that is free:
 *
 * 1. React Native's `fetch` goes through the platform TLS stack — OkHttp on Android,
 *    NSURLSession on iOS. Both reject a self-signed certificate during chain validation,
 *    before any application code runs.
 * 2. Pinning does not rescue it. OkHttp's own documentation is explicit: "CertificatePinner
 *    cannot be used to pin self-signed certificates if such certificates are not accepted by
 *    TrustManager." Pinning is an *extra* check applied after the chain validates, not a
 *    replacement for it. TrustKit behaves the same way on iOS.
 *
 * So reaching this host needs a native module that does both things together: trust this one
 * certificate, and verify it is this one certificate. No off-the-shelf library does that —
 * the runtime-configurable ones (react-native-ssl-public-key-pinning and friends) do step 2
 * only — and a native module means a development build, not Expo Go.
 *
 * The wrong response would be to fall back to an unpinned connection "for now". That would
 * send the device credential and every message to whatever answered on that address. So the
 * app does the other thing: with no pinning transport registered, it **refuses to connect**
 * and says why. Refusing is a feature here, and the tests hold it to that.
 *
 * When the native module exists it calls {@link registerPinnedTransport} once at startup and
 * every screen starts working. Nothing else has to change. The test suite registers a Node
 * implementation and exercises the whole protocol against a real TLS server, so what is
 * unproven is exactly one module wide — not the app.
 */

/** The two pins from a pairing invite. Both travel in the QR code. */
export interface Pin {
  /** SHA-256 of the certificate, lower-case hex. */
  certificateFingerprint: string;
  /** `sha256/<base64>` over the DER SubjectPublicKeyInfo. */
  publicKeyPin: string;
}

export interface PinnedRequest {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  signal?: AbortSignal;
}

export interface PinnedResponse {
  status: number;
  /** Parsed JSON body, or `null` when the host sent nothing (or sent something unreadable). */
  body: unknown;
}

/**
 * A transport that can verify it is talking to one specific host and no other.
 *
 * A conforming implementation MUST fail the connection when the presented certificate does
 * not match `pin`, and MUST do so before sending any part of the request — the credential in
 * the Authorization header is exactly what an impostor would be trying to collect.
 */
export interface PinnedTransport {
  /** Short identifier for logs and the "how am I connecting" line in the UI. */
  readonly id: string;
  /** One sentence a non-technical user can read about how this connection is verified. */
  readonly summary: string;
  request(url: string, pin: Pin, init?: PinnedRequest): Promise<PinnedResponse>;
}

/** Thrown when the app cannot verify the host, and therefore will not talk to it. */
export class CannotPin extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CannotPin";
  }
}

/** Thrown when the host could not be reached at all. */
export class HostUnreachable extends Error {
  constructor(message: string) {
    super(message);
    this.name = "HostUnreachable";
  }
}

const REFUSING: PinnedTransport = {
  id: "none",
  summary:
    "This build cannot verify your computer's identity, so it will not connect. Pairing " +
    "needs a development build of the app; Expo Go cannot pin a certificate.",
  request() {
    return Promise.reject(
      new CannotPin(
        "This build cannot check that it is really your computer answering, so it will not " +
          "send your credential. Install a development build to pair.",
      ),
    );
  },
};

let registered: PinnedTransport | null = null;

/**
 * Install the transport that does the pinning. Called once, at startup, by the native
 * module. Passing `null` restores the refusing transport, which is what tests reset to.
 */
export function registerPinnedTransport(transport: PinnedTransport | null): void {
  registered = transport;
}

/** The transport in force. Never null: with nothing registered, connections are refused. */
export function pinnedTransport(): PinnedTransport {
  return registered ?? REFUSING;
}

/** Whether this build can actually reach a host, and what to tell the user if it cannot. */
export function transportStatus(): { canConnect: boolean; summary: string } {
  const transport = pinnedTransport();
  return { canConnect: transport !== REFUSING, summary: transport.summary };
}
