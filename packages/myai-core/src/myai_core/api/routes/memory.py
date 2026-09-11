from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from myai_core.api.deps import AuditDep, ProfileDep, SessionDep
from myai_core.audit.service import AuditCategory
from myai_core.memory.service import (
    MemoryCreate,
    MemoryRead,
    MemoryService,
    MemoryStoreError,
    MemoryUpdate,
)

router = APIRouter(prefix="/memory", tags=["memory"])


def _svc(session: SessionDep, profile: ProfileDep) -> MemoryService:
    row = profile.get()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create your AI profile first.")
    return MemoryService(session, row.ai_id)


@router.get("", response_model=list[MemoryRead])
def list_memories(
    session: SessionDep, profile: ProfileDep, q: str | None = Query(default=None, max_length=200)
) -> list[MemoryRead]:
    svc = _svc(session, profile)
    rows = svc.search(q) if q else svc.list_all()
    return [MemoryRead.model_validate(r) for r in rows]


@router.post("", response_model=MemoryRead, status_code=201)
def add_memory(
    body: MemoryCreate, session: SessionDep, profile: ProfileDep, audit: AuditDep
) -> MemoryRead:
    row = _svc(session, profile).add(body)
    audit.record(AuditCategory.PROFILE, "memory_added", "A memory was added", {"id": row.id})
    return MemoryRead.model_validate(row)


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: int, body: MemoryUpdate, session: SessionDep, profile: ProfileDep
) -> MemoryRead:
    try:
        return MemoryRead.model_validate(_svc(session, profile).update(memory_id, body))
    except MemoryStoreError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.delete("/{memory_id}", status_code=204)
def delete_memory(
    memory_id: int, session: SessionDep, profile: ProfileDep, audit: AuditDep
) -> None:
    try:
        _svc(session, profile).delete(memory_id)
    except MemoryStoreError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    audit.record(AuditCategory.PROFILE, "memory_deleted", "A memory was deleted", {"id": memory_id})


@router.delete("", status_code=200)
def clear_memories(session: SessionDep, profile: ProfileDep, audit: AuditDep) -> dict[str, int]:
    count = _svc(session, profile).clear()
    audit.record(
        AuditCategory.PROFILE, "memory_cleared", "All memories were cleared", {"count": count}
    )
    return {"deleted": count}
