# ADR-0011 Skill packages, benchmark-set levels and the coding sandbox

## Context

Phase 3 asks for skills that can be learned with `/learn`, levels that "reflect measurable
performance" (spec §33), a modular benchmark system (§43), a skill tree with locked nodes
(§35) and game-like degrees and achievements backed by real criteria (§82-§83). No trained
adapters or downloadable skill resources exist, and Phase 4 (training) has not started.
The project rule is that nothing may claim more than it does.

## Decision

- **A skill package is instructions plus a benchmark.** Each bundled package
  (`myai_core/skills/packages/<skill>/`) has a manifest, an `instructions.md` that is
  appended to the AI's system prompt once the skill is learned (a real, visible change in
  behaviour), and a `benchmark.json` of deterministic tasks. Only skills with a
  measurable benchmark ship a package: Conversation, Writing, Coding, Research, Science.
  Creative skills (images, video, music, games) have none and the UI, CLI and console say
  they cannot be learned in this build.
- **Learning = install + benchmark.** `/learn <skill>` first shows a preview (what is
  installed, benchmark size, model, recommended compute, an estimate derived from the
  measured tokens/s or "unknown"). `/learn <skill> start` installs the package under
  `Skills/<id>/<version>/` and runs the benchmark as a background job. The skill is marked
  learned only when the benchmark completes; a cancelled or failed job leaves it unlearned
  (§36: "Do not falsely say it was learned if only resources were downloaded").
- **The level is the score.** `level = round(score × 100)`, minimum 1 once learned. Scores
  are the mean of per-task check scores; a task passes only when every check passes.
  `SkillLearningService.apply_evaluation` is the single writer of levels and always records
  a `skill_evaluations` row (model, package version, area scores, per-task answers and
  grader details) plus an audit event. `/history` and the Skills page show every change.
- **Graders are pure functions.** `exact`, `contains_*`, `regex`, `numeric`, `word_count`,
  `line_count`, `bullets`, `json_object`, `code_contains` and `python_tests`. Reference
  answers in the tests prove each bundled task is satisfiable as written.
- **Model-written code runs in a limited sandbox.** `python_tests` executes the candidate
  in a separate interpreter process (`-I -S`, or the frozen binary re-executing itself with
  `--sandbox`), with an import allow-list installed before the code runs, an empty scratch
  directory, a stripped environment, a wall-clock timeout and, on POSIX, CPU-time and
  file-size limits. A memory cap is claimed only on Linux: macOS accepts `RLIMIT_AS` and
  then ignores it for the mmap-backed allocations CPython uses for large objects, which CI
  demonstrated by allocating 2 GiB under a 512 MiB cap, and Windows has no equivalent. The
  limit is still requested wherever it exists, but `sandbox.containment()` is the single
  source for what any surface tells a user, so the claim follows the platform. This is
  containment for accidents, not a security boundary against a hostile model; the README
  says so.
- **Jobs are cooperative.** One job at a time (§40 "prevent accidental resource
  overload"); pause, resume and cancel are honoured between tasks; jobs left active by a
  restart are marked failed on startup (§74).
- **`/train` stays honest.** It shows the §37 information (current level, target, areas,
  last benchmark by area) and states that training jobs arrive in Phase 4. It starts nothing.
- **Degrees and achievements** are computed from measured levels and area scores only.

## Consequences

- Levels depend on the active model: switching models and re-running the benchmark can
  lower a level. That is the truth the spec asks for, and the history explains it.
- Benchmarks are small (12 tasks per skill) and lexical; they measure instruction
  following and correctness on simple tasks, not deep competence. Phase 4 can extend the
  packages with larger evaluation sets and adapters without changing the contract.
- The bundled packages ship inside the sidecar/CLI binaries as data files.
