# ADR-0005 Private mode is the only mode

## Context

Spec §8–§9 describe a default Private Mode and an opt-in Contributor Mode.

## Decision

`privacy_mode` has exactly one value, `private`, and is read-only. Contribution is a
separate boolean `contributor_mode`, default `false`, whose changes are written to the
security audit log. Enabling it in Phase 1 sends nothing; it only records the user's
willingness to be asked when a contribution pipeline exists.

## Consequences

- There is no code path in which private data leaves the machine without a distinct,
  later consent step.
- The Privacy Center can always display "Cloud AI data uploads: 0" truthfully.
