# ADR-0001 Monorepo with uv, pnpm and cargo workspaces

## Context

Three user-facing surfaces (desktop, website, mobile) share one API contract and one
product vocabulary. Python (AI runtime), TypeScript (UIs) and Rust (desktop shell) are all
required by the spec.

## Decision

One repository. Python packages in a `uv` workspace with a single lockfile; JavaScript
packages in a `pnpm` workspace; the Rust crate under `apps/desktop/src-tauri`. Shared
contract flows one way: Python → OpenAPI → TypeScript.

## Consequences

- Cross-cutting changes (an API field) are one PR with generated types checked in CI.
- Contributors need three toolchains; `docs/architecture.md` and CI document the exact
  commands.
- Vercel deploys `apps/website` with the root directory set to that folder.
