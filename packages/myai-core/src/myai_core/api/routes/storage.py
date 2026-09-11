from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import AuditDep, StorageDep
from myai_core.audit.service import AuditCategory
from myai_core.hardware.models import StorageVolume
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
