"""Training as a user-facing feature: preview it, run it, record it, keep or discard it.

The search itself lives in :mod:`myai_core.skills.training`. This module is the part with
consequences: it resolves what the user asked for into a plan, keeps the run's record up
to date while it works (so a crash leaves both an explanation and the best candidate
found), writes the trained instructions into the installed skill package when — and only
when — the benchmark says they are better, and keeps the level-writing rule intact: the
level is set by :meth:`SkillLearningService.apply_evaluation` from a benchmark run, never
from the training search.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.audit.service import AuditCategory, AuditService
from myai_core.db.models import SkillState, TrainingRun
from myai_core.hardware.benchmark import BenchmarkResult
from myai_core.schemas import ApiModel
from myai_core.skills.catalog import get_skill
from myai_core.skills.evaluate import EvaluationOutcome, level_from_score
from myai_core.skills.learning import LearningError
from myai_core.skills.packages import TRAINED, SkillPackage
from myai_core.skills.training import Candidate, RoundRecord, TrainingOutcome, TrainingPlan

DEFAULT_BUDGET_SECONDS = 15 * 60
MIN_BUDGET_SECONDS = 60
MAX_BUDGET_SECONDS = 8 * 60 * 60
ESTIMATED_TOKENS_PER_TASK = 60
MAX_ROUNDS = 40


class TrainRoundRead(ApiModel):
    index: int
    source: str
    change: str
    search_score: float
    check_score: float
    accepted: bool
    seconds: float


class TrainingRunRead(ApiModel):
    id: int
    skill_id: str
    job_id: str | None
    model_id: str
    status: str
    budget_seconds: float
    target_level: int | None
    focus_area: str | None
    rounds_completed: int
    rounds: list[TrainRoundRead] = Field(default_factory=list)
    baseline_practice: float | None
    best_practice: float | None
    benchmark_before: float | None
    benchmark_after: float | None
    level_before: int | None
    level_after: int | None
    applied: bool
    summary: str
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TrainPreview(ApiModel):
    """What ``/train <skill>`` shows before anything starts (spec §37)."""

    skill_id: str
    name: str
    icon: str
    learned: bool
    trainable: bool
    blockers: list[str] = Field(description="Why training cannot start; empty when it can.")
    model_id: str | None
    current_level: int
    target_level: int | None
    recommended_target: int
    areas: list[str]
    last_area_scores: dict[str, float]
    focus_area: str | None
    focus_note: str
    budget_minutes: float
    budget_note: str
    practice_tasks: int
    search_tasks: int
    check_tasks: int
    estimated_rounds_min: int | None
    estimated_rounds_max: int | None
    estimate_note: str
    resume_rounds: int = Field(
        default=0, description="Rounds already banked by an earlier run this will continue from."
    )
    what_happens: str


class TrainingService:
    def __init__(self, session: Session, ai_id: str) -> None:
        self._session = session
        self._ai_id = ai_id

    # --- preview ----------------------------------------------------------------------------

    def preview(
        self,
        package: SkillPackage | None,
        *,
        skill_id: str,
        learned: bool,
        current_level: int,
        area_scores: dict[str, float],
        active_model_id: str | None,
        runtime_available: bool,
        duration_seconds: int | None = None,
        target_level: int | None = None,
        specialization: str | None = None,
        all_areas: bool = False,
        measured: BenchmarkResult | None = None,
        time_limit_minutes: int | None = None,
    ) -> TrainPreview:
        skill = get_skill(skill_id)
        if skill is None:
            raise LearningError(f"Unknown skill '{skill_id}'.")
        blockers: list[str] = []
        if not learned:
            blockers.append(f"Learn {skill.name} first: /learn {skill_id}.")
        if package is None or package.practice is None:
            blockers.append(
                f"{skill.name} has no practice set in this build, so there is nothing to "
                "train against yet."
            )
        if not runtime_available:
            blockers.append("The local inference runtime is not available.")
        elif active_model_id is None:
            blockers.append("No local model is installed; training answers practice tasks with it.")

        budget, budget_note = _resolve_budget(duration_seconds, time_limit_minutes)
        focus, focus_note = _resolve_focus(
            package, area_scores, specialization=specialization, all_areas=all_areas
        )
        counts = _split_counts(package, focus)
        est_min, est_max, note = _estimate_rounds(counts["search"], budget, measured)
        resume = self.resume_run(skill_id)
        return TrainPreview(
            skill_id=skill_id,
            name=skill.name,
            icon=skill.icon,
            learned=learned,
            trainable=not blockers,
            blockers=blockers,
            model_id=active_model_id,
            current_level=current_level,
            target_level=target_level,
            recommended_target=min(100, current_level + 4),
            areas=list(package.benchmark.areas) if package else [],
            last_area_scores=area_scores,
            focus_area=focus,
            focus_note=focus_note,
            budget_minutes=round(budget / 60, 1),
            budget_note=budget_note,
            practice_tasks=counts["practice"],
            search_tasks=counts["search"],
            check_tasks=counts["check"],
            estimated_rounds_min=est_min,
            estimated_rounds_max=est_max,
            estimate_note=note,
            resume_rounds=resume.rounds_completed if resume else 0,
            what_happens=(
                f"Training tries changes to the instructions {skill.name} follows — short rules "
                "from its package, rules your AI writes for itself after a mistake, and worked "
                "examples — and keeps a change only when it scores higher on practice tasks the "
                "benchmark never uses. Your model's weights are not changed and nothing is "
                f"downloaded. At the end the {skill.name} benchmark decides whether the result "
                "is kept, and only that benchmark can change the level."
            ),
        )

    def plan(self, preview: TrainPreview, *, seed: int | None = None) -> TrainingPlan:
        return TrainingPlan(
            budget_seconds=preview.budget_minutes * 60,
            target_level=preview.target_level,
            focus_area=preview.focus_area,
            seed=seed if seed is not None else int(datetime.now(tz=UTC).timestamp()) % 100_000,
            max_rounds=MAX_ROUNDS,
        )

    # --- run records ------------------------------------------------------------------------

    def begin(
        self,
        skill_id: str,
        *,
        job_id: str | None,
        model_id: str,
        package_version: str,
        plan: TrainingPlan,
    ) -> TrainingRun:
        run = TrainingRun(
            ai_id=self._ai_id,
            skill_id=skill_id,
            job_id=job_id,
            model_id=model_id,
            package_version=package_version,
            status="running",
            budget_seconds=plan.budget_seconds,
            target_level=plan.target_level,
            focus_area=plan.focus_area,
            seed=plan.seed,
            summary="Training started.",
        )
        self._session.add(run)
        self._session.flush()
        return run

    def record_round(self, run_id: int, record: RoundRecord, best: Candidate) -> None:
        """Persist one round. Called after every round so a crash cannot lose the search."""
        run = self._session.get(TrainingRun, run_id)
        if run is None:
            return
        rounds = list(run.rounds)
        rounds.append(record.model_dump(mode="json"))
        run.rounds = rounds
        run.rounds_completed = len(rounds)
        run.best_candidate = best.model_dump(mode="json")
        self._session.flush()

    def resume_run(self, skill_id: str) -> TrainingRun | None:
        """The most recent run whose best candidate is worth continuing from."""
        stmt = (
            select(TrainingRun)
            .where(
                TrainingRun.ai_id == self._ai_id,
                TrainingRun.skill_id == skill_id,
                TrainingRun.rounds_completed > 0,
            )
            .order_by(TrainingRun.started_at.desc(), TrainingRun.id.desc())
        )
        run = self._session.scalars(stmt.limit(1)).first()
        if run is None or not run.best_candidate:
            return None
        return run

    def resume_candidate(self, skill_id: str, package_version: str) -> Candidate | None:
        run = self.resume_run(skill_id)
        if run is None or run.package_version != package_version:
            return None  # a changed package invalidates instructions built for the old one
        try:
            return Candidate.model_validate(run.best_candidate)
        except ValueError:
            return None

    def interrupt(self, run_id: int, reason: str) -> None:
        run = self._session.get(TrainingRun, run_id)
        if run is None or run.finished_at is not None:
            return
        run.status = "interrupted"
        run.summary = reason
        run.finished_at = datetime.now(tz=UTC)
        self._session.flush()

    def complete(
        self,
        run_id: int,
        *,
        outcome: TrainingOutcome,
        before: EvaluationOutcome,
        after: EvaluationOutcome | None,
        applied: bool,
        evaluation_id: int,
        level_before: int,
        level_after: int,
        summary: str,
    ) -> TrainingRun:
        run = self._session.get(TrainingRun, run_id)
        if run is None:
            raise LearningError(f"Training run {run_id} is missing.")
        run.rounds = [r.model_dump(mode="json") for r in outcome.rounds]
        run.rounds_completed = len(outcome.rounds)
        run.best_candidate = outcome.best.model_dump(mode="json")
        run.baseline_practice = outcome.baseline_check
        run.best_practice = outcome.best_check
        run.benchmark_before = before.score
        run.benchmark_after = after.score if after else None
        run.level_before = level_before
        run.level_after = level_after
        run.applied = applied
        run.evaluation_id = evaluation_id
        run.status = "applied" if applied else "kept_previous"
        run.summary = summary
        run.finished_at = datetime.now(tz=UTC)
        skill = get_skill(run.skill_id)
        name = skill.name if skill else run.skill_id
        AuditService(self._session).record(
            AuditCategory.SYSTEM,
            "skill_trained" if applied else "skill_training_kept_previous",
            f"{name}: {summary}",
            {
                "skill_id": run.skill_id,
                "rounds": run.rounds_completed,
                "benchmark_before": before.score,
                "benchmark_after": after.score if after else None,
                "level_before": level_before,
                "level_after": level_after,
                "applied": applied,
            },
        )
        self._session.flush()
        return run

    def history(self, skill_id: str | None = None, limit: int = 50) -> list[TrainingRun]:
        stmt = select(TrainingRun).where(TrainingRun.ai_id == self._ai_id)
        if skill_id is not None:
            stmt = stmt.where(TrainingRun.skill_id == skill_id)
        stmt = stmt.order_by(TrainingRun.started_at.desc(), TrainingRun.id.desc())
        return list(self._session.scalars(stmt.limit(limit)).all())

    def recover(self) -> int:
        """Mark runs left in progress by a crash. Their best candidate is kept (spec §74)."""
        stale = list(
            self._session.scalars(
                select(TrainingRun).where(
                    TrainingRun.ai_id == self._ai_id, TrainingRun.status == "running"
                )
            ).all()
        )
        for run in stale:
            run.status = "interrupted"
            run.finished_at = datetime.now(tz=UTC)
            run.summary = (
                "Interrupted: the service stopped before this run finished. The best "
                f"instructions it had found after {run.rounds_completed} rounds were kept, "
                "and training this skill again continues from them."
            )
        self._session.flush()
        return len(stale)

    # --- the trained instructions -------------------------------------------------------------

    def write_instructions(self, state: SkillState, text: str, candidate: Candidate) -> Path:
        """Store the trained instructions beside the package, leaving the package intact."""
        if not state.installed_path:
            raise LearningError("The skill package is not installed.")
        folder = Path(state.installed_path)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / TRAINED
        path.write_text(text.strip() + "\n", encoding="utf-8")
        (folder / "trained.json").write_text(
            json.dumps(candidate.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
        )
        state.trained_at = datetime.now(tz=UTC)
        state.version += 1
        self._session.flush()
        return path

    def clear_instructions(self, state: SkillState) -> bool:
        """Go back to the instructions the package shipped with."""
        if not state.installed_path:
            return False
        folder = Path(state.installed_path)
        removed = False
        for name in (TRAINED, "trained.json"):
            target = folder / name
            if target.is_file():
                target.unlink()
                removed = True
        if removed:
            state.trained_at = None
            state.version += 1
            self._session.flush()
        return removed


# --- resolution helpers ---------------------------------------------------------------------


def _resolve_budget(
    duration_seconds: int | None, time_limit_minutes: int | None = None
) -> tuple[float, str]:
    """Resolve the time budget, honouring the user's own job time limit (spec §31)."""
    ceiling = MAX_BUDGET_SECONDS
    ceiling_note = ""
    if time_limit_minutes is not None:
        ceiling = min(ceiling, time_limit_minutes * 60)
        ceiling_note = (
            f" Your time limit of {time_limit_minutes} minutes (Settings, advanced compute) "
            "is the ceiling."
        )
    requested = duration_seconds if duration_seconds is not None else DEFAULT_BUDGET_SECONDS
    clamped = max(MIN_BUDGET_SECONDS, min(ceiling, requested))
    if duration_seconds is None and clamped == DEFAULT_BUDGET_SECONDS:
        return (
            float(clamped),
            f"No duration given, so training runs for {DEFAULT_BUDGET_SECONDS // 60} minutes. "
            "Add one, for example '/train writing 1h'." + ceiling_note,
        )
    if clamped != requested:
        return (
            float(clamped),
            f"Adjusted to {int(clamped // 60)} minutes."
            + (
                ceiling_note
                or f" Training accepts {MIN_BUDGET_SECONDS // 60 or 1} minute to "
                f"{MAX_BUDGET_SECONDS // 3600} hours."
            ),
        )
    return (
        float(clamped),
        "A budget, not a promise: a round in progress is always finished." + ceiling_note,
    )


def _resolve_focus(
    package: SkillPackage | None,
    area_scores: dict[str, float],
    *,
    specialization: str | None,
    all_areas: bool,
) -> tuple[str | None, str]:
    areas = list(package.benchmark.areas) if package else []
    if all_areas or not areas:
        return None, "Practising every area."
    if specialization:
        wanted = specialization.strip().lower().replace(" ", "_")
        match = next((a for a in areas if a.lower() == wanted), None)
        if match:
            return match, f"Practising {match.replace('_', ' ')} tasks."
        return (
            None,
            f"'{specialization}' is not one of this skill's areas ({', '.join(areas)}), "
            "so every area is practised.",
        )
    scored = [(area_scores.get(a, 0.0), a) for a in areas]
    weakest = min(scored)[1] if scored else None
    if weakest is None:
        return None, "Practising every area."
    return (
        weakest,
        f"Practising {weakest.replace('_', ' ')}, the weakest area in the last benchmark. "
        "Add 'all' to practise everything.",
    )


def _split_counts(package: SkillPackage | None, focus: str | None) -> dict[str, int]:
    if package is None or package.practice is None:
        return {"practice": 0, "search": 0, "check": 0}
    from myai_core.skills.training import split_practice

    split = split_practice(package.practice, focus_area=focus)
    return {
        "practice": len(package.practice.tasks),
        "search": len(split.search),
        "check": len(split.check),
    }


def _estimate_rounds(
    search_tasks: int, budget_seconds: float, measured: BenchmarkResult | None
) -> tuple[int | None, int | None, str]:
    if not search_tasks:
        return None, None, "No practice tasks to estimate from."
    if (
        not measured
        or not measured.inference
        or measured.inference.generation_tokens_per_second <= 0
    ):
        return (
            None,
            None,
            "Run the hardware benchmark (Settings, or 'myai benchmark') for a round estimate.",
        )
    inference = measured.inference
    per_task = inference.prompt_seconds + ESTIMATED_TOKENS_PER_TASK / (
        inference.generation_tokens_per_second
    )
    per_round = per_task * search_tasks
    if per_round <= 0:
        return None, None, "Measured speed was too small to estimate from."
    rounds = budget_seconds / per_round
    return (
        max(0, int(rounds * 0.6)),
        max(1, int(rounds * 1.2)),
        f"Based on {inference.generation_tokens_per_second:g} tokens/s measured with "
        f"{inference.model_id}. A range, not a promise.",
    )


def apply_decision(
    before: EvaluationOutcome, after: EvaluationOutcome | None
) -> tuple[bool, str, EvaluationOutcome]:
    """Decide whether the trained instructions are kept, and say why in plain words.

    The comparison is between two benchmark runs made minutes apart with the same model,
    so it is as close to like-for-like as this program can get. A tie keeps the shipped
    instructions: an unproven change is not an improvement.
    """
    if after is None:
        return (
            False,
            "Training found nothing that scored better on practice, so the instructions are "
            f"unchanged. The benchmark was re-run: {round(before.score * 100)}%.",
            before,
        )
    before_pct, after_pct = round(before.score * 100), round(after.score * 100)
    if after.score > before.score:
        return (
            True,
            f"Trained instructions kept: the benchmark went from {before_pct}% to {after_pct}%.",
            after,
        )
    if after.score == before.score:
        return (
            False,
            f"Trained instructions discarded: the benchmark scored the same ({after_pct}%), "
            "and an unproven change is not an improvement.",
            before,
        )
    return (
        False,
        f"Trained instructions discarded: the benchmark fell from {before_pct}% to {after_pct}%. "
        "What looked better on practice did not hold on the benchmark.",
        before,
    )


def level_for(outcome: EvaluationOutcome) -> int:
    return level_from_score(outcome.score)
