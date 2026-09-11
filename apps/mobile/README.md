# @myai/mobile

Expo / React Native app for iOS and Android. The phone is an **authenticated controller**
for the user's desktop AI (spec §6, §52), never a second AI.

Phase 1 ships the project skeleton, store-ready identifiers, a least-privilege permission
manifest and the connection state model with tests. Phase 6 adds sign-in, QR pairing,
chat and training control.

```
pnpm --filter @myai/mobile start        # Expo dev server
pnpm --filter @myai/mobile typecheck
eas build --profile preview --platform android   # requires an Expo account; see eas.json
```

Store submission notes:

- No analytics or crash SDKs are included. Add nothing that transmits user AI data.
- `ITSAppUsesNonExemptEncryption` is `false` today; revisit when end-to-end sync ships.
- Camera permission text is declared ahead of Phase 6 QR pairing and is the only permission.
