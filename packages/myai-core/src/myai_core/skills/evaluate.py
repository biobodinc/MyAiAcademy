"""Run a skill benchmark against the local model (spec §43, §89).

The runner is backend-agnostic: it takes the same ``generate`` callable chat uses. It is
cooperative about pausing and cancelling between tasks so a long benchmark obeys
``/pause``, ``/resume`` and ``/stop``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field

from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions
from myai_core.schemas import ApiModel
from myai_core.skills.graders import grade
from myai_core.skills.packages import BenchmarkTask, SkillPackage

Generate = Callable[[list[ChatMessage], GenerationOptions], Iterator[GenerationChunk]]
ProgressFn = Callable[[int, int], None]
ANSWER_EXCERPT_CHARS = 400
BENCHMARK_STYLE = (
    "You are being evaluated. Answer each task directly and follow its format exactly; "
    "do not add explanations unless asked."
)


class JobCancelledError(Exception):
    pass


@dataclass(slots=True)
class JobControl:
    cancel: threading.Event = field(default_factory=threading.Event)
    paused: threading.Event = field(default_factory=threading.Event)

    def checkpoint(self) -> None:
        """Block while paused; raise when cancelled."""
        while True:
            if self.cancel.is_set():
                raise JobCancelledError
            if not self.paused.is_set():
                return
            time.sleep(0.1)


class TaskOutcome(ApiModel):
    task_id: str
    area: str
    score: float
    passed: bool
    answer: str
    details: list[str]


class EvaluationOutcome(ApiModel):
    score: float
    area_scores: dict[str, float]
    tasks: list[TaskOutcome]
    duration_seconds: float


def level_from_score(score: float) -> int:
    """Levels are the benchmark score on a 1-100 scale; learned skills are at least 1."""
    return max(1, min(100, round(score * 100)))


def run_tasks(
    tasks: Sequence[BenchmarkTask],
    generate: Generate,
    *,
    system: str,
    default_max_tokens: int,
    control: JobControl | None = None,
    on_progress: ProgressFn | None = None,
) -> list[TaskOutcome]:
    """Answer and grade each task in order. Shared by benchmarking and training.

    Cooperative: ``control`` is checked between tasks, so a long run still obeys pause
    and stop.
    """
    control = control or JobControl()
    outcomes: list[TaskOutcome] = []
    for index, task in enumerate(tasks):
        control.checkpoint()
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=task.prompt),
        ]
        options = GenerationOptions(
            max_tokens=task.max_tokens or default_max_tokens, temperature=0.0
        )
        answer = "".join(chunk.text for chunk in generate(messages, options)).strip()
        score, results = grade(task.checks, answer, task.prompt)
        outcomes.append(
            TaskOutcome(
                task_id=task.id,
                area=task.area,
                score=score,
                passed=score >= 1.0,
                answer=answer[:ANSWER_EXCERPT_CHARS],
                details=[f"{r.check}: {r.detail}" for r in results],
            )
        )
        if on_progress:
            on_progress(index + 1, len(tasks))
    return outcomes


def mean_score(outcomes: Sequence[TaskOutcome]) -> float:
    return round(sum(o.score for o in outcomes) / len(outcomes), 4) if outcomes else 0.0


def evaluate_package(
    package: SkillPackage,
    generate: Generate,
    *,
    instructions: str | None = None,
    control: JobControl | None = None,
    on_progress: ProgressFn | None = None,
) -> EvaluationOutcome:
    """Run the package's benchmark. ``instructions`` overrides the package's own text,
    which is how a trained skill is measured with what training produced."""
    started = time.monotonic()
    outcomes = run_tasks(
        package.benchmark.tasks,
        generate,
        system=f"{instructions if instructions is not None else package.instructions}"
        f"\n\n{BENCHMARK_STYLE}",
        default_max_tokens=package.benchmark.default_max_tokens,
        control=control,
        on_progress=on_progress,
    )
    area_scores: dict[str, float] = {}
    for area in package.benchmark.areas:
        scores = [o.score for o in outcomes if o.area == area]
        area_scores[area] = round(sum(scores) / len(scores), 4) if scores else 0.0
    return EvaluationOutcome(
        score=mean_score(outcomes),
        area_scores=area_scores,
        tasks=outcomes,
        duration_seconds=round(time.monotonic() - started, 2),
    )
