# ADR-0004 Python service as a Tauri sidecar with a stdout ready protocol

## Context

The AI runtime is Python (PyTorch, Transformers, PEFT). The desktop shell is Tauri. The
shell must find the service's port and data directory without duplicating platform
path conventions in Rust.

## Decision

Package `myai-core` with PyInstaller into `binaries/myai-core-<triple>` and declare it as
`bundle.externalBin`. On startup the service prints a single line
`MYAI_CORE_READY {json}` naming its base URL and the token _file_. The shell reads the
token from that file. In debug builds without a sidecar, the shell runs `uv run myai-core`.

Alternatives considered: embedding Python (complex, huge binaries), a Rust rewrite of the
core (loses the ML ecosystem), fixed port and hard-coded data dir (fragile).

## Consequences

- The platform data-directory convention lives only in `myai_core/paths.py`.
- Sidecar builds are per-platform; CI builds them on each OS runner.
- PyInstaller one-file startup costs ~1–2 s; the UI shows a starting state.
