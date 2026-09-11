# ADR-0006 Generated TypeScript types with required-by-default responses

## Context

Pydantic marks fields with defaults as optional in JSON Schema. Generated TypeScript then
forces null checks on values the service always sends, which encourages `!` and
hand-written types that drift.

## Decision

All exposed models inherit from `ApiModel`, which sets
`json_schema_serialization_defaults_required=True`. `openapi-typescript` output is
committed; CI regenerates and fails on drift.

## Consequences

- Frontend types are exact. Adding a field to a response model is a two-line change plus
  regeneration.
- Request models (`*Create`, `*Update`) keep optionality because FastAPI emits separate
  input schemas.
