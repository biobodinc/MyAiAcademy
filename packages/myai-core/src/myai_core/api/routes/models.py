from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import AuditDep, PreferencesDep, SessionDep, StateDep, StorageDep
from myai_core.api.model_loading import load_prepared, prepare_active_model
from myai_core.audit.service import AuditCategory
from myai_core.db.models import ModelDownload
from myai_core.models.catalog import CatalogModel, get_catalog_model
from myai_core.models.download import DownloadError
from myai_core.models.service import (
    DownloadStatus,
    ImportRequest,
    ModelEntry,
    ModelError,
    ModelService,
    ModelsOverview,
    ProviderInfo,
    list_providers,
    recommended_for,
)
from myai_core.schemas import ApiModel

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


@router.get("/providers", response_model=list[ProviderInfo])
def providers(state: StateDep) -> list[ProviderInfo]:
    """The model-provider tree (spec §46) with each entry's real status."""
    runtime = state.runtime.status()
    return list_providers(runtime.available, runtime.detail)


@router.post("/import", response_model=ModelsOverview, status_code=201)
async def import_model(
    body: ImportRequest,
    state: StateDep,
    session: SessionDep,
    storage: StorageDep,
    audit: AuditDep,
) -> ModelsOverview:
    """Register a GGUF file you already have. Hashing and copying run off the event loop."""
    svc = _service(session, storage)
    try:
        row = await run_in_threadpool(svc.import_file, body)
    except ModelError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    audit.record(
        AuditCategory.SYSTEM,
        "model_imported",
        f"Imported model file {row.display_name}",
        {"model_id": row.id, "path": row.file_path, "sha256": row.sha256},
    )
    return overview(state, session, storage)


class ModelSourceInfo(ApiModel):
    """What the file host declares for a catalog model, without downloading it.

    Exists because a download that fails its integrity check is otherwise impossible to
    diagnose from the outside: this shows whether the publisher actually publishes a
    content hash for the file, and what the host's own ETag is.
    """

    model_id: str
    url: str
    final_url: str
    status_code: int
    size_bytes: int | None
    publisher_sha256: str | None = Field(
        default=None, description="A hash the publisher promises. A mismatch fails a download."
    )
    etag_sha256: str | None = Field(
        default=None, description="The host's ETag when it looks like a SHA-256. Advisory only."
    )
    pinned_sha256: str | None = Field(default=None, description="The hash pinned in our catalog.")
    will_verify: bool
    note: str


@router.get("/{model_id}/source", response_model=ModelSourceInfo)
async def source_info(model_id: str, state: StateDep) -> ModelSourceInfo:
    """Ask the host what it declares for this file. Downloads nothing."""
    model = get_catalog_model(model_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown model '{model_id}'.")
    try:
        info = await run_in_threadpool(state.downloads.downloader.inspect, model.download_url)
    except DownloadError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    will_verify = bool(model.sha256 or info.publisher_sha256)
    return ModelSourceInfo(
        model_id=model.id,
        url=model.download_url,
        final_url=info.final_url,
        status_code=info.status_code,
        size_bytes=info.size_bytes,
        publisher_sha256=info.publisher_sha256,
        etag_sha256=info.etag_sha256,
        pinned_sha256=model.sha256,
        will_verify=will_verify,
        note=(
            "The download will be verified against a published content hash."
            if will_verify
            else (
                "No content hash is published for this file, so the download can only be "
                "checked for completeness. The host's ETag is not a content hash."
            )
        ),
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
    return next(e for e in svc.entries(state.hardware_cache) if e.id == model_id)


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


@router.post("/unload", response_model=ModelsOverview)
def unload_model(
    state: StateDep, session: SessionDep, storage: StorageDep, audit: AuditDep
) -> ModelsOverview:
    """Release the loaded model's memory. The next message loads it again."""
    loaded = state.runtime.status().loaded_model_id
    if loaded is not None:
        state.runtime.unload()
        audit.record(AuditCategory.SYSTEM, "model_unloaded", "Model unloaded", {"model_id": loaded})
    return overview(state, session, storage)


@router.post("/load", response_model=ModelsOverview)
def load_active(
    state: StateDep, session: SessionDep, storage: StorageDep, prefs: PreferencesDep
) -> ModelsOverview:
    """Load the active model now (chat loads it lazily; this lets the UI warm it up)."""
    prepared = prepare_active_model(state, _service(session, storage), prefs.get())
    load_prepared(state, prepared)
    return overview(state, session, storage)
