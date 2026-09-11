"""Build the :class:`CommandContext` the console and chat share, with Phase 3 job hooks."""

from __future__ import annotations

from sqlalchemy.orm import Session

from myai_core.api.state import AppState
from myai_core.commands.dispatcher import CommandContext
from myai_core.db.models import AIProfile
from myai_core.hardware import HardwareReport, detect_hardware
from myai_core.hardware.benchmark_store import BenchmarkStore
from myai_core.memory.service import MemoryService
from myai_core.models.service import ModelService
from myai_core.preferences.schemas import Preferences
from myai_core.skills.jobs import JobSummary, summarise
from myai_core.skills.learning import EvaluationRead, LearnPreview, SkillLearningService
from myai_core.skills.pipeline import start_skill_job
from myai_core.skills.service import SkillsService
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
    )
