from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import AuditDep, ProfileDep, SessionDep
from myai_core.audit.service import AuditCategory
from myai_core.knowledge.extract import supported_suffixes
from myai_core.knowledge.service import (
    DocumentAddPath,
    DocumentAddText,
    DocumentRead,
    KnowledgeError,
    KnowledgeService,
    RetrievedChunk,
)
from myai_core.schemas import ApiModel

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeOverview(ApiModel):
    documents: list[DocumentRead]
    document_count: int
    chunk_count: int
    supported_suffixes: list[str]
    retrieval_method: str = "lexical (BM25 over SQLite FTS5); semantic embeddings planned"


def _svc(session: SessionDep, profile: ProfileDep) -> KnowledgeService:
    row = profile.get()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create your AI profile first.")
    return KnowledgeService(session, row.ai_id)


@router.get("", response_model=KnowledgeOverview)
def overview(session: SessionDep, profile: ProfileDep) -> KnowledgeOverview:
    svc = _svc(session, profile)
    docs, chunks = svc.stats()
    return KnowledgeOverview(
        documents=[DocumentRead.model_validate(d) for d in svc.list_all()],
        document_count=docs,
        chunk_count=chunks,
        supported_suffixes=supported_suffixes(),
    )


@router.post("/files", response_model=DocumentRead, status_code=201)
async def add_file(
    body: DocumentAddPath, session: SessionDep, profile: ProfileDep, audit: AuditDep
) -> DocumentRead:
    svc = _svc(session, profile)
    try:
        doc = await run_in_threadpool(svc.add_path, body)
    except KnowledgeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    audit.record(
        AuditCategory.PROFILE,
        "knowledge_added",
        f"Document added to knowledge: {doc.title}",
        {"document_id": doc.id, "chunks": doc.chunk_count},
    )
    return DocumentRead.model_validate(doc)


@router.post("/text", response_model=DocumentRead, status_code=201)
def add_text(
    body: DocumentAddText, session: SessionDep, profile: ProfileDep, audit: AuditDep
) -> DocumentRead:
    try:
        doc = _svc(session, profile).add_text(body)
    except KnowledgeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    audit.record(
        AuditCategory.PROFILE,
        "knowledge_added",
        f"Text added to knowledge: {doc.title}",
        {"document_id": doc.id, "chunks": doc.chunk_count},
    )
    return DocumentRead.model_validate(doc)


@router.get("/search", response_model=list[RetrievedChunk])
def search(
    session: SessionDep,
    profile: ProfileDep,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[RetrievedChunk]:
    return _svc(session, profile).search(q, limit=limit)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, session: SessionDep, profile: ProfileDep, audit: AuditDep
) -> None:
    try:
        _svc(session, profile).delete(document_id)
    except KnowledgeError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    audit.record(
        AuditCategory.PROFILE, "knowledge_removed", "Document removed", {"document_id": document_id}
    )
