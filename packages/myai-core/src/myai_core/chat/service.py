from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ulid import ULID

from myai_core.chat.prompt import build_system_prompt
from myai_core.db.models import AIProfile, Conversation, Message
from myai_core.knowledge.service import KnowledgeService, RetrievedChunk
from myai_core.memory.service import MemoryService
from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions, Role
from myai_core.schemas import ApiModel

HISTORY_CHAR_BUDGET = 12_000
RETRIEVAL_TOP_K = 4


class ConversationRead(ApiModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageRead(ApiModel):
    id: int
    role: str
    content: str
    created_at: datetime
    model_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int | None
    retrieved_chunk_ids: list[int]
    finish_reason: str | None

    model_config = ConfigDict(from_attributes=True)


class SendMessage(ApiModel):
    content: str = Field(min_length=1, max_length=20_000)
    options: GenerationOptions | None = Field(
        default=None, description="Omit to use the generation defaults from preferences."
    )


class ConversationUpdate(ApiModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Title cannot be blank.")
        return cleaned


class ChatError(ValueError):
    pass


@dataclass(slots=True)
class StreamEvent:
    kind: str  # 'meta' | 'delta' | 'done' | 'error'
    payload: dict[str, object]


Generator = Callable[[list[ChatMessage], GenerationOptions], Iterator[GenerationChunk]]


class ChatService:
    def __init__(self, session: Session, profile: AIProfile) -> None:
        self._session = session
        self._profile = profile

    # --- conversations ------------------------------------------------------------------

    def list_conversations(self) -> list[ConversationRead]:
        counted = self._session.execute(
            select(Message.conversation_id, func.count()).group_by(Message.conversation_id)
        ).all()
        counts: dict[str, int] = {str(row[0]): int(row[1]) for row in counted}
        rows = self._session.scalars(
            select(Conversation)
            .where(Conversation.ai_id == self._profile.ai_id)
            .order_by(Conversation.updated_at.desc())
        ).all()
        return [
            ConversationRead(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=int(counts.get(c.id, 0)),
            )
            for c in rows
        ]

    def create_conversation(self, title: str | None = None) -> Conversation:
        row = Conversation(
            id=f"conv_{ULID()}",
            ai_id=self._profile.ai_id,
            title=(title or "New conversation")[:200],
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_conversation(self, conversation_id: str) -> Conversation:
        row = self._session.get(Conversation, conversation_id)
        if row is None or row.ai_id != self._profile.ai_id:
            raise ChatError("No such conversation.")
        return row

    def rename_conversation(self, conversation_id: str, title: str) -> Conversation:
        row = self.get_conversation(conversation_id)
        row.title = title
        row.version += 1
        self._session.flush()
        return row

    def delete_conversation(self, conversation_id: str) -> None:
        self._session.delete(self.get_conversation(conversation_id))
        self._session.flush()

    def messages(self, conversation_id: str) -> list[Message]:
        self.get_conversation(conversation_id)
        return list(
            self._session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id)
            ).all()
        )

    # --- prompt assembly ----------------------------------------------------------------

    def build_messages(
        self, conversation_id: str, user_text: str
    ) -> tuple[list[ChatMessage], list[RetrievedChunk]]:
        memories = MemoryService(self._session, self._profile.ai_id).for_prompt()
        knowledge = KnowledgeService(self._session, self._profile.ai_id).search(
            user_text, limit=RETRIEVAL_TOP_K
        )
        system = build_system_prompt(self._profile, memories, knowledge)
        history = self.messages(conversation_id)
        window: list[ChatMessage] = []
        budget = HISTORY_CHAR_BUDGET
        for msg in reversed(history):
            if msg.role not in ("user", "assistant"):
                continue
            if budget - len(msg.content) < 0:
                break
            budget -= len(msg.content)
            role: Role = "user" if msg.role == "user" else "assistant"
            window.append(ChatMessage(role=role, content=msg.content))
        window.reverse()
        return (
            [
                ChatMessage(role="system", content=system),
                *window,
                ChatMessage(role="user", content=user_text),
            ],
            knowledge,
        )

    # --- sending ------------------------------------------------------------------------

    def send(
        self,
        conversation_id: str,
        data: SendMessage,
        *,
        generate: Generator,
        model_id: str,
        default_options: GenerationOptions | None = None,
    ) -> Iterator[StreamEvent]:
        """Persist the user turn, stream the reply, persist the assistant turn.

        Yields events suitable for SSE. The assistant message is written even when the
        stream fails part-way, with ``finish_reason='error'``, so nothing is silently lost.
        """
        conversation = self.get_conversation(conversation_id)
        user_msg = Message(conversation_id=conversation.id, role="user", content=data.content)
        self._session.add(user_msg)
        if conversation.title == "New conversation":
            conversation.title = _title_from(data.content)
        conversation.version += 1
        self._session.flush()
        self._session.commit()

        messages, knowledge = self.build_messages(conversation.id, data.content)
        chunk_ids = [k.chunk_id for k in knowledge]
        yield StreamEvent(
            "meta",
            {
                "user_message_id": user_msg.id,
                "model_id": model_id,
                "retrieved": [k.model_dump() for k in knowledge],
                "conversation_title": conversation.title,
            },
        )

        started = time.monotonic()
        buffer: list[str] = []
        finish: str | None = None
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        error: str | None = None
        try:
            for chunk in generate(messages, data.options or default_options or GenerationOptions()):
                if chunk.text:
                    buffer.append(chunk.text)
                    yield StreamEvent("delta", {"text": chunk.text})
                if chunk.prompt_tokens is not None:
                    prompt_tokens = chunk.prompt_tokens
                if chunk.completion_tokens is not None:
                    completion_tokens = chunk.completion_tokens
                if chunk.done:
                    finish = chunk.finish_reason or "stop"
        except Exception as exc:
            error = str(exc)
            finish = "error"

        duration_ms = int((time.monotonic() - started) * 1000)
        reply = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="".join(buffer),
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            retrieved_chunk_ids=chunk_ids,
            finish_reason=finish or "stop",
        )
        self._session.add(reply)
        conversation.version += 1
        self._session.flush()
        self._session.commit()
        if error:
            yield StreamEvent("error", {"message": error, "assistant_message_id": reply.id})
        else:
            yield StreamEvent(
                "done",
                {
                    "assistant_message_id": reply.id,
                    "finish_reason": reply.finish_reason,
                    "duration_ms": duration_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                },
            )


def _title_from(text_: str) -> str:
    first = " ".join(text_.strip().split())
    return (first[:57] + "…") if len(first) > 60 else first or "New conversation"


def model_file_path(path: str) -> Path:
    return Path(path)
