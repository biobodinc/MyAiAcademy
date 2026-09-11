"""Glue between the API process state and skill jobs: create, run and finish them."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from myai_core.api.model_loading import ModelNotReadyError, resolve_active_model
from myai_core.db.models import Job
from myai_core.hardware.volumes import probe_volumes
from myai_core.models.service import ModelService
from myai_core.preferences.service import PreferencesService
from myai_core.skills.evaluate import JobControl, evaluate_package
from myai_core.skills.jobs import JobBusyError, JobKind
from myai_core.skills.learning import LearningError, SkillLearningService
from myai_core.skills.packages import SkillPackage
from myai_core.storage import StorageManager

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from myai_core.api.state import AppState


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
    else:  # pragma: no cover - train arrives in Phase 4
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Training jobs arrive in Phase 4.")

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


def _bundled(learning: SkillLearningService, skill_id: str) -> SkillPackage:
    try:
        return learning.installed_package(skill_id)
    except LearningError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _work_for(
    state: AppState, job_id: str, kind: JobKind, skill_id: str, ai_id: str
) -> Callable[[JobControl, Callable[[int, int], None]], dict[str, object]]:
    def work(control: JobControl, progress: Callable[[int, int], None]) -> dict[str, object]:
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
