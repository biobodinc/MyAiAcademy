"""Training a skill (spec §37, §38, §40): a measured search over how the AI is instructed.

What training is, exactly
-------------------------

Training **does not change the model's weights**. Fine-tuning a multi-gigabyte model is
not something this program can honestly do on the machines it targets, and claiming
otherwise would be a lie the user could not check.

What it does instead is real, measurable and theirs: it searches for a better set of
*instructions* for one skill — the text prepended to every request the AI answers for
that skill — and keeps a change only when the change measurably scores higher. Two kinds
of change are tried:

* **Tactics**: short rules. Some come from the skill package; others the model writes
  itself after seeing a task it got wrong. Either way a tactic survives only if it
  measures better.
* **Worked examples**: a practice task the model answered perfectly, kept as a
  demonstration.

Why the numbers can be trusted
------------------------------

The practice tasks training searches on are a different set from the benchmark tasks
that set the level (:class:`~myai_core.skills.packages.PracticeSet` enforces this), and
the practice tasks are themselves split:

* the **search split** decides whether a candidate looks better, and
* the **check split** must not get worse before the candidate is accepted.

That makes a gain that exists only on the tasks it was selected against fail to survive.
When training finishes, the winning instructions are measured once on the untouched
benchmark, through the same evaluation path a manual re-run uses, and that measurement —
not the search — is what may change the level. If the benchmark does not improve, the
previous instructions are kept and the run says so.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from pydantic import Field

from myai_core.models.provider import ChatMessage, GenerationOptions
from myai_core.schemas import ApiModel
from myai_core.skills.evaluate import (
    BENCHMARK_STYLE,
    Generate,
    JobControl,
    TaskOutcome,
    mean_score,
    run_tasks,
)
from myai_core.skills.packages import BenchmarkTask, PracticeSet

MAX_TACTICS = 6
MAX_EXEMPLARS = 2
TACTIC_MAX_CHARS = 160
EXEMPLAR_MAX_CHARS = 200
"""Worked examples are kept short so trained instructions still fit the chat prompt."""
MIN_CHECK_TASKS = 2
IMPROVEMENT_EPSILON = 1e-9
"""A candidate must score strictly higher, not merely round to the same number."""

TACTICS_HEADING = "## Practised guidance"
EXAMPLES_HEADING = "## Worked examples"
_TACTIC_CLEAN_RE = re.compile(
    r"^[\s\-*•\d.)\"'`\u201c\u201d\u2018\u2019]+"
    r"|[\s\"'`\u201c\u201d\u2018\u2019]+$"
)


class Exemplar(ApiModel):
    """A practice task the model itself answered perfectly, kept as a demonstration."""

    task_id: str
    prompt: str
    answer: str


class Candidate(ApiModel):
    """One set of instructions under test. The empty candidate is the package as shipped."""

    tactics: list[str] = Field(default_factory=list)
    exemplars: list[Exemplar] = Field(default_factory=list)

    def render(self, base_instructions: str) -> str:
        parts = [base_instructions.strip()]
        if self.tactics:
            parts.append(TACTICS_HEADING + "\n" + "\n".join(f"- {t}" for t in self.tactics))
        if self.exemplars:
            examples = "\n\n".join(
                f"Task: {e.prompt.strip()}\nGood answer: {e.answer.strip()}" for e in self.exemplars
            )
            parts.append(EXAMPLES_HEADING + "\n" + examples)
        return "\n\n".join(parts)

    @property
    def is_empty(self) -> bool:
        return not self.tactics and not self.exemplars


class RoundRecord(ApiModel):
    """One attempt, kept whether or not it worked: the record of what training tried."""

    index: int
    source: str = ""
    """Where the change came from: ``package``, ``model``, ``example`` or ``drop``."""
    change: str
    search_score: float
    check_score: float
    accepted: bool
    seconds: float


class TrainingOutcome(ApiModel):
    rounds: list[RoundRecord]
    baseline_search: float
    baseline_check: float
    best: Candidate
    best_search: float
    best_check: float
    stopped_because: str
    seconds: float

    @property
    def improved_on_practice(self) -> bool:
        """Whether the search found anything better on the split it did not select on."""
        return self.best_check > self.baseline_check + IMPROVEMENT_EPSILON


RoundCallback = Callable[[RoundRecord, "Candidate"], None]
"""Called after every round so progress and the best-so-far can be persisted."""
LevelFn = Callable[[float], int]


@dataclass(frozen=True, slots=True)
class TrainingPlan:
    """What the user asked for (spec §37 qualifiers), already resolved to numbers."""

    budget_seconds: float
    target_level: int | None = None
    focus_area: str | None = None
    seed: int = 0
    max_rounds: int = 40


@dataclass(frozen=True, slots=True)
class PracticeSplit:
    search: tuple[BenchmarkTask, ...]
    check: tuple[BenchmarkTask, ...]


def split_practice(practice: PracticeSet, *, focus_area: str | None = None) -> PracticeSplit:
    """Split practice tasks into the ones that choose and the ones that confirm.

    Deterministic (sorted by id, then every third task to the check split) so a run can
    be repeated and a stored result can be re-derived.
    """
    tasks = sorted(practice.tasks, key=lambda t: t.id)
    if focus_area:
        focused = [t for t in tasks if t.area == focus_area]
        # Keep the rest when focusing would leave too few tasks to measure anything.
        if len(focused) >= MIN_CHECK_TASKS * 2:
            tasks = focused
    check = tuple(t for i, t in enumerate(tasks) if i % 3 == 2)
    search = tuple(t for i, t in enumerate(tasks) if i % 3 != 2)
    if len(check) < MIN_CHECK_TASKS:  # tiny sets: confirm on everything rather than nothing
        return PracticeSplit(search=tuple(tasks), check=tuple(tasks))
    return PracticeSplit(search=search, check=check)


def clean_tactic(text: str) -> str:
    """Reduce a model's reply to one short rule, or to nothing if it is not usable."""
    first = next((line for line in text.strip().splitlines() if line.strip()), "")
    cleaned = _TACTIC_CLEAN_RE.sub("", first).strip()
    cleaned = " ".join(cleaned.split())
    if len(cleaned) < 8 or len(cleaned) > TACTIC_MAX_CHARS:
        return ""
    return cleaned


def ask_for_tactic(generate: Generate, failure: TaskOutcome, prompt: str) -> str:
    """Ask the model to write the rule that would have saved it. Validated by measurement.

    This is the one place where the model writes its own instructions. Nothing it says is
    trusted: the reply is reduced to a single short line and then has to earn its place by
    scoring better, exactly like a line that came from the package.
    """
    request = (
        "You answered a task incorrectly. Write one short rule that would have avoided "
        "the mistake, in at most 20 words. Reply with the rule only, no explanation.\n\n"
        f"Task: {prompt.strip()[:600]}\n"
        f"Your answer: {failure.answer.strip()[:400]}\n"
        f"Why it was marked wrong: {'; '.join(failure.details)[:300]}"
    )
    messages = [
        ChatMessage(role="system", content="You improve instructions. Be terse and concrete."),
        ChatMessage(role="user", content=request),
    ]
    reply = "".join(
        chunk.text
        for chunk in generate(messages, GenerationOptions(max_tokens=48, temperature=0.0))
    )
    return clean_tactic(reply)


class _Proposer:
    """Chooses the next change to try. Seeded, so a run is reproducible."""

    def __init__(self, library: Sequence[str], seed: int) -> None:
        self._library = list(library)
        # Reproducibility, not secrecy: the same seed must replay the same search.
        self._rng = random.Random(seed)  # noqa: S311

    def propose(
        self,
        current: Candidate,
        *,
        failures: Sequence[tuple[BenchmarkTask, TaskOutcome]],
        solved: Sequence[tuple[BenchmarkTask, TaskOutcome]],
        generate: Generate | None,
    ) -> tuple[Candidate, str, str] | None:
        """Return (candidate, source, human description), or None when nothing is left."""
        moves: list[str] = []
        unused = [t for t in self._library if t not in current.tactics]
        if unused and len(current.tactics) < MAX_TACTICS:
            moves.append("package")
        if generate is not None and failures and len(current.tactics) < MAX_TACTICS:
            moves.append("model")
        if solved and len(current.exemplars) < MAX_EXEMPLARS:
            moves.append("example")
        if len(current.tactics) > 1:
            moves.append("drop")
        self._rng.shuffle(moves)
        # One kind of change failing to produce anything usable (a model that writes an
        # unusable rule, an example already in the candidate) is not the end of the
        # search: fall through to the next kind, and give up only when all are spent.
        for source in moves:
            attempt = self._attempt(source, current, unused, failures, solved, generate)
            if attempt is not None:
                return attempt
        return None

    def _attempt(
        self,
        source: str,
        current: Candidate,
        unused: Sequence[str],
        failures: Sequence[tuple[BenchmarkTask, TaskOutcome]],
        solved: Sequence[tuple[BenchmarkTask, TaskOutcome]],
        generate: Generate | None,
    ) -> tuple[Candidate, str, str] | None:
        if source == "package":
            tactic = unused[self._rng.randrange(len(unused))]
            return self._with_tactic(current, tactic), source, f"Added guidance: {tactic}"
        if source == "model" and generate is not None:
            task, outcome = failures[self._rng.randrange(len(failures))]
            tactic = ask_for_tactic(generate, outcome, task.prompt)
            if not tactic or tactic in current.tactics:
                return None
            return (
                self._with_tactic(current, tactic),
                source,
                f"Your AI wrote a rule for itself after '{task.id}': {tactic}",
            )
        if source == "example":
            task, outcome = solved[self._rng.randrange(len(solved))]
            if any(e.task_id == task.id for e in current.exemplars):
                return None
            exemplar = Exemplar(
                task_id=task.id,
                prompt=task.prompt[:EXEMPLAR_MAX_CHARS],
                answer=outcome.answer[:EXEMPLAR_MAX_CHARS],
            )
            return (
                current.model_copy(update={"exemplars": [*current.exemplars, exemplar]}),
                source,
                f"Added a worked example from '{task.id}'",
            )
        dropped = current.tactics[self._rng.randrange(len(current.tactics))]
        kept = [t for t in current.tactics if t != dropped]
        return (
            current.model_copy(update={"tactics": kept}),
            "drop",
            f"Removed guidance to see if it was carrying its weight: {dropped}",
        )

    @staticmethod
    def _with_tactic(current: Candidate, tactic: str) -> Candidate:
        return current.model_copy(update={"tactics": [*current.tactics, tactic]})


def train_skill(
    *,
    base_instructions: str,
    practice: PracticeSet,
    generate: Generate,
    plan: TrainingPlan,
    start_from: Candidate | None = None,
    control: JobControl | None = None,
    on_round: RoundCallback | None = None,
    before_round: Callable[[], None] | None = None,
    level_from_score: LevelFn | None = None,
) -> TrainingOutcome:
    """Search for better instructions within a time budget. Returns what it measured.

    ``start_from`` resumes from a previous run's best candidate: that is what makes a
    training run survive a restart (spec §40 checkpoints). ``before_round`` is where a
    caller enforces machine limits (spec §31): it runs between rounds and may block.
    """
    control = control or JobControl()
    split = split_practice(practice, focus_area=plan.focus_area)
    started = time.monotonic()
    rounds: list[RoundRecord] = []

    def score(candidate: Candidate, tasks: Sequence[BenchmarkTask]) -> list[TaskOutcome]:
        return run_tasks(
            tasks,
            generate,
            system=f"{candidate.render(base_instructions)}\n\n{BENCHMARK_STYLE}",
            default_max_tokens=practice.default_max_tokens,
            control=control,
        )

    baseline = Candidate()
    baseline_search_outcomes = score(baseline, split.search)
    baseline_check_outcomes = score(baseline, split.check)
    baseline_search = mean_score(baseline_search_outcomes)
    baseline_check = mean_score(baseline_check_outcomes)

    best = baseline
    best_search, best_check = baseline_search, baseline_check
    last_outcomes = baseline_search_outcomes
    if start_from is not None and not start_from.is_empty:
        resumed_search = score(start_from, split.search)
        resumed_check = score(start_from, split.check)
        if mean_score(resumed_check) >= best_check:
            best = start_from
            best_search, best_check = mean_score(resumed_search), mean_score(resumed_check)
            last_outcomes = resumed_search

    proposer = _Proposer(practice.tactics, plan.seed)
    stopped = "the budget ran out"
    by_id = {t.id: t for t in split.search}

    while True:
        control.checkpoint()
        if before_round is not None:
            before_round()
            control.checkpoint()
        elapsed = time.monotonic() - started
        if len(rounds) >= plan.max_rounds:
            stopped = f"it reached the {plan.max_rounds}-round limit"
            break
        per_round = _average_round_seconds(rounds, elapsed)
        if elapsed + per_round > plan.budget_seconds:
            break
        if (
            plan.target_level is not None
            and level_from_score is not None
            and level_from_score(best_check) >= plan.target_level
        ):
            stopped = f"practice reached the level {plan.target_level} you asked for"
            break

        failures = [(by_id[o.task_id], o) for o in last_outcomes if not o.passed]
        solved = [(by_id[o.task_id], o) for o in last_outcomes if o.passed]
        round_started = time.monotonic()
        proposal = proposer.propose(best, failures=failures, solved=solved, generate=generate)
        if proposal is None:
            stopped = "it ran out of changes worth trying"
            break
        candidate, source, change = proposal

        search_outcomes = score(candidate, split.search)
        search_score = mean_score(search_outcomes)
        improved = search_score > best_search + IMPROVEMENT_EPSILON
        check_score = best_check
        if improved:
            # Only pay for the check split when the candidate is worth confirming.
            check_score = mean_score(score(candidate, split.check))
        accepted = improved and check_score >= best_check - IMPROVEMENT_EPSILON
        if accepted:
            best, best_search, best_check = candidate, search_score, check_score
            last_outcomes = search_outcomes
        rounds.append(
            RoundRecord(
                index=len(rounds) + 1,
                source=source,
                change=change,
                search_score=search_score,
                check_score=check_score,
                accepted=accepted,
                seconds=round(time.monotonic() - round_started, 2),
            )
        )
        if on_round is not None:
            on_round(rounds[-1], best)

    return TrainingOutcome(
        rounds=rounds,
        baseline_search=baseline_search,
        baseline_check=baseline_check,
        best=best,
        best_search=best_search,
        best_check=best_check,
        stopped_because=stopped,
        seconds=round(time.monotonic() - started, 2),
    )


def _average_round_seconds(rounds: Sequence[RoundRecord], elapsed: float) -> float:
    """How long to expect the next round to take, from what this run has measured."""
    if not rounds:
        return elapsed  # the baseline runs cost about what one round will
    recent = [r.seconds for r in rounds[-3:]]
    return sum(recent) / len(recent)
