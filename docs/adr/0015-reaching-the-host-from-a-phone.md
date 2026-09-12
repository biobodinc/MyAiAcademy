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
  never sends it anywhere. The pairing QR carries the certificate's SHA-256 fingerprint
  next to the code, so the two travel together over the air gap of someone looking at their
  own screen. The device then accepts exactly one certificate — this host's — and rejects
  every other, _including_ a genuine one from a real authority. Here that is stronger than
  the web's model, because there is no authority that could be persuaded to issue a
  certificate for this host to somebody else.
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

Built and tested against a real TLS socket: the listener, the certificate, the pin, the
refusal of the owner token, the pairing invite and its QR payload, and the desktop and CLI
surfaces for all of it. The mobile app has the pairing-invite parser and the fingerprint
comparison, tested, including the malformed and expired payloads it must refuse.

**Not built: the phone actually connecting.** React Native's networking uses the platform
TLS stack, which will reject a self-signed certificate, and pinning requires a native
module and therefore a development build. That is not something that can be written
honestly without a device to run it on: it would be code that has never once made a
connection. The phone app therefore still reports itself as unpaired, and the mobile
disclosure says exactly this rather than implying a working app is a build away.

## Consequences

- The strongest claim this project makes — "nothing can reach your AI" — now has an
  exception the user creates deliberately, can see, and can revoke. It is off until they
  turn it on, and the audit log records both.
- Regenerating the certificate invalidates every pin, forcing devices to pair again. That
  is the intended blast radius of "I think something is wrong; reset it".
- A future relayed connection (§18, Phase 7) must not weaken any of this: the same
  credential, the same refusal of the owner token, and end-to-end encryption that the relay
  cannot read.
