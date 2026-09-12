"""The training search: does it find a real gain, and does it refuse a fake one?

The model here is scripted so the tests are about the search, not about any particular
local model. Two scripted behaviours matter:

* a model that follows one specific rule when it is present — training must find it;
* a model that is simply noisy — training must not report an improvement.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest

from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions
from myai_core.skills.evaluate import JobCancelledError, JobControl, level_from_score
from myai_core.skills.packages import BenchmarkTask, PracticeSet
from myai_core.skills.training import (
    Candidate,
    Exemplar,
    TrainingPlan,
    clean_tactic,
    split_practice,
    train_skill,
)

RULE = "Reply with the single word asked for and nothing else."
BASE = "You are helpful."


def _practice(tactics: list[str] | None = None) -> PracticeSet:
    words = ["ok", "yes", "red", "four", "north", "blue", "left", "two", "up"]
    return PracticeSet(
        version="1.0.0",
        default_max_tokens=32,
        tactics=tactics if tactics is not None else [RULE, "Be friendly and chatty."],
        tasks=[
            BenchmarkTask(
                id=f"t{i:02d}",
                area="instruction_following",
                prompt=f"Reply with only the word {word}.",
                checks=[{"type": "exact", "expected": [word]}],
            )
            for i, word in enumerate(words)
        ],
    )


class ScriptedModel:
    """Answers correctly only when the rule is in its instructions."""

    def __init__(self, rule: str = RULE, tactic_reply: str = "") -> None:
        self.rule = rule
        self.tactic_reply = tactic_reply
        self.calls = 0

    def __call__(
        self, messages: list[ChatMessage], options: GenerationOptions
    ) -> Iterator[GenerationChunk]:
        self.calls += 1
        system = messages[0].content
        prompt = messages[-1].content
        if "Write one short rule" in prompt:
            yield GenerationChunk(text=self.tactic_reply)
            return
        word = prompt.rstrip(".").split()[-1]
        follows = self.rule in system
        yield GenerationChunk(text=word if follows else f"Sure! Here you go: {word}, my friend.")


def test_practice_split_never_shares_a_task() -> None:
    split = split_practice(_practice())
    assert split.search and split.check
    assert not ({t.id for t in split.search} & {t.id for t in split.check})
    assert split_practice(_practice()).check == split.check  # deterministic


def test_focus_narrows_only_when_enough_tasks_remain() -> None:
    practice = _practice()
    practice.tasks[0].area = "clarity"
    # One task in 'clarity' is too few to measure, so the whole set is kept.
    assert len(split_practice(practice, focus_area="clarity").search) > 1
    kept = split_practice(practice, focus_area="instruction_following")
    assert all(t.area == "instruction_following" for t in (*kept.search, *kept.check))


def test_training_finds_the_rule_that_actually_helps() -> None:
    model = ScriptedModel()
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(),
        generate=model,
        plan=TrainingPlan(budget_seconds=30, seed=1, max_rounds=8),
    )
    assert outcome.baseline_check == 0.0
    assert outcome.improved_on_practice
    assert RULE in outcome.best.tactics
    assert outcome.best_check == 1.0
    accepted = [r for r in outcome.rounds if r.accepted]
    assert accepted and accepted[0].source in {"package", "model"}
    assert all(r.change for r in outcome.rounds)


def test_training_reports_no_improvement_when_there_is_none() -> None:
    """A model that ignores its instructions must not produce a claimed gain."""
    model = ScriptedModel(rule="a rule nothing will ever contain")
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(),
        generate=model,
        plan=TrainingPlan(budget_seconds=30, seed=3, max_rounds=6),
    )
    assert not outcome.improved_on_practice
    assert outcome.best.is_empty
    assert not any(r.accepted for r in outcome.rounds)


def test_a_model_written_rule_is_tried_and_kept_only_if_it_measures_better() -> None:
    model = ScriptedModel(tactic_reply=f"  - “{RULE}”  ")
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(tactics=[]),  # nothing in the package: the model must write it
        generate=model,
        plan=TrainingPlan(budget_seconds=30, seed=2, max_rounds=6),
    )
    assert outcome.improved_on_practice
    assert outcome.best.tactics == [RULE]
    assert any(r.source == "model" for r in outcome.rounds)


def test_the_budget_is_respected_even_when_rounds_appear_to_cost_nothing() -> None:
    """A budget that cannot expire is not a budget.

    Windows' ``time.monotonic`` ticks about every 16 ms, which is longer than a round with
    a scripted model takes, so rounds there measured as free and an estimate-only check
    never fired. The loop therefore stops on the elapsed budget itself as well as on its
    estimate of the next round.
    """
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(),
        generate=ScriptedModel(),
        plan=TrainingPlan(budget_seconds=0.0, seed=1, max_rounds=40),
    )
    assert outcome.rounds == []
    assert outcome.stopped_because == "the budget ran out"


def test_the_round_limit_is_respected() -> None:
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(tactics=[f"filler rule {i}" for i in range(20)]),
        generate=ScriptedModel(rule="never present"),
        plan=TrainingPlan(budget_seconds=60, seed=5, max_rounds=3),
    )
    assert len(outcome.rounds) == 3
    assert "3-round limit" in outcome.stopped_because


def test_a_target_level_stops_the_search_early() -> None:
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(),
        generate=ScriptedModel(),
        plan=TrainingPlan(budget_seconds=60, seed=1, target_level=50, max_rounds=20),
        level_from_score=level_from_score,
    )
    assert "level 50" in outcome.stopped_because


def test_stopping_is_honoured_between_tasks() -> None:
    control = JobControl()
    control.cancel.set()
    with pytest.raises(JobCancelledError):
        train_skill(
            base_instructions=BASE,
            practice=_practice(),
            generate=ScriptedModel(),
            plan=TrainingPlan(budget_seconds=30, seed=1),
            control=control,
        )


def test_pausing_blocks_until_resumed() -> None:
    control = JobControl()
    control.paused.set()
    finished = threading.Event()

    def run() -> None:
        train_skill(
            base_instructions=BASE,
            practice=_practice(),
            generate=ScriptedModel(),
            plan=TrainingPlan(budget_seconds=30, seed=1, max_rounds=2),
            control=control,
        )
        finished.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert not finished.wait(0.3)
    control.paused.clear()
    assert finished.wait(10)


def test_the_same_seed_replays_the_same_search() -> None:
    def run(seed: int) -> list[str]:
        outcome = train_skill(
            base_instructions=BASE,
            practice=_practice(tactics=[f"rule {i}" for i in range(6)]),
            generate=ScriptedModel(rule="never present"),
            plan=TrainingPlan(budget_seconds=60, seed=seed, max_rounds=4),
        )
        return [r.change for r in outcome.rounds]

    assert run(11) == run(11)
    assert run(11) != run(12)


def test_training_resumes_from_a_stored_candidate() -> None:
    """A run interrupted by a restart keeps its best candidate; the next run starts there."""
    stored = Candidate(tactics=[RULE])
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(),
        generate=ScriptedModel(),
        plan=TrainingPlan(budget_seconds=30, seed=4, max_rounds=1),
        start_from=stored,
    )
    assert outcome.best_check == 1.0
    assert RULE in outcome.best.tactics


def test_a_resumed_candidate_that_is_worse_is_dropped() -> None:
    outcome = train_skill(
        base_instructions=BASE,
        practice=_practice(),
        generate=ScriptedModel(rule="never present"),
        plan=TrainingPlan(budget_seconds=30, seed=4, max_rounds=1),
        start_from=Candidate(tactics=["a rule that does nothing"]),
    )
    # It scored the same, not better, so the shipped instructions stay the baseline.
    assert outcome.best_check == outcome.baseline_check


def test_rendered_instructions_keep_the_package_text_first() -> None:
    candidate = Candidate(
        tactics=["Answer in one word."],
        exemplars=[Exemplar(task_id="t1", prompt="Say ok.", answer="ok")],
    )
    text = candidate.render(BASE)
    assert text.startswith(BASE)
    assert "- Answer in one word." in text
    assert "Task: Say ok.\nGood answer: ok" in text
    assert Candidate().render(BASE) == BASE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('  "Answer in one word."  ', "Answer in one word."),
        ("- Answer in one word.\nAnd here is why...", "Answer in one word."),
        ("1. Answer in one word.", "Answer in one word."),
        ("ok", ""),  # too short to be a rule
        ("x" * 400, ""),  # a paragraph, not a rule
        ("", ""),
    ],
)
def test_a_model_written_rule_is_reduced_to_one_usable_line(raw: str, expected: str) -> None:
    assert clean_tactic(raw) == expected
