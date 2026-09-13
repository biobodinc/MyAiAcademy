# ADR-0015 Reaching the host from a phone

- Status: accepted
- Date: 2026-09-12
- Extends ADR-0003 (loopback-only local API) and ADR-0014 (per-client credentials).

## Context

Phase 6 is the mobile controller: a phone that shows what your AI is doing and can steer
it (§6, §13-§18, §52). Everything before this point has been able to assume the strongest
possible boundary — the service listens on 127.0.0.1, so nothing off this machine can
reach it at all. A phone breaks that assumption by definition.

The usual shortcut is plain HTTP on the local network, on the reasoning that a home network
is "trusted". It is not. Anyone else on that Wi-Fi — a guest, a housemate, a compromised
smart speaker — can read everything on it. For a program whose entire claim is that your
conversations stay yours, sending them across a room in the clear would be the single most
damaging thing it could do.

TLS is therefore not optional. But the ordinary trust model does not apply: no certificate
authority will issue a certificate for `192.168.1.24`, there is no stable hostname, and the
address changes with the network.

## Decision

**A second listener, off by default, HTTPS only, with a certificate the device pins.**

- The loopback listener is untouched: same socket, same owner token, same strict `Host`
  allow-list. Network access is a _separate_ listener the user turns on, and turning it on
  and off is written to the audit log.
- The host mints its own certificate (P-256, `cryptography`), keeps the key owner-only, and
  never sends it anywhere. The pairing QR carries the pins next to the code, so they travel
  together over the air gap of someone looking at their own screen. The device then accepts
  exactly one host — this one — and rejects every other, _including_ one holding a genuine
  certificate from a real authority. Here that is stronger than the web's model, because
  there is no authority that could be persuaded to issue a certificate for this host to
  somebody else.
- **Two pins travel, because they have two different readers.** The certificate's SHA-256
  fingerprint is what a _person_ compares, shown in groups of four on both screens. Every
  pinning implementation a phone can actually use — OkHttp's `CertificatePinner`, TrustKit,
  and the HPKP syntax both inherit — pins something else: the SHA-256 of the DER
  SubjectPublicKeyInfo, base64, written `sha256/…`. Publishing only the first would have
  meant the pin in the QR code could not be handed to any real pinning library, which is a
  thing better discovered now than after a device build exists.
- **The installation token is refused over the network.** The master key stays on the
  machine that owns it. A device pairs, gets a credential of its own, and that credential
  can be revoked on its own. Attempting to use the owner token from the network is a 403
  that says why.
- The `Host` allow-list is relaxed **only** on this listener, because a phone legitimately
  addresses the machine by its address on the network. The loopback listener still refuses
  anything but a loopback `Host`, which is what makes DNS-rebinding attacks fail.
- Which listener a request arrived on is set on the ASGI scope by the listener itself, not
  taken from a header. A header is written by whoever is talking to us; this fact must not
  be forgeable.
- The second listener **answers the ASGI lifespan protocol itself** rather than passing it
  to the application. Without that, a second uvicorn server running the same application
  runs its startup again — a second database engine, a second job manager, and a
  replacement for the shared state the first listener is already using. There is one
  service with two doors, not two services.

## What is built, and what is not

Built and tested against a real TLS socket, on both sides.

On the host: the listener, the certificate, both pins, the refusal of the owner token, the
pairing invite and its QR payload, and the desktop and CLI surfaces for all of it.

In the phone app: the invite parser, the fingerprint comparison, the pairing exchange, the
authenticated calls, revocation, and the credential in the Keychain — driven end to end in
`tests/client.test.ts` against a real HTTPS server with a real self-signed P-256
certificate, through a transport that verifies the pins by hand exactly as a native module
must. The tests hold it to the properties that matter: an impostor's certificate is refused
_before the pairing code is sent_, and the installation's owner token is never what the
phone uses.

**Not built: the connection from a real phone.** The reason is sharper than "React Native
rejects self-signed certificates", and worth recording because it disqualifies the obvious
fix. Pinning does not help: pinning is applied _after_ chain validation, so a certificate
the TrustManager already rejected never reaches the pinner. OkHttp says so outright —
"CertificatePinner cannot be used to pin self-signed certificates if such certificates are
not accepted by TrustManager" — and TrustKit is the same on iOS. Reaching this host
therefore needs a module that trusts this one certificate _and_ verifies it is this one
certificate, together. No off-the-shelf library does both; the runtime-configurable ones do
only the second. A module means a development build, which means a device.

So the app refuses to connect when it cannot pin, and says so on screen in words, with the
Connect button disabled rather than offered and then failed. `src/transport.ts` is the one
seam: a native module registers itself at startup and every screen begins working, with
nothing else to change. Refusing is the designed behaviour, not a gap — an unpinned
fallback would hand the device credential and every message to whatever answered on that
address.

## Consequences

- The strongest claim this project makes — "nothing can reach your AI" — now has an
  exception the user creates deliberately, can see, and can revoke. It is off until they
  turn it on, and the audit log records both.
- Regenerating the certificate invalidates every pin, forcing devices to pair again. That
  is the intended blast radius of "I think something is wrong; reset it".
- A future relayed connection (§18, Phase 7) must not weaken any of this: the same
  credential, the same refusal of the owner token, and end-to-end encryption that the relay
  cannot read.
