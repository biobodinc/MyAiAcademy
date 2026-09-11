# ADR-0009 Measured benchmark, live metrics and a deterministic guide

## Context

Spec §30 asks for a short hardware benchmark, §84 for live system figures on the
dashboard, and §66 for a small onboarding assistant that can answer "what is training?"
before any model is installed. Each is easy to fake (a table of guessed tokens/s, a
canned chatbot) and the project rule is that nothing may claim more than it measured.

## Decision

- **Benchmark = measurements only.** `hardware/benchmark.py` times a single-thread
  memory copy (the cheapest proxy for CPU token generation, which is bandwidth-bound),
  records memory pressure, and, when the runtime and an installed model exist, times a
  real 48-token generation with the active model. Tiers stay specification-based; the
  report shows measurements beside them with `benchmark_ran` set. Results are stored in
  `hardware_benchmarks` so the last run survives restarts.
- **Metrics are whole-machine snapshots.** `hardware/metrics.py` samples psutil and
  `nvidia-smi`; a GPU without live counters is reported by name with `null` figures, never
  with an invented percentage. The UI says the numbers are for the whole machine.
- **The guide is not a model.** `guide/` is a curated topic list with keyword matching.
  Every answer carries `source: "Built-in guide (not your AI model)"`, the console shows
  that label, and a question the guide cannot answer says so and suggests topics. Guide
  questions are never logged.
- **Advanced limits say what they enforce.** Each advanced compute preference states
  whether it is enforced now (CPU share, RAM cap) or stored for Phase 4 (GPU share,
  temperature, time), in the schema, the Settings page and the CLI.

## Consequences

- Benchmark numbers differ between runs and machines; that is the point. Consumers must
  not derive tier changes from them without a documented threshold.
- The guide needs curation when features ship: an answer that names a phase must be
  updated when that phase lands. `test_guide_topics_are_consistent` keeps related links
  valid; wording is reviewed by hand.
- Storage cleanup only ever deletes paths that appear in a fresh candidate scan and
  refuses protected categories without an explicit acknowledgement (spec §63).
