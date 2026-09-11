from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from myai_core.chat.prompt import build_system_prompt
from myai_core.chat.service import ChatError, ChatService, SendMessage
from myai_core.knowledge.service import DocumentAddText, KnowledgeService
from myai_core.memory.service import MemoryCreate, MemoryService
from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions
from myai_core.profile.schemas import ProfileCreate
from myai_core.profile.service import ProfileService


@pytest.fixture
def profile(session: Session):  # type: ignore[no-untyped-def]
    return ProfileService(session).create(
        ProfileCreate(name="Nova", owner_name="Alex", personality="curious")
    )


def _echo(messages: list[ChatMessage], _o: GenerationOptions) -> Iterator[GenerationChunk]:
    yield GenerationChunk(text="Hello ")
    yield GenerationChunk(
        text="Alex!", done=True, finish_reason="stop", prompt_tokens=42, completion_tokens=2
    )


def _broken(_m: list[ChatMessage], _o: GenerationOptions) -> Iterator[GenerationChunk]:
    yield GenerationChunk(text="partial ")
    raise RuntimeError("GPU fell over")


def test_prompt_includes_persona_memory_and_knowledge(session: Session, profile) -> None:  # type: ignore[no-untyped-def]
    MemoryService(session, profile.ai_id).add(MemoryCreate(content="Alex likes horses"))
    KnowledgeService(session, profile.ai_id).add_text(
        DocumentAddText(title="Plan", text="The horse film shoots in October in Iceland.")
    )
    chat = ChatService(session, profile)
    conv = chat.create_conversation()
    messages, retrieved = chat.build_messages(conv.id, "When does the horse film shoot?")
    system = messages[0].content
    assert messages[0].role == "system" and messages[-1].role == "user"
    assert "You are Nova" in system and "Alex" in system and "curious" in system
    assert "Alex likes horses" in system
    assert retrieved and "[Plan §1]" in system and "Iceland" in system
    assert build_system_prompt(profile, [], []).startswith("You are Nova")


def test_send_streams_and_persists(session: Session, profile) -> None:  # type: ignore[no-untyped-def]
    chat = ChatService(session, profile)
    conv = chat.create_conversation()
    events = list(chat.send(conv.id, SendMessage(content="hi"), generate=_echo, model_id="m1"))
    kinds = [e.kind for e in events]
    assert kinds == ["meta", "delta", "delta", "done"]
    assert events[-1].payload["prompt_tokens"] == 42
    msgs = chat.messages(conv.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "Hello Alex!" and msgs[1].model_id == "m1"
    assert msgs[1].finish_reason == "stop" and msgs[1].duration_ms is not None
    convs = chat.list_conversations()
    assert convs[0].title == "hi" and convs[0].message_count == 2


def test_send_records_partial_reply_on_error(session: Session, profile) -> None:  # type: ignore[no-untyped-def]
    chat = ChatService(session, profile)
    conv = chat.create_conversation("Test")
    events = list(chat.send(conv.id, SendMessage(content="go"), generate=_broken, model_id="m1"))
    assert events[-1].kind == "error" and "GPU fell over" in str(events[-1].payload["message"])
    reply = chat.messages(conv.id)[-1]
    assert (
        reply.role == "assistant" and reply.content == "partial " and reply.finish_reason == "error"
    )


def test_history_window_and_scoping(session: Session, profile) -> None:  # type: ignore[no-untyped-def]
    chat = ChatService(session, profile)
    conv = chat.create_conversation()
    for i in range(3):
        list(chat.send(conv.id, SendMessage(content=f"turn {i}"), generate=_echo, model_id="m"))
    messages, _ = chat.build_messages(conv.id, "next")
    assert [m.role for m in messages] == ["system", *(["user", "assistant"] * 3), "user"]
    other = ChatService(session, ProfileServiceStub(ai_id="myai_other"))  # type: ignore[arg-type]
    with pytest.raises(ChatError):
        other.get_conversation(conv.id)
    chat.delete_conversation(conv.id)
    with pytest.raises(ChatError):
        chat.messages(conv.id)


class ProfileServiceStub:
    def __init__(self, ai_id: str) -> None:
        self.ai_id = ai_id
        self.name = "Other"
        self.owner_name = ""
        self.personality = ""
        self.communication_style = ""
