from __future__ import annotations

from fastapi import APIRouter
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import (
    PreferencesDep,
    ProfileDep,
    SessionDep,
    SkillsDep,
    StateDep,
    StorageDep,
)
from myai_core.commands.dispatcher import CommandContext, execute
from myai_core.commands.models import CommandResult
from myai_core.hardware import HardwareReport, detect_hardware
from myai_core.memory.service import MemoryService
from myai_core.schemas import ApiModel

router = APIRouter(prefix="/commands", tags=["commands"])


class CommandRequest(ApiModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("", response_model=CommandResult)
async def run_command(
    body: CommandRequest,
    state: StateDep,
    session: SessionDep,
    profile: ProfileDep,
    prefs: PreferencesDep,
    skills: SkillsDep,
    storage: StorageDep,
) -> CommandResult:
    row = profile.get()
    ai_id = row.ai_id if row else None
    preferences = prefs.get()

    def hardware() -> HardwareReport:
        if state.hardware_cache is None:
            state.hardware_cache = detect_hardware()
        return state.hardware_cache

    def status() -> dict[str, object]:
        built = state.status.build(
            profile_exists=row is not None,
            storage_configured=storage.get_config() is not None,
            onboarding_completed=preferences.onboarding_completed,
            privacy_mode=preferences.privacy_mode.value,
            ai_state=state.ai_state(session),
        )
        return state.status.labels(built)

    def memories() -> list[str]:
        if ai_id is None:
            return []
        return [m.content for m in MemoryService(session, ai_id).list_all()]

    ctx = CommandContext(
        hardware=hardware,
        skills=lambda: skills.summary(ai_id),
        preferences=lambda: preferences,
        status=status,
        memories=memories,
    )
    return await run_in_threadpool(execute, body.text, ctx)
