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
| **Website** (Next.js, Vercel)                  | Landing, downloads, privacy and security pages, account pages (Phase 5).                                                                                                                                                                                   |
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
  anywhere, including Google Play and the App Store. The download page will say
  "Not available yet" until that happens.
- **Your AI is reachable from your network only if you say so.** The service listens on
  127.0.0.1 until you turn on network access; then it starts a second, HTTPS-only listener
  with a certificate your device pins when it pairs, and it refuses this installation's own
  token over the network so the master key never leaves the machine. Turning it on and off
  is in the audit log ([ADR-0015](docs/adr/0015-reaching-the-host-from-a-phone.md)).
- **The mobile app still cannot connect.** The computer side is built and tested — the
  listener, the certificate, the pairing code and the QR that carries the fingerprint to
  pin — but pinning a self-signed certificate in React Native needs a native module and a
  device build, and we will not ship a connection that has never been made on real
  hardware. The app parses pairing invites, compares fingerprints, and otherwise reports
  itself unpaired, which is the truth.
- **Knowledge retrieval is keyword-based** (BM25 over SQLite FTS5), not semantic. It finds
  passages that share words with your question.
- **Training does not change your model's weights.** `/train` searches for better
  _instructions_ for one skill — short rules from its package, rules your AI writes for
  itself after a mistake, and worked examples — and keeps a change only when it scores
  higher on practice tasks. When the search ends, that skill's benchmark runs with the old
  and the new instructions and the result is kept only if the score went up; if it did not,
  the run says so and nothing changes. Levels still come only from a benchmark run.
  Fine-tuning a quantised local model is not something this program can honestly do, so it
  does not claim to (see
  [ADR-0013](docs/adr/0013-training-optimises-instructions-not-weights.md)).
- **Images, video and music cannot be generated at all.** There is no local provider in this
  build, and a prompt is never sent to an online service instead — that would be the clearest
  possible break of the claim above. Each says what it would take (a local model of several
  gigabytes, and in practice a graphics card) rather than naming a future phase. **Games can
  be learned and trained**: designing mechanics, levels and narrative is prose and arithmetic,
  so it has a deterministic benchmark like the other text skills
  ([ADR-0018](docs/adr/0018-creative-skills-and-the-cloud-shortcut.md)).
- **The account server exists in the repository, but is not running anywhere.** An
  account server is written and tested — sign-up with email confirmation, sign-in with a
  password or with Google, Apple or Facebook, device pairing and revocation — and the website
  has pages for it. No provider credentials are configured, so no provider is offered. Nothing is deployed: the
  published site is built without an account server configured, so those pages say there is
  none rather than showing a form that posts into the void. The desktop app and the command
  line still have no account code path at all. When it does run it will hold an email
  address, a hashed password, which devices you have added, and a log of account activity —
  never your conversations, memories, files or model weights.
- **Nothing on your network can reach your AI until you turn that on.** The local service
  listens on 127.0.0.1 only. Network access is a second listener you switch on deliberately:
  HTTPS with a certificate the host mints and a device pins, recorded in the audit log both
  ways, and this installation's own token is refused over it. A paired
  client holds its own credential, which you can revoke on its own; only the installation
  itself can grant or revoke access, export or erase
  ([ADR-0014](docs/adr/0014-per-client-credentials-and-erasure.md)).
- **A paired program only gets what you ticked.** Access is a set of named capabilities you
  approve when you make the pairing code, described in words rather than identifiers, with
  reading and writing as separate asks. The default grant contains nothing you have written.
  A part of the API nobody classified is refused rather than allowed
  ([ADR-0017](docs/adr/0017-what-a-paired-program-may-do.md)).
- **Not every model download can be hash-verified.** A download is only failed when it
  disagrees with a hash the publisher actually promises (a hash pinned in our catalog, or
  Hugging Face's `X-Linked-Etag`). A plain `ETag` is an opaque validator, not a content
  hash, so it is never used to reject a file. Where no published hash exists the download
  is checked for completeness only, and the app labels that model "unverified" rather than
  implying it was checked. `myai models check <id>` shows what a host declares.
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
cd MyAiAcademy            # a checkout of this repository
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
