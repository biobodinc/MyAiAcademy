"""Glue between the API process state and skill jobs: create, run and finish them."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from myai_core.api.model_loading import ModelNotReadyError, resolve_active_model
from myai_core.db.models import Job
from myai_core.hardware.benchmark_store import BenchmarkStore
from myai_core.hardware.metrics import probe_metrics
from myai_core.hardware.volumes import probe_volumes
from myai_core.models.service import ModelService
from myai_core.preferences.service import PreferencesService
from myai_core.skills.evaluate import JobControl, evaluate_package
from myai_core.skills.jobs import JobBusyError, JobKind
from myai_core.skills.learning import LearningError, SkillLearningService
from myai_core.skills.packages import SkillPackage
from myai_core.skills.trainer import TrainingService, TrainPreview, apply_decision
from myai_core.skills.training import Candidate, RoundRecord, TrainingPlan, train_skill
from myai_core.storage import StorageManager

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from myai_core.api.state import AppState

ProgressFn = Callable[[int, int], None]
BENCHMARK_UNITS = 2
"""Progress units reserved for the benchmark runs that decide whether training is kept."""
THERMAL_WAIT_SECONDS = 600.0
"""How long a round will wait for a machine over the user's temperature limit to cool."""
THERMAL_POLL_SECONDS = 5.0


def start_skill_job(
    state: AppState, session: Session, *, kind: JobKind, skill_id: str, ai_id: str
) -> Job:
    """Validate, create and start a ``learn`` or ``evaluate`` job. Raises HTTPException."""
    storage = StorageManager(session, probe_volumes)
    models = ModelService(session, storage)
    preferences = PreferencesService(session).get()
    learning = SkillLearningService(session, ai_id, storage)
    runtime_ok, _ = state.runtime.provider.availability()
    preview = learning.preview(
        skill_id,
        hardware=state.hardware_cache,
        measured=None,
        active_model_id=models.active_model_id(),
        runtime_available=runtime_ok,
    )
    if kind == "learn":
        if preview.already_learned:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{preview.name} is already learned. Re-run its benchmark with evaluate.",
            )
        if preview.blockers:
            raise HTTPException(status.HTTP_409_CONFLICT, " ".join(preview.blockers))
    elif kind == "evaluate":
        if not preview.already_learned:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Learn {preview.name} first: /learn {skill_id}"
            )
        model_blockers = [b for b in preview.blockers if "model" in b or "runtime" in b]
        if model_blockers:
            raise HTTPException(status.HTTP_409_CONFLICT, " ".join(model_blockers))
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Use start_training_job for a training job."
        )

    try:
        prepared = resolve_active_model(state, models, preferences)
    except ModelNotReadyError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    package = learning.installed_package(skill_id) if kind == "evaluate" else None
    total = (
        len(package.benchmark.tasks)
        if package
        else len(_bundled(learning, skill_id).benchmark.tasks)
    )
    try:
        job = state.jobs.create(
            session,
            kind=kind,
            ai_id=ai_id,
            skill_id=skill_id,
            model_id=prepared.model_id,
            compute_preset=preferences.compute_preset.value,
            total=total,
        )
    except JobBusyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()  # the worker reads the job row through its own session
    state.jobs.start(job.id, _work_for(state, job.id, kind, skill_id, ai_id))
    return job


def training_preview(
    state: AppState,
    session: Session,
    *,
    skill_id: str,
    ai_id: str,
    duration_seconds: int | None = None,
    target_level: int | None = None,
    specialization: str | None = None,
    all_areas: bool = False,
) -> TrainPreview:
    """What ``/train <skill>`` shows before anything starts. Starts nothing."""
    storage = StorageManager(session, probe_volumes)
    models = ModelService(session, storage)
    learning = SkillLearningService(session, ai_id, storage)
    runtime_ok, _ = state.runtime.provider.availability()
    skill_state = learning.state_for(skill_id)
    try:
        package = learning.installed_package(skill_id)
    except LearningError:
        package = None
    try:
        return TrainingService(session, ai_id).preview(
            package,
            skill_id=skill_id,
            learned=learning.is_learned(skill_id),
            current_level=skill_state.level if skill_state else 0,
            area_scores=learning.latest_area_scores().get(skill_id, {}),
            active_model_id=models.active_model_id(),
            runtime_available=runtime_ok,
            duration_seconds=duration_seconds,
            target_level=target_level,
            specialization=specialization,
            all_areas=all_areas,
            measured=BenchmarkStore(session).latest(),
            time_limit_minutes=PreferencesService(session).get().time_limit_minutes,
        )
    except LearningError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


def start_training_job(
    state: AppState,
    session: Session,
    *,
    skill_id: str,
    ai_id: str,
    duration_seconds: int | None = None,
    target_level: int | None = None,
    specialization: str | None = None,
    all_areas: bool = False,
    seed: int | None = None,
) -> Job:
    """Validate, create and start a ``train`` job (spec §37, §40)."""
    preview = training_preview(
        state,
        session,
        skill_id=skill_id,
        ai_id=ai_id,
        duration_seconds=duration_seconds,
        target_level=target_level,
        specialization=specialization,
        all_areas=all_areas,
    )
    if preview.blockers:
        raise HTTPException(status.HTTP_409_CONFLICT, " ".join(preview.blockers))

    storage = StorageManager(session, probe_volumes)
    models = ModelService(session, storage)
    preferences = PreferencesService(session).get()
    learning = SkillLearningService(session, ai_id, storage)
    try:
        prepared = resolve_active_model(state, models, preferences)
    except ModelNotReadyError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    package = learning.installed_package(skill_id)
    training = TrainingService(session, ai_id)
    plan = training.plan(preview, seed=seed)
    try:
        job = state.jobs.create(
            session,
            kind="train",
            ai_id=ai_id,
            skill_id=skill_id,
            model_id=prepared.model_id,
            compute_preset=preferences.compute_preset.value,
            # Rounds are not knowable in advance: this is the first live estimate and the
            # worker replaces it after every round.
            total=(preview.estimated_rounds_max or 1) + BENCHMARK_UNITS,
        )
    except JobBusyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    run = training.begin(
        skill_id,
        job_id=job.id,
        model_id=prepared.model_id,
        package_version=package.manifest.version,
        plan=plan,
    )
    session.commit()
    state.jobs.start(job.id, _training_work(state, job.id, run.id, skill_id, ai_id, plan))
    return job


def _bundled(learning: SkillLearningService, skill_id: str) -> SkillPackage:
    try:
        return learning.installed_package(skill_id)
    except LearningError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _work_for(
    state: AppState, job_id: str, kind: JobKind, skill_id: str, ai_id: str
) -> Callable[[JobControl, ProgressFn], dict[str, object]]:
    def work(control: JobControl, progress: ProgressFn) -> dict[str, object]:
        with state.session_factory() as session:
            storage = StorageManager(session, probe_volumes)
            models = ModelService(session, storage)
            preferences = PreferencesService(session).get()
            learning = SkillLearningService(session, ai_id, storage)
            prepared = resolve_active_model(state, models, preferences)
            if kind == "learn":
                package, _ = learning.install(skill_id)
            else:
                package = learning.installed_package(skill_id)
            session.commit()

        control.checkpoint()
        state.runtime.ensure_loaded(prepared.path, prepared.config)
        outcome = evaluate_package(
            package, state.runtime.generate, control=control, on_progress=progress
        )

        with state.session_factory() as session:
            storage = StorageManager(session, probe_volumes)
            learning = SkillLearningService(session, ai_id, storage)
            row = learning.apply_evaluation(
                skill_id,
                outcome,
                model_id=prepared.model_id,
                package_version=package.manifest.version,
                job_id=job_id,
            )
            session.commit()
            return {
                "score": outcome.score,
                "level_before": row.level_before,
                "level_after": row.level_after,
                "area_scores": outcome.area_scores,
                "duration_seconds": outcome.duration_seconds,
                "evaluation_id": row.id,
            }

    return work


def _training_work(
    state: AppState, job_id: str, run_id: int, skill_id: str, ai_id: str, plan: TrainingPlan
) -> Callable[[JobControl, ProgressFn], dict[str, object]]:
    """The training job: search, then let the benchmark decide whether to keep the result."""

    def work(control: JobControl, progress: ProgressFn) -> dict[str, object]:
        with state.session_factory() as session:
            storage = StorageManager(session, probe_volumes)
            models = ModelService(session, storage)
            preferences = PreferencesService(session).get()
            learning = SkillLearningService(session, ai_id, storage)
            package = learning.installed_package(skill_id)
            resume = TrainingService(session, ai_id).resume_candidate(
                skill_id, package.manifest.version
            )
            prepared = resolve_active_model(state, models, preferences)
            session.commit()
        if package.practice is None:  # pragma: no cover - the preview refuses this first
            raise LearningError(f"{skill_id} has no practice set to train against.")

        control.checkpoint()
        state.runtime.ensure_loaded(prepared.path, prepared.config)
        started = time.perf_counter()
        temperature_limit = preferences.temperature_limit_c

        def before_round() -> None:
            """Hold between rounds while the machine is hotter than the user allows (§31).

            Only acts on a temperature we can actually read: a GPU that reports one through
            nvidia-smi. There is no portable CPU temperature, so no limit is pretended.
            """
            if temperature_limit is None:
                return
            deadline = time.perf_counter() + THERMAL_WAIT_SECONDS
            while time.perf_counter() < deadline:
                control.checkpoint()
                gpu = probe_metrics(state.hardware_cache.gpus if state.hardware_cache else None).gpu
                if (
                    gpu is None
                    or gpu.temperature_c is None
                    or gpu.temperature_c <= temperature_limit
                ):
                    return
                time.sleep(THERMAL_POLL_SECONDS)

        def on_round(record: RoundRecord, best: Candidate) -> None:
            with state.session_factory() as session:
                TrainingService(session, ai_id).record_round(run_id, record, best)
                session.commit()
            progress(record.index, _projected_total(record.index, started, plan))

        outcome = train_skill(
            base_instructions=package.instructions,
            practice=package.practice,
            generate=state.runtime.generate,
            plan=plan,
            start_from=resume,
            control=control,
            on_round=on_round,
            before_round=before_round,
            level_from_score=_level_from_score,
        )

        # The benchmark, not the search, decides. Both runs happen now, with the same
        # model in the same state, so the comparison is like for like.
        done = len(outcome.rounds)
        total = done + BENCHMARK_UNITS
        control.checkpoint()
        before = evaluate_package(package, state.runtime.generate, control=control)
        progress(done + 1, total)
        after = None
        if not outcome.best.is_empty:
            control.checkpoint()
            after = evaluate_package(
                package,
                state.runtime.generate,
                instructions=outcome.best.render(package.instructions),
                control=control,
            )
        progress(total, total)

        applied, summary, kept = apply_decision(before, after)
        with state.session_factory() as session:
            storage = StorageManager(session, probe_volumes)
            learning = SkillLearningService(session, ai_id, storage)
            training = TrainingService(session, ai_id)
            skill_state = learning.state_for(skill_id)
            level_before = skill_state.level if skill_state else 0
            if applied and skill_state is not None:
                training.write_instructions(
                    skill_state, outcome.best.render(package.instructions), outcome.best
                )
            row = learning.apply_evaluation(
                skill_id,
                kept,
                model_id=prepared.model_id,
                package_version=package.manifest.version,
                job_id=job_id,
            )
            run = training.complete(
                run_id,
                outcome=outcome,
                before=before,
                after=after,
                applied=applied,
                evaluation_id=row.id,
                level_before=level_before,
                level_after=row.level_after,
                summary=summary,
            )
            session.commit()
            return {
                "training_run_id": run.id,
                "rounds": len(outcome.rounds),
                "accepted_rounds": sum(1 for r in outcome.rounds if r.accepted),
                "practice_before": outcome.baseline_check,
                "practice_after": outcome.best_check,
                "benchmark_before": before.score,
                "benchmark_after": after.score if after else None,
                "level_before": row.level_before,
                "level_after": row.level_after,
                "applied": applied,
                "summary": summary,
                "stopped_because": outcome.stopped_because,
                "evaluation_id": row.id,
            }

    return work


def _projected_total(done: int, started: float, plan: TrainingPlan) -> int:
    """A live estimate of the total rounds, from how long this run's rounds actually take.

    Guessing up front would be wrong in both directions; the bar is honest as long as it
    is derived from measured speed and the remaining budget.
    """
    elapsed = time.perf_counter() - started
    per_round = elapsed / done if done else 0.0
    remaining = max(0.0, plan.budget_seconds - elapsed)
    projected = done + (int(remaining / per_round) if per_round > 0 else 0)
    return min(plan.max_rounds, max(done, projected)) + BENCHMARK_UNITS


def _level_from_score(score: float) -> int:
    from myai_core.skills.evaluate import level_from_score

    return level_from_score(score)
