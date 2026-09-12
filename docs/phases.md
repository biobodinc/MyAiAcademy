# Implementation phases

Status legend: ✅ done · 🚧 partial · ⬜ not started. "Done" means implemented **and**
tested **and** honest in the UI about its limits.

| Phase                   | Scope (spec §99)                                                                                                           | Status | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 Foundation            | Repository, desktop shell, React UI, Python backend, SQLite, hardware detection, storage management, AI profile, dashboard | ✅     | Plus CLI, command interpreter, audit log, Privacy Center, live system metrics, measured benchmark, storage cleanup, advanced compute limits, built-in guide, website and mobile skeletons, installers via CI.                                                                                                                                                                                                                                                                                                                                                 |
| 2 Local AI              | Local model provider, chat, memory, knowledge, model management                                                            | ✅     | llama.cpp provider, curated GGUF catalog with licence gate, resumable verified downloads, streaming chat with real cancellation and per-user generation defaults, conversation rename, model unload, import of user-supplied GGUF files, provider tree with honest status, explicit memory, lexical knowledge retrieval. Exercised end to end with the real llama.cpp runtime on a synthetic model in CI; a catalog model on consumer hardware is still to be confirmed (see README disclosures).                                                             |
| 3 Skills                | Skill architecture, `/learn`, `/train`, levels, tree, benchmarks                                                           | ✅     | Bundled skill packages (instructions + deterministic benchmark) for Conversation, Writing, Coding, Research, Science; `/learn` preview and start; background jobs with pause/resume/stop; levels set only by benchmark runs; history, degrees, achievements. `/train` shows its information and states training arrives in Phase 4. Creative skills stay unlearnable until a benchmark exists.                                                                                                                                                                |
| 4 Training              | Jobs, estimation, compute controls, pause/resume, checkpoints, history                                                     | ✅     | `/train` runs a measured search over a skill's instructions: packaged tactics, rules the model writes for itself after a mistake, and worked examples. Selection happens on a practice set disjoint from the benchmark; the benchmark then decides whether the result is kept, and only it can change a level. Budget, target level and focus qualifiers; pause/resume/stop; every round persisted, so a run interrupted by a restart resumes from its best candidate. Undo puts the package's instructions back. Model weights are never changed (ADR-0013). |
| 5 Security              | Accounts, device identity/authorization, secure storage, Privacy Center, audit                                             | 🚧     | Per-client credentials with pairing codes, revocation that takes effect at once, and a caller identity recorded in the audit log; secret-storage permissions checked and repaired at start-up; Privacy Center export (data, never credentials) and an erase that deletes rows behind a typed confirmation. Accounts, OIDC and device identity across machines do not exist: there is no account server, and every surface says so rather than implying one (ADR-0014).                                                                                        |
| 6 Mobile                | Auth, QR pairing, permissions, chat, status, training control                                                              | 🚧     | Expo skeleton, store identifiers, connection state machine. No pairing.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 7 Sync                  | Direct device sync, encrypted relay, conflicts, projects, memory                                                           | ⬜     | Versioned rows in place.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 8 Portable AI           | `.myai`, export/import, backup, external drives, compatibility, encryption                                                 | 🚧     | Storage layout and removable-drive detection exist; format documented as a draft.                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 9 Developer integration | Local API, capability permissions, website authorization, connected apps                                                   | 🚧     | Local API exists with installation-level auth; scoped capabilities do not.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 10 Creative skills      | Provider abstractions for video, music, images, coding                                                                     | ⬜     | Catalog entries marked `planned`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

## What "functional" means for Phase 5

A user can see exactly which programs may act as their AI, add one without handing over the
master key, and take that access away again. In the app (or `myai security`) they create a
pairing code, type it into the tool they are pairing, and that tool gets a credential of its
own; the code works once and expires in minutes. The list shows what each client is, when it
was last used, and a Revoke button that stops it on its next request. A paired client can use
the AI but cannot issue or revoke access, export or erase — that is the owner's alone, and it
is enforced in the API rather than by hiding a button.

The same page says where this installation's secrets live and whether anyone else on the
machine can read them, repairing the permissions at start-up if they can, and saying plainly
when the platform makes that unverifiable rather than showing a tick it cannot justify. It
says there is no account, because there is not.

"Export my data" writes an archive containing everything this installation holds about them,
with a manifest listing what is inside and what was deliberately left out. "Erase everything"
shows the counts first, requires a typed phrase, deletes the rows, and says what it could not
reach.

### Phase 5 spec coverage

| Spec section                 | Where                                                                                                    |
| ---------------------------- | -------------------------------------------------------------------------------------------------------- |
| §47 Local API protection     | Loopback bind, Host and Origin checks, then a credential that identifies a caller (`security/auth.py`)   |
| §51-§53 Device authorization | `security/devices.py`: pairing codes, issued credentials, revocation; `/api/security/*`                  |
| §60 Secure storage           | `security/storage_checks.py` verifies and repairs permissions; secrets are stored only as SHA-256 hashes |
| §61 Audit                    | Every grant, revocation and rejected pairing attempt recorded; filter by category, client or date        |
| §62 Privacy Center           | Real client counts; export with a manifest; erase behind a typed phrase (`privacy/portability.py`)       |
| §56-§59 Accounts, OIDC       | **Not implemented.** `AccountState` reports no account and why, and no surface implies otherwise         |

## What "functional" means for Phase 4

A user who has learned Writing types `/train writing 30m` (or opens the Train dialog) and
sees what will happen: the time budget, which area will be practised and why, how many
practice tasks will be used to search and how many to confirm, an estimated number of
rounds derived from their measured tokens per second, and the plain statement that their
model's weights will not change. They confirm; a job runs one round at a time, each round
trying a change and keeping it only if it measures better. They can pause, resume or stop
it, and the round-by-round record says exactly what was tried. When the budget ends, the
Writing benchmark runs with the old instructions and with the new ones, and the result is
kept only if the score went up — if it did not, the run says so and nothing changes. A
level that moved, moved because a benchmark measured it. If the service is killed
mid-run, the run is marked interrupted, keeps the best instructions it had found, and the
next training run for that skill continues from them. "Undo training" puts the package's own
instructions back and leaves the measured level alone.

### Phase 4 spec coverage

| Spec section                     | Where                                                                                                         |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| §3 Learn / Train terminology     | `/learn` acquires a package; `/train` improves what is there, by measurement                                  |
| §31 Compute settings             | The job records the preset in force; the runtime load honours it                                              |
| §37 /train information           | `trainer.TrainPreview`: level, target, areas, last benchmark by area, focus, budget, estimate, model          |
| §38 /train qualifiers            | Duration, target level, focus area and `all` parsed in `commands/parser.py`, resolved in `trainer._resolve_*` |
| §40 Jobs                         | The `train` job kind in `skills/pipeline.py`; one at a time; pause/resume/stop honoured between tasks         |
| §41 Estimation                   | Rounds estimated from the measured benchmark; the job's total re-projected from real round times              |
| §42 History                      | `training_runs` with every round; `GET /api/skills/{id}/training`; `myai training <skill>`                    |
| §43 Benchmark system             | The same graders; practice tasks kept disjoint from benchmark tasks by `load_package`                         |
| §74 Crash recovery (checkpoints) | `TrainingService.recover()` marks interrupted runs and keeps their best candidate for the next run            |
| §89 Levels                       | `apply_evaluation` remains the only level writer (ADR-0007, ADR-0013)                                         |

## What "functional" means for Phase 3

A user types `/learn conversation` (or clicks Learn) and sees exactly what will happen:
the package that gets installed, how many benchmark tasks run, with which model, the
recommended compute and an estimate when one can be derived. They confirm; a job runs the
benchmark with their local model, can be paused, resumed or stopped, and when it finishes
the skill is learned at the level it scored. The Skills page shows per-area scores, the
tree unlocks the next skills, `/history` lists every level change with the model that
produced it, and degrees and achievements light up only from those measurements. Learned
skills change how the AI is prompted in Chat. Creative skills say plainly that they cannot
be learned yet. Nothing is downloaded and the model is not retrained.

### Phase 3 spec coverage

| Spec section                  | Where                                                                                                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------- |
| §3 Learn / Train terminology  | `/learn` acquires (package + benchmark); `/train` explains improvement is Phase 4                        |
| §33 Level system              | `skills/evaluate.py` `level_from_score`; `apply_evaluation` is the only level writer                     |
| §34 Skill tiers               | `skills/levels.py` bands                                                                                 |
| §35 Skill tree                | `requires` in the catalog; locked nodes show requirements; enforced in the learn preview                 |
| §36 /learn                    | Preview with resources, benchmark, model, compute and estimate; "start" confirmation; learned only after |
| §37-§38 /train                | Parsed qualifiers (duration, level, focus, all) shown; no job started; Phase 4 stated                    |
| §39 Other commands            | `/pause` `/resume` `/stop` control the running job; `/history` lists benchmark runs                      |
| §40 Jobs                      | `jobs` table with the spec's fields; one at a time; queued/running/paused/completed/failed/cancelled     |
| §42 History                   | `skill_evaluations`; Skills page history; `myai history`                                                 |
| §43 Benchmark system          | `skills/graders.py`, `skills/packages/*/benchmark.json`, areas per skill; coding tasks in a sandbox      |
| §74 Crash recovery (jobs)     | Active jobs are marked failed on restart with an explanation                                             |
| §82-§83 Progression, degrees  | `skills/academy.py` from measured levels and area scores only                                            |
| §88 First learning experience | Preview → confirm → progress → "learned at level N"                                                      |

## What "functional" means for Phase 2

A user picks a model from the catalog, reads its licence, accepts it, watches the download
verify itself, and chats with their named AI locally. They add memories on purpose (the AI
never remembers conversations on its own), add documents to knowledge, and see which
passages were retrieved for each answer. They can rename or delete conversations, free
the model's memory with one click, and (in Advanced mode) set the reply length and
temperature that every message uses unless a client overrides them. Stopping a reply
really stops generation and keeps the partial text. A GGUF file the user already has can
be imported (rights confirmed by the user, hash recorded) and used like a catalog model.

### Phase 2 spec coverage

| Spec section                                                                             | Where                                                                                                                  |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| §44 Memory system                                                                        | `memory/`: add, edit, delete, search (FTS5), clear; never auto-created; Memory page, `myai memory`                     |
| §45 Knowledge system                                                                     | `knowledge/`: txt, md, code, pdf; paragraph chunks; BM25 retrieval; passages shown per reply; "does not retrain" label |
| §46 Model provider architecture                                                          | `ModelProvider` protocol; `LlamaCppProvider`; `GET /api/models/providers` lists local/external with real status        |
| §69 Model licences                                                                       | Catalog licence shown and accepted before any request; imported files carry a "your own licence" record                |
| §19 Offline operation                                                                    | Chat, memory, knowledge and installed models work with no internet; status distinguishes internet from AI availability |
| §31 Compute settings (runtime)                                                           | Preset and CPU override feed `LoadConfig`; RAM cap refuses oversize loads                                              |
| §67 Error handling                                                                       | Partial replies persisted with `finish_reason` error/cancelled; backend messages surfaced verbatim                     |
| §71 Testing                                                                              | Fake-provider route tests, real-runtime tests (`test_real_runtime.py`), cancellation tests over a live server          | The CLI offers the same through `myai models`, |
| `myai chat`, `myai memory` and `myai knowledge`. If the inference runtime is missing the |
| status says so; if no model is installed the status says that instead.                   |

## What "functional" means for Phase 1

A user can install the desktop app, be walked through first run (name the AI, pick
interests, see an honest hardware assessment, choose a storage location, read the privacy
promise, ask the built-in guide what any of it means), land on a dashboard that shows the
AI's level, a truthful "current status" line and live CPU/RAM/GPU figures, and use the
console (`/help`, `/status`, `/hardware`, `/skills`, `/memory`, `/settings`,
natural-language mapping, product questions). The Hardware page can run a short measured
benchmark; the Storage page shows usage per category and cleans up leftovers with a
warning before protected resources are touched; Advanced mode exposes exact compute
limits and says which are enforced today. The CLI exposes the same service. Every Phase
2+ feature is visibly labelled with its phase.

### Phase 1 spec coverage

| Spec section              | Where                                                                                                           |
| ------------------------- | --------------------------------------------------------------------------------------------------------------- |
| §28 AI profile            | `profile/`, My AI page, `myai profile`                                                                          |
| §29 Hardware detection    | `hardware/detect.py` and probes; never crashes, warnings shown                                                  |
| §30 Hardware benchmark    | `hardware/benchmark.py`: memory bandwidth, memory pressure, measured tokens/s once a model exists               |
| §31 Compute settings      | Presets in Settings; advanced limits (CPU %, RAM cap enforced now; GPU %, temperature, time stored for Phase 4) |
| §61 Audit log             | `audit/`, Activity page, `myai audit`                                                                           |
| §62 Privacy Center        | `/api/privacy`, Privacy Center page                                                                             |
| §63 Storage manager       | `storage/`, usage per category, `storage/cleanup.py` with protected-category warning                            |
| §64/§65 Beginner/Advanced | `experience_mode`; advanced compute card only in Advanced mode, with the spec's warning                         |
| §66 Onboarding AI         | `guide/`: deterministic curated answers, labelled "Built-in guide (not your AI model)"                          |
| §67 Error handling        | Service gate, inline alerts with cause and retry, benchmark/cleanup report refusals                             |
| §68 Offline status        | `status/service.py`, sidebar pills, `/status`                                                                   |
| §81 Command system        | `commands/`, Console, `myai run`                                                                                |
| §84 Main dashboard        | Level badge, skills, current status, quick actions, live system card (`hardware/metrics.py`)                    |
| §86 Design language       | Cards, level badges, progress bars, animations, light/dark themes                                               |
| §87 First-run flow        | `OnboardingWizard.tsx` (account step deferred to Phase 5, labelled)                                             |

## Product direction to carry forward (recorded 2026-09-11, not yet implemented)

Decisions from the product owner that later phases must honour. Nothing below is built
yet, and no pricing has been decided.

- **An account is required to access downloads and to sign in to the desktop app.**
  Phase 5 (accounts, OIDC with PKCE) therefore moves ahead of Phase 3/4 work that would
  otherwise ship without a sign-in gate on the download page. The website's download page
  will require sign-in before showing release assets.
- **The CLI may require a subscription** if subscriptions are introduced. The business
  model is still being decided; the best case is subscriptions. Until then the CLI stays
  a temporary, ungated interface from a source checkout (see README "Temporary
  interface").
- Existing promises stay intact: the local AI keeps working offline once installed
  (spec §92), private data never leaves the machine, and no capability is gated in a way
  that holds the user's AI or data hostage (spec §101). Gating applies to distribution
  and sign-in, not to the user's already-installed AI.
