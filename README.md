# MyAI Academy

**Build it. Teach it. Make it yours.**

A privacy-first personal AI you build, teach, train, specialize and carry across your
devices. Private by default. Local by design. Sharing by choice.

> Your AI. Your hardware. Your data. Your skills.

## Status

Phases 1 (Foundation) and 2 (Local AI) are implemented and tested. Later phases are visible
in the product as clearly labelled "Planned · Phase N" states; nothing is faked. See
[`docs/phases.md`](docs/phases.md) for the per-phase table.

| Surface                                        | What works today                                                                                                                                                                                                                                           |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Desktop app** (Tauri + React, Windows first) | First-run flow, dashboard, hardware assessment, storage location management, AI profile, skill tree, settings, Privacy Center, security activity log, command console (`/help`, `/status`, `/hardware`, `/skills`, `/settings`, natural-language mapping). |
| **Local service** (`myai-core`, Python)        | Loopback-only authenticated API, SQLite with migrations, hardware detection, storage manager, profile, preferences, audit log.                                                                                                                             |
| **CLI** (`myai`)                               | Same features from a terminal.                                                                                                                                                                                                                             |
| **Website** (Next.js, Vercel)                  | Landing, downloads from GitHub Releases, privacy and security pages, sign-in entry point (Phase 5).                                                                                                                                                        |
| **Mobile** (Expo)                              | Store-ready skeleton with the connection state model; pairing arrives in Phase 6.                                                                                                                                                                          |

## Quick start (developers)

```
uv sync --all-packages --all-groups     # Python workspace
pnpm install                            # JavaScript workspace
pnpm --filter @myai/desktop tauri dev   # desktop app; spawns the local service
```

Or without the desktop shell:

```
uv run myai-core          # terminal 1
uv run myai status        # terminal 2
uv run myai run "/hardware"
```

Full instructions: [`CONTRIBUTING.md`](CONTRIBUTING.md). Architecture and decisions:
[`docs/architecture.md`](docs/architecture.md), [`docs/adr/`](docs/adr/). Threat model:
[`docs/security/threat-model.md`](docs/security/threat-model.md).

## Installers

Release builds are produced by [`.github/workflows/release.yml`](.github/workflows/release.yml)
on a version tag: Windows NSIS/MSI, macOS DMG, Linux AppImage/deb, the CLI as a wheel and
per-OS archive, and mobile builds via EAS. No secrets are committed; signing material lives
in CI secrets and the Vercel/EAS dashboards.

## Licence

Apache-2.0. See [`LICENSE`](LICENSE).
