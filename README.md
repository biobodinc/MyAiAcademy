# MyAI Academy

**Build it. Teach it. Make it yours.**

A privacy-first personal AI you build, teach, train, specialize and carry across your
devices. Private by default. Local by design. Sharing by choice.

> Your AI. Your hardware. Your data. Your skills.

## Status

Phases 1 (Foundation), 2 (Local AI) and 3 (Skills) are implemented and tested. Later phases are visible
in the product as clearly labelled "Planned · Phase N" states; nothing is faked. See
[`docs/phases.md`](docs/phases.md) for the per-phase table.

| Surface                                        | What works today                                                                                                                                                                                                                                           |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Desktop app** (Tauri + React, Windows first) | First-run flow, dashboard, hardware assessment, storage location management, AI profile, skill tree, settings, Privacy Center, security activity log, command console (`/help`, `/status`, `/hardware`, `/skills`, `/settings`, natural-language mapping). |
| **Local service** (`myai-core`, Python)        | Loopback-only authenticated API, SQLite with migrations, hardware detection, storage manager, profile, preferences, audit log.                                                                                                                             |
| **CLI** (`myai`)                               | Same features from a terminal.                                                                                                                                                                                                                             |
| **Website** (Next.js, Vercel)                  | Landing, downloads from GitHub Releases, privacy and security pages, sign-in entry point (Phase 5).                                                                                                                                                        |
| **Mobile** (Expo)                              | Store-ready skeleton with the connection state model; pairing arrives in Phase 6.                                                                                                                                                                          |

## Disclosures

Read this before relying on the software. These statements hold until this section is
updated.

- **Catalog models have not yet been downloaded and run by the authors on consumer
  hardware.** The real llama.cpp runtime is exercised end to end in the test suite
  (`test_real_runtime.py`: loading, chat templating, streaming, benchmarking, unloading)
  with a small synthetic model, and downloads are verified against a local server. What
  remains unconfirmed is the full path with a catalog model from Hugging Face on an
  ordinary PC, because the environment the code was written in could not reach Hugging
  Face. Any failure is reported in the UI rather than hidden.
- **No signed installers are published yet.** The release workflow builds Windows, macOS
  and Linux packages and CLI archives, but nothing has been signed, notarised or uploaded
  to GitHub Releases, Google Play or the App Store. The download page will say
  "Not available yet" until that happens.
- **The mobile app is a skeleton.** It shows its connection state truthfully ("not
  paired") and nothing else. Pairing, chat and controls arrive in Phase 6.
- **Knowledge retrieval is keyword-based** (BM25 over SQLite FTS5), not semantic. It finds
  passages that share words with your question.
- **Training is not implemented (Phase 4).** Skills are learned from bundled packages
  (instructions plus a 12-task benchmark) and a skill's level is the score its benchmark
  produced with your local model; `/train` shows its information and states that training
  jobs arrive in Phase 4. Creative skills (images, video, music, games) have no benchmark
  yet and cannot be learned.
- **The coding benchmark executes code written by your local model.** It runs in a
  separate interpreter with an import allow-list, a scratch directory, a timeout and
  resource limits. That contains accidents; it is not a security boundary against a
  hostile model, so treat imported models with the same care as any software you run.
- **Network activity is limited to** an internet reachability check (a TCP connect with
  no payload) and model downloads you start after accepting a licence. Nothing you write,
  remember or add to knowledge leaves your machine.

## Temporary interface: the command line

Until installers are published, the supported way to use MyAI Academy is the `myai` CLI
run from a source checkout. It exposes everything the desktop app does today.

```
git clone https://github.com/biobodinc/MyAiAcademy.git
cd MyAiAcademy
uv sync --all-packages --all-groups --all-extras   # needs Python 3.11+, uv, CMake and a C++ compiler
uv run myai serve                                    # terminal 1: the local service (127.0.0.1 only)
uv run myai status                                   # terminal 2
uv run myai profile create --name Nova
uv run myai storage set-root ~/MyAI
uv run myai models list
uv run myai models download qwen2.5-1.5b-instruct-q4km   # shows the licence, asks, then downloads
uv run myai chat
uv run myai models import ~/models/some.gguf --confirm-rights   # use a GGUF you already have
uv run myai learn conversation                       # preview, confirm, benchmark -> level
uv run myai history                                  # every level change and why
uv run myai ask "what is training?"                  # built-in guide, not the model
uv run myai hardware --benchmark                     # memory bandwidth + measured tokens/s
uv run myai storage cleanup                          # leftovers; --delete removes them
uv run myai settings set --mode advanced --cpu 50    # advanced compute limits
```

`uv run myai --help` lists every command. The desktop app (`pnpm --filter @myai/desktop
tauri dev`) and website (`pnpm --filter @myai/website dev`) run from the same checkout.

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
