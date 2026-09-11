# ADR-0003 SQLite with SQLAlchemy 2.0 and Alembic

## Context

The spec mandates SQLite. The schema will grow substantially (jobs, memory, devices,
sync metadata) and must migrate in place on users' machines.

## Decision

SQLAlchemy 2.0 typed ORM with Alembic migrations run programmatically at startup
(`db/migrate.py`), WAL journal mode, foreign keys on. A test asserts the ORM metadata
and the migration chain agree.

## Consequences

- Every schema change ships as a migration; no `create_all` in production.
- Rows destined for sync carry `version`/`updated_at`/`origin_device_id` from the start
  so Phase 7 does not need a disruptive migration.
