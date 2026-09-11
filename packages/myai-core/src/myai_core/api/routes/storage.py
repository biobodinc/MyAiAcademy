from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import AuditDep, SessionDep, StorageDep
from myai_core.audit.service import AuditCategory
from myai_core.hardware.models import StorageVolume
from myai_core.storage.cleanup import (
    CleanupPlan,
    CleanupRequest,
    CleanupResult,
    ProtectedDeletionError,
    delete_candidates,
    find_candidates,
)
from myai_core.storage.manager import StorageError
from myai_core.storage.models import (
    CategoryOverrideRequest,
    StorageLocationCheck,
    StorageOverview,
    StorageSetupRequest,
)

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("", response_model=StorageOverview)
async def read_overview(storage: StorageDep) -> StorageOverview:
    return await run_in_threadpool(storage.overview)


@router.get("/check", response_model=StorageLocationCheck)
def check_location(storage: StorageDep, path: str = Query(min_length=1)) -> StorageLocationCheck:
    return storage.check_location(path)


@router.get("/external-candidates", response_model=list[StorageVolume])
def external_candidates(storage: StorageDep) -> list[StorageVolume]:
    return storage.detect_external_candidates()


@router.put("/root", response_model=StorageOverview)
def configure_root(
    body: StorageSetupRequest, storage: StorageDep, audit: AuditDep
) -> StorageOverview:
    try:
        config = storage.configure_root(body.root_path)
    except StorageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    audit.record(
        AuditCategory.STORAGE,
        "root_configured",
        "MyAI storage location set",
        {"root_path": config.root_path},
    )
    return storage.overview()


@router.put("/overrides", response_model=StorageOverview)
def set_override(
    body: CategoryOverrideRequest, storage: StorageDep, audit: AuditDep
) -> StorageOverview:
    try:
        storage.set_category_override(body.category, body.path)
    except StorageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    audit.record(
        AuditCategory.STORAGE,
        "override_changed",
        f"{body.category.value.title()} location {'set' if body.path else 'reset'}",
        {"category": body.category.value, "path": body.path},
    )
    return storage.overview()


def _plan(storage: StorageDep, session: SessionDep) -> CleanupPlan:
    from myai_core.models.service import ModelService

    if storage.get_config() is None:
        return CleanupPlan(candidates=[], reclaimable_bytes=0, protected_bytes=0)
    tracked = [m.file_path for m in ModelService(session, storage).installed()]
    return find_candidates(storage.category_paths(), tracked)


@router.get("/cleanup", response_model=CleanupPlan)
async def cleanup_plan(storage: StorageDep, session: SessionDep) -> CleanupPlan:
    """What could be deleted safely, with protected items flagged (spec §63)."""
    return await run_in_threadpool(_plan, storage, session)


@router.post("/cleanup", response_model=CleanupResult)
async def cleanup(
    body: CleanupRequest, storage: StorageDep, session: SessionDep, audit: AuditDep
) -> CleanupResult:
    plan = await run_in_threadpool(_plan, storage, session)
    try:
        result = await run_in_threadpool(delete_candidates, plan, body)
    except ProtectedDeletionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if result.deleted:
        audit.record(
            AuditCategory.STORAGE,
            "cleanup",
            f"Deleted {len(result.deleted)} file(s) during storage cleanup",
            {
                "paths": result.deleted,
                "freed_bytes": result.freed_bytes,
                "protected_acknowledged": body.acknowledge_protected,
            },
        )
    return result
