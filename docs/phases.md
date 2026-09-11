# Implementation phases

Status legend: ✅ done · 🚧 partial · ⬜ not started. "Done" means implemented **and**
tested **and** honest in the UI about its limits.

| Phase                   | Scope (spec §99)                                                                                                           | Status | Notes                                                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------- |
| 1 Foundation            | Repository, desktop shell, React UI, Python backend, SQLite, hardware detection, storage management, AI profile, dashboard | ✅     | Plus CLI, command interpreter, audit log, Privacy Center, website and mobile skeletons, installers via CI.          |
| 2 Local AI              | Local model provider, chat, memory, knowledge, model management                                                            | ⬜     | `status.ai` reports `not_configured`; console explains chat is unavailable.                                         |
| 3 Skills                | Skill architecture, `/learn`, `/train`, levels, tree, benchmarks                                                           | 🚧     | Catalog, level bands, tree/locking and the parser exist; learning pipeline and benchmarks do not. `/learn` says so. |
| 4 Training              | Jobs, estimation, compute controls, pause/resume, checkpoints, history                                                     | ⬜     | Compute presets are stored; nothing consumes them yet.                                                              |
| 5 Security              | Accounts, device identity/authorization, secure storage, Privacy Center, audit                                             | 🚧     | Local auth, audit log and Privacy Center exist. Accounts, devices and OIDC do not.                                  |
| 6 Mobile                | Auth, QR pairing, permissions, chat, status, training control                                                              | 🚧     | Expo skeleton, store identifiers, connection state machine. No pairing.                                             |
| 7 Sync                  | Direct device sync, encrypted relay, conflicts, projects, memory                                                           | ⬜     | Versioned rows in place.                                                                                            |
| 8 Portable AI           | `.myai`, export/import, backup, external drives, compatibility, encryption                                                 | 🚧     | Storage layout and removable-drive detection exist; format documented as a draft.                                   |
| 9 Developer integration | Local API, capability permissions, website authorization, connected apps                                                   | 🚧     | Local API exists with installation-level auth; scoped capabilities do not.                                          |
| 10 Creative skills      | Provider abstractions for video, music, images, coding                                                                     | ⬜     | Catalog entries marked `planned`.                                                                                   |

## What "functional" means for Phase 2

A user picks a model from the catalog, reads its licence, accepts it, watches the download
verify itself, and chats with their named AI locally. They add memories on purpose (the AI
never remembers conversations on its own), add documents to knowledge, and see which
passages were retrieved for each answer. The CLI offers the same through `myai models`,
`myai chat`, `myai memory` and `myai knowledge`. If the inference runtime is missing the
status says so; if no model is installed the status says that instead.

## What "functional" means for Phase 1

A user can install the desktop app, be walked through first run (name the AI, pick
interests, see an honest hardware assessment, choose a storage location, read the privacy
promise), land on a dashboard, and use the console (`/help`, `/status`, `/hardware`,
`/skills`, `/settings`, natural-language mapping). The CLI exposes the same service.
Every Phase 2+ feature is visibly labelled with its phase.
