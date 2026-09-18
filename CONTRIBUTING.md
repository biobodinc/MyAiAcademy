# Contributing

This is internal setup documentation for whoever is working on MyAI Academy, not an
invitation for outside contributions: the project is proprietary and the repository is
private. See [`LICENSE`](LICENSE).

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node 22+ and pnpm 10 (`corepack enable`)
- Rust stable and the Tauri prerequisites for your OS
  (https://tauri.app/start/prerequisites/)

## Setup

```
uv sync --all-packages --all-groups --all-extras   # --all-extras builds llama-cpp-python (local chat)
pnpm install
pnpm api:types          # regenerate TypeScript types from openapi.json
```

Without `--all-extras` everything still works except local chat, and the service reports
the missing runtime honestly. Building the extra needs CMake and a C++ compiler (see
https://github.com/abetlen/llama-cpp-python#installation for prebuilt wheels).

## Run

```
uv run myai-core                       # local service only
uv run myai status                     # CLI against it
pnpm --filter @myai/desktop tauri dev  # desktop app (spawns the service itself)
pnpm --filter @myai/desktop dev        # UI in a browser; needs VITE_MYAI_DEV_TOKEN
pnpm --filter @myai/website dev
pnpm --filter @myai/mobile start
```

## Checks (what CI runs)

```
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/myai-core/src packages/myai-cli/src
uv run pytest
pnpm typecheck && pnpm lint && pnpm test
pnpm format:check
cd apps/desktop/src-tauri && cargo clippy --all-targets -- -D warnings
uv run python scripts/export_openapi.py && git diff --exit-code packages/api-client/openapi.json
```

## Principles for changes

- Never claim a capability the code does not have. Unimplemented features return
  `unavailable`/`planned` and the UI shows the phase.
- Never add a code path that transmits private data without an explicit consent step and
  an audit-log entry.
- No secrets in the repository, in frontend bundles, in logs or in stdout.
- Every schema change is an Alembic migration.
- Add a test with the change; add an ADR for a decision with trade-offs.
