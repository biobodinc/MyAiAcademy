# ADR-0013 Training optimises instructions, not weights

- Status: accepted
- Date: 2026-09-12
- Supersedes nothing. Extends ADR-0007 (one writer of levels) and ADR-0011 (skill packages).

## Context

The spec promises training (§37, §38): a user says `/train writing 2h` and their AI gets
better at writing, with jobs, estimates, compute controls, pause/resume, checkpoints and
history (§99 Phase 4).

The obvious reading is fine-tuning the model's weights. We are not going to pretend to do
that:

- The models this program runs are quantised GGUF files, 1-8 GB, loaded through
  llama.cpp. Training weights needs the unquantised model, a training framework, and far
  more memory and time than the machines in our hardware tiers have. A LoRA adapter is
  closer to feasible but still needs hours on a GPU we cannot assume, and
  `llama-cpp-python` exposes no training entry point at all.
- A "training" feature that spins a progress bar and changes nothing measurable would be
  the exact dishonesty this project refuses: the user cannot check it, so they would have
  to take our word for it.

What _is_ both feasible and genuinely effective on a local model is changing how the model
is instructed. A model's behaviour on a task depends heavily on the instructions and worked
examples in its prompt, and searching that space against a scoring function is a
well-established method (automated prompt optimisation). It costs only inference, it runs
on a CPU, it is interruptible, and — decisively — its effect is measurable with the
benchmark machinery Phase 3 already has.

## Decision

**Training is a measured search over a skill's instructions. The model's weights are never
touched, and every surface says so in those words.**

- A **candidate** is the package's instructions plus up to six short _tactics_ and up to
  two _worked examples_. `Candidate.render()` produces the text; the empty candidate is the
  package exactly as shipped.
- Tactics come from two places. Each skill package ships a list of candidate tactics in
  `practice.json`. The model also writes its own: shown a task it just got wrong and why,
  it is asked for one short rule that would have avoided the mistake. A model-written rule
  is reduced to a single line, length-checked, and then has to earn its place the same way
  a packaged one does.
- **Only measurement decides.** A candidate is accepted when it scores strictly higher on
  the _search split_ of the practice tasks and does not score lower on the _check split_.
  A tie is a rejection: an unproven change is not an improvement.
- **The tasks training selects on are never the tasks that set the level.** Each package
  has a `practice.json` disjoint from `benchmark.json`; `load_package` refuses a package
  where the two share a task id. Practice is then split again so a candidate has to hold up
  on tasks it was not chosen against.
- **The benchmark decides whether the result is kept at all.** When the search ends, the
  benchmark runs twice — once with the current instructions, once with the winner — with
  the same model in the same state, minutes apart. The trained instructions are written to
  disk only if the benchmark score went up. Otherwise the previous instructions stay and
  the run says exactly that, with both numbers.
- **Levels are still written in one place.** The kept result goes through
  `SkillLearningService.apply_evaluation`, which is the only level writer (ADR-0007). A
  training run row records what happened and points at the evaluation that set the level;
  it never sets one itself.
- **Trained instructions live beside the package, not over it.** Training writes
  `trained.md` (and the candidate as `trained.json`) into the installed skill folder;
  `instructions.md` is untouched, so the shipped text is always recoverable and "undo
  training" is a file deletion. Reverting deliberately leaves the level alone — it was
  measured, and reverting measures nothing.
- **Budget, target and focus are the spec's qualifiers, resolved to numbers.** A duration
  becomes a wall-clock budget (default 15 minutes, 1 minute to 8 hours); a target level
  stops the search once the check split reaches it; a focus area narrows practice to that
  area when enough tasks remain, and says so plainly when it does not. Whatever the
  budget, a round in progress is always finished rather than abandoned half-scored.
- **Checkpoints are the run row.** Every round is persisted as it completes, along with the
  best candidate so far. A run interrupted by a crash is marked interrupted on the next
  start, keeps that candidate, and the next training run for that skill resumes from it —
  unless the package version has changed, in which case instructions built for the old
  package are discarded.
- **Progress is an estimate derived from measurement, not a guess.** Rounds cannot be
  counted in advance, so the job's total is re-projected after every round from the
  measured round time and the remaining budget, and the UI labels it as estimated.

## Consequences

- Training genuinely improves what the user sees: trained instructions are what
  `instructions_for_prompt` injects into chat, so a skill that measured better also behaves
  differently in conversation. Because trained text is longer, the prompt budget now falls
  back to a skill's package instructions rather than dropping the skill when space runs
  short.
- The gains are bounded by what instructions can do. A model that ignores its instructions
  gains nothing, and the run will say nothing was kept. That is the honest outcome, and it
  is a supported result rather than a failure.
- Practice sets are content we have to write and keep solvable: 12 tasks per skill, with
  reference answers in the test suite proving each is satisfiable as written.
- Weight-level training (a LoRA adapter, say) is not ruled out forever. If it arrives it
  will be a different mechanism under the same command, and the same rule will apply: the
  level changes only when the benchmark says so.
