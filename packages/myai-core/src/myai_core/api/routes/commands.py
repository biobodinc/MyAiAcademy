from __future__ import annotations

from fastapi import APIRouter
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from myai_core.api.command_context import build_command_context
from myai_core.api.deps import PreferencesDep, ProfileDep, SessionDep, StateDep, StorageDep
from myai_core.commands.dispatcher import execute
from myai_core.commands.models import CommandResult
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
    storage: StorageDep,
) -> CommandResult:
    ctx = build_command_context(
        state, session, profile=profile.get(), preferences=prefs.get(), storage=storage
    )
    return await run_in_threadpool(execute, body.text, ctx)
