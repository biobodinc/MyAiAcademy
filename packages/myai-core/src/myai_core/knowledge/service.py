from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from ulid import ULID

from myai_core.db.models import Chunk, Document
from myai_core.knowledge.chunking import chunk_text
from myai_core.knowledge.extract import UnsupportedDocumentError, extract_text, media_type_for
from myai_core.schemas import ApiModel


class DocumentRead(ApiModel):
    id: str
    title: str
    source_path: str | None
    media_type: str
    size_bytes: int
    sha256: str
    chunk_count: int
    status: str
    error: str | None
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentAddPath(ApiModel):
    path: str = Field(min_length=1)
    title: str | None = Field(default=None, max_length=255)


class DocumentAddText(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=4_000_000)


class RetrievedChunk(ApiModel):
    chunk_id: int
    document_id: str
    document_title: str
    ordinal: int
    content: str
    score: float = Field(description="BM25 rank; lower is better (SQLite convention).")


class KnowledgeError(ValueError):
    pass


class KnowledgeService:
    def __init__(self, session: Session, ai_id: str) -> None:
        self._session = session
        self._ai_id = ai_id

    def list_all(self) -> list[Document]:
        stmt = (
            select(Document).where(Document.ai_id == self._ai_id).order_by(Document.added_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def get(self, document_id: str) -> Document:
        row = self._session.get(Document, document_id)
        if row is None or row.ai_id != self._ai_id:
            raise KnowledgeError("No such document.")
        return row

    def add_path(self, data: DocumentAddPath) -> Document:
        path = Path(data.path).expanduser()
        if not path.is_file():
            raise KnowledgeError(f"File not found: {path}")
        try:
            media_type = media_type_for(path)
            content = extract_text(path)
        except UnsupportedDocumentError as exc:
            raise KnowledgeError(str(exc)) from exc
        return self._ingest(
            title=data.title or path.name,
            source_path=str(path),
            media_type=media_type,
            size_bytes=path.stat().st_size,
            content=content,
        )

    def add_text(self, data: DocumentAddText) -> Document:
        return self._ingest(
            title=data.title,
            source_path=None,
            media_type="text/plain",
            size_bytes=len(data.text.encode("utf-8")),
            content=data.text,
        )

    def delete(self, document_id: str) -> None:
        row = self.get(document_id)
        self._session.delete(row)  # chunks cascade; FTS triggers clean the index
        self._session.flush()

    def search(self, query: str, limit: int = 5) -> list[RetrievedChunk]:
        cleaned = _fts_query(query)
        if not cleaned:
            return []
        stmt = text(
            "SELECT c.id, c.document_id, d.title, c.ordinal, c.content, bm25(chunks_fts) AS score "
            "FROM chunks_fts f JOIN chunks c ON c.id = f.rowid "
            "JOIN documents d ON d.id = c.document_id "
            "WHERE chunks_fts MATCH :q AND d.ai_id = :ai AND d.status = 'ready' "
            "ORDER BY score LIMIT :n"
        )
        rows = self._session.execute(stmt, {"q": cleaned, "ai": self._ai_id, "n": limit}).all()
        return [
            RetrievedChunk(
                chunk_id=r[0],
                document_id=r[1],
                document_title=r[2],
                ordinal=r[3],
                content=r[4],
                score=float(r[5]),
            )
            for r in rows
        ]

    def stats(self) -> tuple[int, int]:
        docs = self._session.scalar(
            select(func.count()).select_from(Document).where(Document.ai_id == self._ai_id)
        )
        chunks = self._session.scalar(
            select(func.count())
            .select_from(Chunk)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.ai_id == self._ai_id)
        )
        return int(docs or 0), int(chunks or 0)

    def _ingest(
        self, *, title: str, source_path: str | None, media_type: str, size_bytes: int, content: str
    ) -> Document:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = self._session.scalars(
            select(Document).where(Document.ai_id == self._ai_id, Document.sha256 == digest)
        ).first()
        if existing is not None:
            raise KnowledgeError(f"Already in knowledge as '{existing.title}'.")
        chunks = chunk_text(content)
        if not chunks:
            raise KnowledgeError("The document contains no text.")
        doc = Document(
            id=f"doc_{ULID()}",
            ai_id=self._ai_id,
            title=title.strip()[:255],
            source_path=source_path,
            media_type=media_type,
            size_bytes=size_bytes,
            sha256=digest,
            chunk_count=len(chunks),
            status="ready",
        )
        self._session.add(doc)
        self._session.flush()
        self._session.add_all(
            Chunk(document_id=doc.id, ordinal=i, content=c) for i, c in enumerate(chunks)
        )
        self._session.flush()
        return doc


def _fts_query(raw: str) -> str:
    words = [w.strip('"').strip() for w in raw.split()]
    words = [w for w in words if len(w) > 1]
    if not words:
        return ""
    # OR semantics with BM25 ranking: a question usually shares only some words with the
    # relevant passage; requiring all of them would miss it.
    return " OR ".join(f'"{w}"' for w in words[:16])
