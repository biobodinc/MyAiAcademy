from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import PreferencesDep, ProfileDep, SkillsDep, StateDep, StorageDep
from myai_core.commands.dispatcher import CommandContext, execute
from myai_core.commands.models import CommandResult
from myai_core.hardware import HardwareReport, detect_hardware

router = APIRouter(prefix="/commands", tags=["commands"])


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("", response_model=CommandResult)
async def run_command(
    body: CommandRequest,
    state: StateDep,
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
        )
        return state.status.labels(built)

    ctx = CommandContext(
        hardware=hardware,
        skills=lambda: skills.summary(ai_id),
        preferences=lambda: preferences,
        status=status,
    )
    return await run_in_threadpool(execute, body.text, ctx)
