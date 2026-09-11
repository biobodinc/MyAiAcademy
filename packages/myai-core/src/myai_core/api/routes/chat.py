from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import iterate_in_threadpool

from myai_core.api.deps import PreferencesDep, ProfileDep, SessionDep, StateDep, StorageDep
from myai_core.api.model_loading import prepare_active_model
from myai_core.chat.service import (
    ChatError,
    ChatService,
    ConversationRead,
    MessageRead,
    SendMessage,
)
from myai_core.commands.dispatcher import CommandContext, execute
from myai_core.commands.parser import is_command
from myai_core.hardware import HardwareReport, detect_hardware
from myai_core.memory.service import MemoryService
from myai_core.models.provider import ProviderError
from myai_core.models.service import ModelService
from myai_core.skills.service import SkillsService

router = APIRouter(prefix="/chat", tags=["chat"])


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


def _chat(session: SessionDep, profile: ProfileDep) -> ChatService:
    row = profile.get()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create your AI profile first.")
    return ChatService(session, row)


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(session: SessionDep, profile: ProfileDep) -> list[ConversationRead]:
    return _chat(session, profile).list_conversations()


@router.post("/conversations", response_model=ConversationRead, status_code=201)
def create_conversation(
    body: ConversationCreate, session: SessionDep, profile: ProfileDep
) -> ConversationRead:
    row = _chat(session, profile).create_conversation(body.title)
    return ConversationRead(
        id=row.id, title=row.title, created_at=row.created_at, updated_at=row.updated_at
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: str, session: SessionDep, profile: ProfileDep
) -> list[MessageRead]:
    try:
        return [
            MessageRead.model_validate(m) for m in _chat(session, profile).messages(conversation_id)
        ]
    except ChatError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, session: SessionDep, profile: ProfileDep) -> None:
    try:
        _chat(session, profile).delete_conversation(conversation_id)
    except ChatError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: SendMessage,
    state: StateDep,
    session: SessionDep,
    profile: ProfileDep,
    storage: StorageDep,
    prefs: PreferencesDep,
) -> StreamingResponse:
    """Stream the assistant's reply as server-sent events.

    Events: ``meta`` (what was retrieved, which model), ``delta`` (text), ``done`` or
    ``error``. A slash command inside a conversation is executed by the command
    interpreter instead of the model and returned as a single ``command`` event.
    """
    chat = _chat(session, profile)
    try:
        chat.get_conversation(conversation_id)
    except ChatError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    if is_command(body.content):
        result = _run_command(body.content, state, session, profile, prefs, storage)
        return StreamingResponse(iter([_sse("command", result)]), media_type="text/event-stream")

    prepared = prepare_active_model(state, ModelService(session, storage), prefs.get())

    def events() -> Iterator[str]:
        try:
            state.runtime.ensure_loaded(prepared.path, prepared.config)
        except ProviderError as exc:
            yield _sse("error", {"message": str(exc)})
            return
        for event in chat.send(
            conversation_id, body, generate=state.runtime.generate, model_id=prepared.model_id
        ):
            yield _sse(event.kind, event.payload)

    return StreamingResponse(
        iterate_in_threadpool(events()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(kind: str, payload: object) -> str:
    return f"event: {kind}\ndata: {json.dumps(payload, default=str)}\n\n"


def _run_command(
    text: str,
    state: StateDep,
    session: SessionDep,
    profile: ProfileDep,
    prefs: PreferencesDep,
    storage: StorageDep,
) -> dict[str, object]:
    row = profile.get()
    preferences = prefs.get()

    def hardware() -> HardwareReport:
        if state.hardware_cache is None:
            state.hardware_cache = detect_hardware()
        return state.hardware_cache

    def status_labels() -> dict[str, object]:
        built = state.status.build(
            profile_exists=row is not None,
            storage_configured=storage.get_config() is not None,
            onboarding_completed=preferences.onboarding_completed,
            privacy_mode=preferences.privacy_mode.value,
            ai_state=state.ai_state(session),
        )
        return state.status.labels(built)

    def memories() -> list[str]:
        if row is None:
            return []
        return [m.content for m in MemoryService(session, row.ai_id).list_all()]

    ctx = CommandContext(
        hardware=hardware,
        skills=lambda: SkillsService(session).summary(row.ai_id if row else None),
        preferences=lambda: preferences,
        status=status_labels,
        memories=memories,
    )
    return execute(text, ctx).model_dump()
