"""Build the :class:`CommandContext` the console and chat share, with Phase 3 job hooks."""

from __future__ import annotations

from sqlalchemy.orm import Session

from myai_core.api.state import AppState
from myai_core.commands.dispatcher import CommandContext
from myai_core.commands.models import TrainTarget
from myai_core.db.models import AIProfile
from myai_core.hardware import HardwareReport, detect_hardware
from myai_core.hardware.benchmark_store import BenchmarkStore
from myai_core.memory.service import MemoryService
from myai_core.models.service import ModelService
from myai_core.preferences.schemas import Preferences
from myai_core.skills.jobs import JobSummary, summarise
from myai_core.skills.learning import EvaluationRead, LearnPreview, SkillLearningService
from myai_core.skills.pipeline import start_skill_job, start_training_job, training_preview
from myai_core.skills.service import SkillsService, count_trainable_skills
from myai_core.skills.trainer import TrainPreview
from myai_core.storage import StorageManager


def build_command_context(
    state: AppState,
    session: Session,
    *,
    profile: AIProfile | None,
    preferences: Preferences,
    storage: StorageManager,
) -> CommandContext:
    ai_id = profile.ai_id if profile else None

    def hardware() -> HardwareReport:
        if state.hardware_cache is None:
            state.hardware_cache = detect_hardware()
        return state.hardware_cache

    def status_labels() -> dict[str, object]:
        current = state.jobs.current(session)
        built = state.status.build(
            profile_exists=profile is not None,
            storage_configured=storage.get_config() is not None,
            onboarding_completed=preferences.onboarding_completed,
            privacy_mode=preferences.privacy_mode.value,
            ai_state=state.ai_state(session),
            job=summarise(current) if current else None,
            trainable_skills=count_trainable_skills(session, ai_id),
        )
        return state.status.labels(built)

    def memories() -> list[str]:
        if ai_id is None:
            return []
        return [m.content for m in MemoryService(session, ai_id).list_all()]

    def learning() -> SkillLearningService:
        assert ai_id is not None
        return SkillLearningService(session, ai_id, storage)

    def learn_preview(skill_id: str) -> LearnPreview:
        runtime_ok, _ = state.runtime.provider.availability()
        return learning().preview(
            skill_id,
            hardware=state.hardware_cache,
            measured=BenchmarkStore(session).latest(),
            active_model_id=ModelService(session, storage).active_model_id(),
            runtime_available=runtime_ok,
        )

    def start_learn(skill_id: str) -> JobSummary:
        assert ai_id is not None
        return summarise(
            start_skill_job(state, session, kind="learn", skill_id=skill_id, ai_id=ai_id)
        )

    def train_preview(skill_id: str, target: TrainTarget | None) -> TrainPreview:
        assert ai_id is not None
        return training_preview(
            state,
            session,
            skill_id=skill_id,
            ai_id=ai_id,
            duration_seconds=target.duration_seconds if target else None,
            target_level=target.target_level if target else None,
            specialization=_focus(target),
            all_areas=bool(target and target.all_areas),
        )

    def start_train(skill_id: str, target: TrainTarget | None) -> JobSummary:
        assert ai_id is not None
        return summarise(
            start_training_job(
                state,
                session,
                skill_id=skill_id,
                ai_id=ai_id,
                duration_seconds=target.duration_seconds if target else None,
                target_level=target.target_level if target else None,
                specialization=_focus(target),
                all_areas=bool(target and target.all_areas),
            )
        )

    def current_job() -> JobSummary | None:
        job = state.jobs.current(session)
        return summarise(job) if job else None

    def job_action(job_id: str, action: str) -> bool:
        return {
            "pause": state.jobs.pause,
            "resume": state.jobs.resume,
            "cancel": state.jobs.cancel,
        }[action](job_id)

    def history() -> list[EvaluationRead]:
        if ai_id is None:
            return []
        return [EvaluationRead.model_validate(r) for r in learning().history(limit=20)]

    has_profile = ai_id is not None
    return CommandContext(
        hardware=hardware,
        skills=lambda: SkillsService(session).summary(ai_id),
        preferences=lambda: preferences,
        status=status_labels,
        memories=memories,
        learn_preview=learn_preview if has_profile else None,
        start_learn=start_learn if has_profile else None,
        current_job=current_job,
        job_action=job_action,
        history=history,
        train_preview=train_preview if has_profile else None,
        start_train=start_train if has_profile else None,
    )


def _focus(target: TrainTarget | None) -> str | None:
    """Drop the confirmation words the parser collects as a trailing specialization."""
    if target is None or not target.specialization:
        return None
    words = [w for w in target.specialization.split() if w not in _CONFIRMATIONS]
    return " ".join(words) or None


_CONFIRMATIONS = {"start", "confirm", "yes", "go"}
