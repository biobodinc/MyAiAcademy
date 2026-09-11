# ADR-0007 Skill levels change only through evaluation

## Context

Spec §33 and §89: levels must reflect measurable performance, not time spent.

## Decision

`SkillState.level` has no API that sets it directly. It starts at 0 (unlearned), becomes
1 when a learning pipeline completes and its first evaluation passes, and only changes
afterwards when an evaluation run records a score. The overall level is the rounded mean
of the top three learned skills.

## Consequences

- Phase 1 shows level 0 for every skill and says why.
- Benchmarks (Phase 3) are the sole writer of levels; the audit log records each change.
