# @myai/mobile

Expo / React Native app for iOS and Android. The phone is an **authenticated controller**
for the user's desktop AI (spec §6, §52), never a second AI.

## Seeing it, quickly

```bash
pnpm install
pnpm --filter @myai/mobile web      # opens in a browser; fastest by a distance
pnpm --filter @myai/mobile start    # dev server; press w / a / i, or scan with Expo Go
pnpm --filter @myai/mobile test     # 59 tests, including the client against real TLS
pnpm --filter @myai/mobile typecheck
```

The **web** target is the quick look: the whole UI renders, and the pairing screen will read
and validate a real pairing code. **Expo Go** gets you the same on a real phone. Neither can
actually pair — see below — and the app says so on screen rather than failing at the point
of connection.

## What works, and what does not

Built and tested:

- reading a pairing invite, including every malformed and expired payload it must refuse;
- comparing the certificate fingerprint, shown in the same groups the desktop shows;
- the pairing exchange, the authenticated calls, and revocation — all exercised against a
  real TLS server with a real self-signed P-256 certificate in `tests/client.test.ts`;
- the credential in the Keychain / Keystore, and the refusal to keep one anywhere less safe.

**Not built: the connection from a real phone.** It needs a native module, and here is
precisely why, because the reason is not obvious:

1. React Native's `fetch` uses the platform TLS stack. Both OkHttp (Android) and
   NSURLSession (iOS) reject a self-signed certificate during chain validation, before any
   application code runs.
2. Pinning does not fix that. OkHttp's documentation is explicit — _"CertificatePinner
   cannot be used to pin self-signed certificates if such certificates are not accepted by
   TrustManager"_ — because pinning is an extra check applied **after** the chain validates.
   TrustKit behaves the same way on iOS.

So a phone needs a module that does both together: trust this one certificate, and verify it
is this one certificate. The runtime-configurable libraries
([react-native-ssl-public-key-pinning](https://github.com/frw/react-native-ssl-public-key-pinning)
and friends) do the second only. A module means a development build, which means a device to
run it on.

Rather than ship an unpinned connection "for now" — which would hand the device credential
and every message to whatever answered on that address — the app **refuses to connect** when
it cannot pin, and says so. `src/transport.ts` is the seam: a native module calls
`registerPinnedTransport()` once at startup and every screen starts working, with nothing
else to change. The test suite registers a Node implementation and drives the whole protocol
through it, so what is unproven is one module wide, not one app wide.

## Store submission notes

- No analytics or crash SDKs. Add nothing that transmits user AI data.
- The camera is the only permission, is requested when the scanner is opened rather than at
  launch, and is used for nothing but reading the pairing QR code.
- `ITSAppUsesNonExemptEncryption` is `false` today; revisit when end-to-end sync ships.
- `eas build --profile preview --platform android` needs an Expo account; see `eas.json`.
