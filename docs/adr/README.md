# Architecture Decision Records

Short records of decisions that were not obvious. Format: context, decision, consequences.

| #                                                             | Title                                                           |
| ------------------------------------------------------------- | --------------------------------------------------------------- |
| [0001](0001-monorepo-and-toolchains.md)                       | Monorepo with uv, pnpm and cargo workspaces                     |
| [0002](0002-local-api-authentication.md)                      | Local API authentication: loopback + token + origin/host checks |
| [0003](0003-sqlite-sqlalchemy-alembic.md)                     | SQLite with SQLAlchemy 2.0 and Alembic                          |
| [0004](0004-python-sidecar-under-tauri.md)                    | Python service as a Tauri sidecar with a stdout ready protocol  |
| [0005](0005-privacy-modes.md)                                 | Private mode is the only mode; contribution is an opt-in flag   |
| [0006](0006-openapi-generated-types.md)                       | Generated TypeScript types with required-by-default responses   |
| [0007](0007-levels-only-from-evaluation.md)                   | Skill levels change only through evaluation                     |
| [0008](0008-local-inference-and-retrieval.md)                 | llama.cpp for local inference; lexical retrieval first          |
| [0009](0009-measured-benchmark-and-builtin-guide.md)          | Measured benchmark, live metrics and a deterministic guide      |
| [0010](0010-stream-cancellation-and-synthetic-model-tests.md) | Real stream cancellation and testing against the real runtime   |
| [0011](0011-skill-packages-and-benchmark-levels.md)           | Skill packages, benchmark-set levels and the coding sandbox     |
| [0012](0012-only-promised-hashes-may-fail-a-download.md)      | Only a promised hash may fail a download                        |
| [0013](0013-training-optimises-instructions-not-weights.md)   | Training optimises instructions, not weights                    |
| [0014](0014-per-client-credentials-and-erasure.md)            | Per-client credentials, and an erase that erases                |
