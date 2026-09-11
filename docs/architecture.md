# Architecture

MyAI Academy is a **local-first personal AI platform**. This document describes the system as
it exists after Phase 1 and the boundaries later phases must respect. Decisions with
trade-offs are recorded as ADRs in `docs/adr/`.

## Components

```
┌────────────────────────────────────────────────────────────────────────────┐
│ User's computer                                                            │
│                                                                            │
│  ┌──────────────────────┐   invoke()   ┌──────────────────────────────┐    │
│  │ Desktop shell (Tauri)│◄────────────►│ React UI (apps/desktop/src)  │    │
│  │ apps/desktop/src-tauri│              │ TanStack Query + api-client  │    │
│  │ - spawns sidecar     │              └──────────────┬───────────────┘    │
│  │ - reads token file   │                             │ HTTP + Bearer      │
│  │ - folder picker      │                             ▼                    │
│  └──────────┬───────────┘              ┌──────────────────────────────┐    │
│             │ spawn, stdout ready line │ myai-core (FastAPI, Python)  │    │
│             └─────────────────────────►│ 127.0.0.1 only               │    │
│                                        │ SQLite + Alembic             │    │
│  ┌──────────────────────┐   HTTP       │ hardware · storage · profile │    │
│  │ myai CLI (Typer)     │─────────────►│ preferences · skills · audit │    │
│  └──────────────────────┘              │ commands · status · privacy  │    │
│                                        └──────────────┬───────────────┘    │
│                                                       ▼                    │
│   App data dir (small, per-user)        MyAI storage root (large, chosen)  │
│   ├─ myai-core.sqlite3                  ├─ Models/    ├─ Checkpoints/      │
│   ├─ local-api.token (0600)             ├─ Skills/    ├─ Memory/           │
│   └─ local-api.json (no secret)         ├─ Training/  ├─ Knowledge/ …      │
└────────────────────────────────────────────────────────────────────────────┘

  apps/website (Next.js on Vercel): marketing, downloads, sign-in entry (Phase 5)
  apps/mobile  (Expo): authenticated controller for the desktop AI (Phase 6)
  packages/api-client: TypeScript types generated from myai-core's OpenAPI document
```

### myai-core (`packages/myai-core`)

The only process that owns private state. Layers:

| Layer           | Location                                                                                         | Notes                                                                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Persistence     | `db/`                                                                                            | SQLAlchemy 2.0 typed ORM, Alembic migrations run at startup, SQLite in WAL mode. Rows that will sync later carry `version`/`updated_at` from day one (spec §72).      |
| Domain services | `hardware/`, `storage/`, `profile/`, `preferences/`, `skills/`, `commands/`, `audit/`, `status/` | Plain Python; no FastAPI imports. Each has a Pydantic schema module and is unit-tested without HTTP.                                                                  |
| API             | `api/`                                                                                           | Thin routers. Every route under `/api` is behind `require_local_auth`. Responses derive from `ApiModel` so defaulted fields are _required_ in OpenAPI (see ADR-0006). |
| Process         | `server.py`                                                                                      | Picks a loopback port, writes the discovery file, prints the `MYAI_CORE_READY` line, runs uvicorn.                                                                    |

**Honesty rule.** Anything not implemented reports itself as `unavailable`, `not_configured`
or `planned` through the API. The UI renders those states; it never fills them in.

### Desktop shell (`apps/desktop/src-tauri`)

Rust, deliberately thin (three commands). It supervises the sidecar and hands the UI the
token it read from disk. The React UI runs unchanged in a browser during development.
CSP and capabilities are least-privilege (`capabilities/default.json`).

### Shared API contract (`packages/api-client`)

`scripts/export_openapi.py` dumps `openapi.json`; `openapi-typescript` generates
`src/generated/schema.d.ts`; `openapi-fetch` provides a typed client. Both files are
committed, so the frontends build without Python and CI verifies they are current.

## Data boundary (spec §10)

| Category                                                                                 | Where it lives              | Leaves the machine?                                                                       |
| ---------------------------------------------------------------------------------------- | --------------------------- | ----------------------------------------------------------------------------------------- |
| Private (profile, preferences, audit, and later memory, knowledge, weights, checkpoints) | app data dir + storage root | Never by default. Only through explicit export or a future opt-in sync/contribution flow. |
| Public / downloadable (updates, skill packages, models, docs)                            | fetched on demand           | Downloads only. Licences shown first (Phase 2+).                                          |
| Explicitly shared                                                                        | —                           | Only after a consent screen, category by category, revocable.                             |

Network activity as of Phase 2: a TCP connect (no payload) to a public resolver for
online/offline status, and model downloads from Hugging Face that the user starts after
accepting the licence. Chat, memory and knowledge never leave the machine. There is no
account, sync, telemetry or crash-reporting code.

## Security boundaries (spec §47, §73)

1. Loopback bind. There is no configuration to bind elsewhere; the settings validator
   rejects it.
2. `Host` validation (DNS-rebinding protection) and `Origin` allow-list (packaged Tauri
   origins plus the Vite dev server).
3. Per-installation bearer token, 256-bit, owner-only file, constant-time comparison.
4. Strict CSP in the webview; capabilities limited to folder picker and `https:` opener.
5. Audit log for security-relevant events (storage changes, consent toggles).

Later phases layer scoped capabilities for third-party apps (Phase 9) and device
identities (Phase 5) on top of this; they do not replace it.

## Where later phases plug in

| Phase         | Extension point already present                                                                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2 Local AI    | `status.ai` becomes `available`; a `ModelProvider` package lands under `myai_core/models/`; `OnboardingStep.LOCAL_MODEL` gains a real screen.                      |
| 3 Skills      | `SkillState` rows are created by the learning pipeline; `SkillDefinition.availability` flips to `available`; command dispatcher handlers for `/learn` return jobs. |
| 4 Training    | `TrainingJob` table (spec §40) with the same `version`/`updated_at` convention; `ComputePreset` percentages feed the scheduler.                                    |
| 5 Security    | Device identity table; `AuditEvent.device_id` is already nullable for it; OIDC/PKCE flow terminates in the desktop shell via a deep link.                          |
| 6 Mobile      | `apps/mobile/src/connection.ts` is the state machine screens are built on; `api-client` accepts device credentials through its provider interface.                 |
| 7 Sync        | Conflict detection uses the `version` columns; conflicts are surfaced, never auto-resolved for important state.                                                    |
| 8 Portable AI | Storage layout is already the on-disk shape of a `.myai` package (`docs/formats/myai-package.md`).                                                                 |

## Repository layout

```
apps/desktop      Tauri + React + TypeScript + Tailwind
apps/website      Next.js (Vercel)
apps/mobile       Expo / React Native
packages/myai-core  Python local service
packages/myai-cli   Python CLI
packages/api-client TypeScript API types + client
scripts/          export_openapi.py, build_sidecar.py
docs/             this file, ADRs, security, formats, phases
```

Tooling: `uv` workspace for Python (`uv sync --all-packages --all-groups`), `pnpm`
workspace for JavaScript, `cargo` for the shell. `ruff`, `mypy --strict`, `eslint`
(strict type-checked), `clippy -D warnings` and `prettier` gate CI.
