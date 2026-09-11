from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from myai_core.api.deps import AuditDep, PreferencesDep, SessionDep, StateDep, StorageDep
from myai_core.audit.service import AuditCategory
from myai_core.db.models import ModelDownload
from myai_core.models.catalog import CatalogModel
from myai_core.models.runtime import load_config_for
from myai_core.models.service import (
    DownloadStatus,
    ModelEntry,
    ModelError,
    ModelService,
    ModelsOverview,
    recommended_for,
)

router = APIRouter(prefix="/models", tags=["models"])


class ModelIdBody(BaseModel):
    model_id: str


def _service(session: SessionDep, storage: StorageDep) -> ModelService:
    return ModelService(session, storage)


@router.get("", response_model=ModelsOverview)
def overview(state: StateDep, session: SessionDep, storage: StorageDep) -> ModelsOverview:
    svc = _service(session, storage)
    runtime = state.runtime.status()
    return ModelsOverview(
        runtime_available=runtime.available,
        runtime_detail=runtime.detail,
        active_model_id=svc.active_model_id(),
        loaded_model_id=runtime.loaded_model_id,
        backend=runtime.backend,
        models=svc.entries(state.hardware_cache),
    )


@router.get("/recommended", response_model=CatalogModel)
def recommended(state: StateDep) -> CatalogModel:
    return recommended_for(state.hardware_cache)


@router.post("/{model_id}/accept-license", response_model=ModelEntry)
def accept_license(
    model_id: str, state: StateDep, session: SessionDep, storage: StorageDep, audit: AuditDep
) -> ModelEntry:
    svc = _service(session, storage)
    try:
        model = svc.accept_license(model_id)
    except ModelError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    audit.record(
        AuditCategory.SYSTEM,
        "model_license_accepted",
        f"Accepted the {model.license.name} for {model.name}",
        {"model_id": model.id, "license_id": model.license.id},
    )
    return next(e for e in svc.entries(state.hardware_cache) if e.catalog.id == model_id)


@router.post("/{model_id}/download", response_model=DownloadStatus, status_code=202)
def start_download(
    model_id: str, state: StateDep, session: SessionDep, storage: StorageDep, audit: AuditDep
) -> DownloadStatus:
    svc = _service(session, storage)
    try:
        model, dest, job = svc.prepare_download(model_id)
    except ModelError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    audit.record(
        AuditCategory.SYSTEM,
        "model_download_started",
        f"Downloading {model.name} from {model.hf_repo}",
        {"model_id": model.id, "url": model.download_url},
    )
    session.commit()  # the worker thread reads the job row through its own session
    state.downloads.start(job.id, model, dest)
    return DownloadStatus.model_validate(job)


@router.get("/downloads/{job_id}", response_model=DownloadStatus)
def download_status(job_id: str, session: SessionDep) -> DownloadStatus:
    job = session.get(ModelDownload, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown download.")
    return DownloadStatus.model_validate(job)


@router.post("/downloads/{job_id}/cancel", response_model=DownloadStatus)
def cancel_download(job_id: str, state: StateDep, session: SessionDep) -> DownloadStatus:
    job = session.get(ModelDownload, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown download.")
    if not state.downloads.cancel(job_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "That download is not running.")
    return DownloadStatus.model_validate(job)


@router.post("/active", response_model=ModelsOverview)
def set_active(
    body: ModelIdBody,
    state: StateDep,
    session: SessionDep,
    storage: StorageDep,
    audit: AuditDep,
) -> ModelsOverview:
    svc = _service(session, storage)
    try:
        svc.set_active(body.model_id)
    except ModelError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if state.runtime.status().loaded_model_id not in (None, body.model_id):
        state.runtime.unload()
    audit.record(
        AuditCategory.SYSTEM, "model_activated", "Active model changed", {"model_id": body.model_id}
    )
    return overview(state, session, storage)


@router.delete("/{model_id}", response_model=ModelsOverview)
def remove_model(
    model_id: str, state: StateDep, session: SessionDep, storage: StorageDep, audit: AuditDep
) -> ModelsOverview:
    svc = _service(session, storage)
    if state.runtime.status().loaded_model_id == model_id:
        state.runtime.unload()
    try:
        svc.remove(model_id)
    except ModelError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    audit.record(AuditCategory.SYSTEM, "model_removed", "Model removed", {"model_id": model_id})
    return overview(state, session, storage)


@router.post("/load", response_model=ModelsOverview)
def load_active(
    state: StateDep, session: SessionDep, storage: StorageDep, prefs: PreferencesDep
) -> ModelsOverview:
    """Load the active model now (chat loads it lazily; this lets the UI warm it up)."""
    from pathlib import Path

    from myai_core.models.provider import ProviderError

    svc = _service(session, storage)
    active = svc.active_model_id()
    if active is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No active model.")
    installed = svc.get_installed(active)
    assert installed is not None
    config = load_config_for(active, state.hardware_cache, prefs.get().compute_preset)
    try:
        state.runtime.ensure_loaded(Path(installed.file_path), config)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return overview(state, session, storage)
