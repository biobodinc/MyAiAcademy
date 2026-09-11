# ADR-0002 Local API authentication

## Context

The service must be reachable by the desktop webview and the CLI, and by nothing else.
"Bound to localhost" alone does not stop a browser tab from issuing requests to
`127.0.0.1`, nor DNS rebinding.

## Decision

Four layers: loopback-only bind (validated, no override), `Host` allow-list, `Origin`
allow-list, and a per-installation 256-bit bearer token stored `0600` and compared in
constant time. Tauri reads the token from disk and passes it to the UI at runtime;
during browser development a developer pastes it into `.env.local`.

Alternatives considered: Unix sockets / named pipes (no browser story; harder for Windows
WebView2), mTLS (heavy for local), no auth (rejected by spec §47).

## Consequences

- Same-user malware can read the token. This matches every desktop app's threat model;
  OS keychain storage is planned for Phase 5.
- Third-party apps (Phase 9) will receive _scoped_ tokens rather than this installation
  token.
