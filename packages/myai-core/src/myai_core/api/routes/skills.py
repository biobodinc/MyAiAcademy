from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import Field

from myai_core.api.deps import ProfileDep, SessionDep, SkillsDep, StateDep, StorageDep
from myai_core.db.models import AIProfile
from myai_core.hardware.benchmark_store import BenchmarkStore
from myai_core.models.service import ModelService
from myai_core.schemas import ApiModel
from myai_core.skills.jobs import JobRead
from myai_core.skills.learning import (
    EvaluationRead,
    LearningError,
    LearnPreview,
    SkillLearningService,
)
from myai_core.skills.pipeline import start_skill_job, start_training_job, training_preview
from myai_core.skills.service import SkillsSummary, SkillStatus
from myai_core.skills.trainer import TrainingRunRead, TrainingService, TrainPreview

router = APIRouter(prefix="/skills", tags=["skills"])


class TrainRequest(ApiModel):
    """Qualifiers from ``/train <skill> …`` (spec §38), already parsed."""

    duration_seconds: int | None = Field(default=None, ge=1, description="From '2h' or '90m'.")
    target_level: int | None = Field(default=None, ge=1, le=100)
    specialization: str | None = Field(default=None, description="One of the skill's areas.")
    all_areas: bool = False
    seed: int | None = Field(
        default=None, description="Fix the search's seed to repeat a run exactly."
    )


_NO_QUALIFIERS = TrainRequest()


@router.get("", response_model=SkillsSummary)
def read_skills(skills: SkillsDep, profile: ProfileDep) -> SkillsSummary:
    row = profile.get()
    return skills.summary(row.ai_id if row else None)


@router.get("/history", response_model=list[EvaluationRead])
def all_history(
    session: SessionDep,
    profile: ProfileDep,
    storage: StorageDep,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[EvaluationRead]:
    row = profile.get()
    if row is None:
        return []
    learning = SkillLearningService(session, row.ai_id, storage)
    return [EvaluationRead.model_validate(e) for e in learning.history(limit=limit)]


@router.get("/{skill_id}", response_model=SkillStatus)
def read_skill(skill_id: str, skills: SkillsDep, profile: ProfileDep) -> SkillStatus:
    row = profile.get()
    for item in skills.summary(row.ai_id if row else None).skills:
        if item.id == skill_id:
            return item
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown skill '{skill_id}'.")


@router.get("/{skill_id}/learn-preview", response_model=LearnPreview)
def learn_preview(
    skill_id: str, state: StateDep, session: SessionDep, profile: ProfileDep, storage: StorageDep
) -> LearnPreview:
    row = _require_profile(profile)
    learning = SkillLearningService(session, row.ai_id, storage)
    runtime_ok, _ = state.runtime.provider.availability()
    try:
        return learning.preview(
            skill_id,
            hardware=state.hardware_cache,
            measured=BenchmarkStore(session).latest(),
            active_model_id=ModelService(session, storage).active_model_id(),
            runtime_available=runtime_ok,
        )
    except LearningError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/{skill_id}/learn", response_model=JobRead, status_code=202)
def learn(skill_id: str, state: StateDep, session: SessionDep, profile: ProfileDep) -> JobRead:
    """Install the skill package and run its benchmark as a background job (spec §36)."""
    row = _require_profile(profile)
    try:
        job = start_skill_job(state, session, kind="learn", skill_id=skill_id, ai_id=row.ai_id)
    except LearningError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return JobRead.model_validate(job)


@router.post("/{skill_id}/evaluate", response_model=JobRead, status_code=202)
def evaluate(skill_id: str, state: StateDep, session: SessionDep, profile: ProfileDep) -> JobRead:
    """Re-run a learned skill's benchmark (for example after changing model)."""
    row = _require_profile(profile)
    try:
        job = start_skill_job(state, session, kind="evaluate", skill_id=skill_id, ai_id=row.ai_id)
    except LearningError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return JobRead.model_validate(job)


@router.get("/{skill_id}/evaluations", response_model=list[EvaluationRead])
def evaluations(
    skill_id: str, session: SessionDep, profile: ProfileDep, storage: StorageDep
) -> list[EvaluationRead]:
    row = _require_profile(profile)
    learning = SkillLearningService(session, row.ai_id, storage)
    return [EvaluationRead.model_validate(e) for e in learning.history(skill_id)]


@router.post("/{skill_id}/train-preview", response_model=TrainPreview)
def train_preview(
    skill_id: str,
    state: StateDep,
    session: SessionDep,
    profile: ProfileDep,
    request: Annotated[TrainRequest, Body()] = _NO_QUALIFIERS,
) -> TrainPreview:
    """What training would do. Starts nothing (spec §37)."""
    row = _require_profile(profile)
    return training_preview(
        state,
        session,
        skill_id=skill_id,
        ai_id=row.ai_id,
        duration_seconds=request.duration_seconds,
        target_level=request.target_level,
        specialization=request.specialization,
        all_areas=request.all_areas,
    )


@router.post("/{skill_id}/train", response_model=JobRead, status_code=202)
def train(
    skill_id: str,
    state: StateDep,
    session: SessionDep,
    profile: ProfileDep,
    request: Annotated[TrainRequest, Body()] = _NO_QUALIFIERS,
) -> JobRead:
    """Start a training job: search for better instructions, then let the benchmark judge."""
    row = _require_profile(profile)
    try:
        job = start_training_job(
            state,
            session,
            skill_id=skill_id,
            ai_id=row.ai_id,
            duration_seconds=request.duration_seconds,
            target_level=request.target_level,
            specialization=request.specialization,
            all_areas=request.all_areas,
            seed=request.seed,
        )
    except LearningError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return JobRead.model_validate(job)


@router.get("/{skill_id}/training", response_model=list[TrainingRunRead])
def training_runs(
    skill_id: str,
    session: SessionDep,
    profile: ProfileDep,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[TrainingRunRead]:
    row = _require_profile(profile)
    runs = TrainingService(session, row.ai_id).history(skill_id, limit=limit)
    return [TrainingRunRead.model_validate(r) for r in runs]


@router.post("/{skill_id}/training/revert", response_model=SkillStatus)
def revert_training(
    skill_id: str,
    skills: SkillsDep,
    session: SessionDep,
    profile: ProfileDep,
    storage: StorageDep,
) -> SkillStatus:
    """Put back the instructions the skill package shipped with.

    The level is left exactly as it was: it was measured, and reverting instructions does
    not re-measure anything. Re-run the benchmark to see what the original scores now.
    """
    row = _require_profile(profile)
    learning = SkillLearningService(session, row.ai_id, storage)
    skill_state = learning.state_for(skill_id)
    if skill_state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{skill_id} has not been learned.")
    if not TrainingService(session, row.ai_id).clear_instructions(skill_state):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{skill_id} is not using trained instructions."
        )
    session.commit()
    for item in skills.summary(row.ai_id).skills:
        if item.id == skill_id:
            return item
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown skill '{skill_id}'.")


def _require_profile(profile: ProfileDep) -> AIProfile:
    row = profile.get()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create your AI profile first.")
    return row
