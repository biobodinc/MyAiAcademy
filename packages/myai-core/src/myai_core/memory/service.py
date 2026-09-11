from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import ConfigDict, Field
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session
from ulid import ULID

from myai_core.db.models import Memory
from myai_core.schemas import ApiModel

MAX_MEMORIES_IN_PROMPT = 40
MAX_MEMORY_CHARS = 1000


class MemoryCategory(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    INSTRUCTION = "instruction"
    OTHER = "other"


class MemoryCreate(ApiModel):
    content: str = Field(min_length=1, max_length=MAX_MEMORY_CHARS)
    category: MemoryCategory = MemoryCategory.FACT


class MemoryUpdate(ApiModel):
    content: str | None = Field(default=None, min_length=1, max_length=MAX_MEMORY_CHARS)
    category: MemoryCategory | None = None
    expected_version: int | None = Field(default=None, ge=1)


class MemoryRead(ApiModel):
    id: int
    uid: str
    content: str
    category: MemoryCategory
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)


class MemoryStoreError(ValueError):
    pass


class MemoryService:
    def __init__(self, session: Session, ai_id: str) -> None:
        self._session = session
        self._ai_id = ai_id

    def list_all(self, limit: int = 500) -> list[Memory]:
        stmt = (
            select(Memory)
            .where(Memory.ai_id == self._ai_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get(self, memory_id: int) -> Memory:
        row = self._session.get(Memory, memory_id)
        if row is None or row.ai_id != self._ai_id:
            raise MemoryStoreError("No such memory.")
        return row

    def add(self, data: MemoryCreate) -> Memory:
        row = Memory(
            uid=f"mem_{ULID()}",
            ai_id=self._ai_id,
            content=" ".join(data.content.split()),
            category=data.category.value,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def update(self, memory_id: int, data: MemoryUpdate) -> Memory:
        row = self.get(memory_id)
        if data.expected_version is not None and data.expected_version != row.version:
            raise MemoryStoreError("This memory changed elsewhere. Reload and try again.")
        if data.content is not None:
            row.content = " ".join(data.content.split())
        if data.category is not None:
            row.category = data.category.value
        row.version += 1
        self._session.flush()
        return row

    def delete(self, memory_id: int) -> None:
        row = self.get(memory_id)
        self._session.delete(row)
        self._session.flush()

    def clear(self) -> int:
        count = self._session.scalar(
            select(func.count()).select_from(Memory).where(Memory.ai_id == self._ai_id)
        )
        self._session.execute(delete(Memory).where(Memory.ai_id == self._ai_id))
        self._session.flush()
        return int(count or 0)

    def search(self, query: str, limit: int = 20) -> list[Memory]:
        """Full-text search (FTS5, porter stemming). Falls back to LIKE on odd input."""
        cleaned = _fts_query(query)
        if not cleaned:
            return []
        stmt = text(
            "SELECT m.id FROM memories_fts f JOIN memories m ON m.id = f.rowid "
            "WHERE memories_fts MATCH :q AND m.ai_id = :ai ORDER BY bm25(memories_fts) LIMIT :n"
        )
        ids = [
            r[0] for r in self._session.execute(stmt, {"q": cleaned, "ai": self._ai_id, "n": limit})
        ]
        if not ids:
            return []
        rows = {r.id: r for r in self._session.scalars(select(Memory).where(Memory.id.in_(ids)))}
        return [rows[i] for i in ids if i in rows]

    def for_prompt(self) -> list[Memory]:
        """Most recent memories, capped, for inclusion in the system prompt."""
        return self.list_all(limit=MAX_MEMORIES_IN_PROMPT)


def _fts_query(raw: str) -> str:
    """Build a safe FTS5 query: each word quoted, ANDed, prefix-matched."""
    words = [w.strip('"').strip() for w in raw.split()]
    words = [w for w in words if w]
    return " ".join(f'"{w}"*' for w in words[:12])
