# Threat model (Phase 1)

This is a living document. It covers the software as shipped in Phase 1 and states the
assumptions later phases must revisit.

## Assets

- **A1** Private AI state: profile, preferences, audit log; later memory, knowledge,
  training data, weights, checkpoints, projects.
- **A2** The local API token (`local-api.token`).
- **A3** Availability of the local service (the AI keeps working offline).
- **A4** Integrity of the storage root layout.

## Trust boundaries

- **B1** Process boundary between the webview (untrusted content model, even though we
  ship it) and the Rust shell / Python service.
- **B2** The user's OS account. Other local users are outside the trust boundary; other
  processes in the same account are _partly_ trusted (they can read the token file, as
  any same-user process can read any user file).
- **B3** The network. The service never listens on it in Phase 1.

## Threats and mitigations

| ID  | Threat                                                                                                     | Mitigation                                                                                                                                                             | Residual risk                                                                                                                                                            |
| --- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| T1  | A malicious web page in the user's browser calls `http://127.0.0.1:<port>` (CSRF against a localhost API). | Bearer token required; `Origin` allow-list; browsers cannot omit `Origin` on cross-origin requests; CORS returns no `Access-Control-Allow-Origin` for unknown origins. | None known.                                                                                                                                                              |
| T2  | DNS rebinding: attacker's hostname resolves to 127.0.0.1 so a same-origin request reaches the API.         | `Host` header must be a loopback literal (421 otherwise).                                                                                                              | None known.                                                                                                                                                              |
| T3  | Port scanning by local malware to discover the API.                                                        | `/healthz` reveals only that a MyAI service is listening; all data endpoints need the token.                                                                           | A same-user process can read the token (B2). Mitigation of same-user malware is out of scope for any desktop app; OS keychain storage of the token is planned (Phase 5). |
| T4  | Token leakage through logs, UI source, discovery file or stdout.                                           | Token never logged; never in frontend bundle; discovery file and ready line carry the token _path_, not the value; tests assert this.                                  | None known.                                                                                                                                                              |
| T5  | Another local user reads private state.                                                                    | App data dir `0700`, token file `0600` on POSIX; Windows inherits per-user ACLs from the profile directory.                                                            | FAT-formatted external drives cannot hold permissions; the storage root warns about low space but not (yet) about filesystem type.                                       |
| T6  | Webview compromise (XSS via API content).                                                                  | Strict CSP (`script-src 'self'`, no inline scripts), React escaping, Tauri capabilities limited to folder picker and `https:` opener, `freezePrototype`.               | None known.                                                                                                                                                              |
| T7  | The service is exposed on the LAN by misconfiguration.                                                     | `CoreSettings.host` validator rejects non-loopback values; no UI or CLI flag exists to change it.                                                                      | None known.                                                                                                                                                              |
| T8  | Supply chain: dependencies.                                                                                | Lockfiles committed (`uv.lock`, `pnpm-lock.yaml`, `Cargo.lock`), pinned CI actions, no post-install scripts required.                                                  | Ongoing review needed; Dependabot config planned.                                                                                                                        |
| T9  | Privacy: accidental telemetry.                                                                             | No analytics, crash reporting or update-check code paths exist. The single outbound action is a TCP connect with no payload. Documented in the Privacy Center.         | None known.                                                                                                                                                              |
| T10 | Destructive storage operations.                                                                            | Phase 1 never deletes user data; protected categories are flagged for later delete flows (spec §63).                                                                   | —                                                                                                                                                                        |

## Out of scope for Phase 1 (revisit)

- Account authentication and device identity (Phase 5): password never reaches the app;
  OIDC with PKCE; device revocation.
- Pairing (Phase 6): short-lived challenge in the QR code; established protocols only.
- Sync (Phase 7): end-to-end encryption with user-controlled keys; the relay stores
  ciphertext only; conflict detection via row versions.
- Portable packages (Phase 8): password-based key derivation (Argon2id), authenticated
  encryption, integrity manifest.
- Third-party capability scopes (Phase 9): per-app, per-capability grants; never
  `computer.full_access`.
