"""Privacy Center (spec §62): a truthful summary computed from local state."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from myai_core.api.deps import PreferencesDep, SessionDep, StateDep, StorageDep
from myai_core.privacy.portability import (
    ERASE_CONFIRMATION,
    ErasePlan,
    EraseResult,
    ExportResult,
    erase_data,
    export_data,
    plan_erase,
)
from myai_core.schemas import ApiModel
from myai_core.security.auth import CallerDep
from myai_core.security.devices import DeviceService
from myai_core.storage import StorageCategory

router = APIRouter(prefix="/privacy", tags=["privacy"])


class PrivacySummary(ApiModel):
    private_data_location: str = "Local only"
    cloud_ai_data_uploads: int = 0
    community_sharing: bool
    cloud_backup: bool = False
    connected_devices: int = 0
    connected_apps: int = 0
    account_linked: bool = False
    notes: list[str]


class ExportRequest(ApiModel):
    destination: str | None = Field(
        default=None, description="Where to write it. Defaults to Exports in your storage root."
    )
    include_model_files: bool = Field(
        default=False,
        description="Copy the files in your storage root as well. Large; off by default.",
    )


class EraseRequest(ApiModel):
    confirm: str = Field(description=f"Must be exactly '{ERASE_CONFIRMATION}'.")
    remove_files: bool = Field(
        default=False, description="Also delete the files under your storage root."
    )


@router.get("", response_model=PrivacySummary)
def read_privacy(prefs: PreferencesDep, session: SessionDep) -> PrivacySummary:
    preferences = prefs.get()
    return PrivacySummary(
        community_sharing=preferences.contributor_mode,
        connected_devices=DeviceService(session).active_count(),
        notes=[
            "This build has no cloud account, sync or upload code paths at all.",
            "Outbound network activity: an internet reachability check (a TCP connect with "
            "no payload) and model downloads from Hugging Face that you start yourself "
            "after reading the licence. Chat, memory and knowledge never leave this machine.",
            "Clients you have paired can use this AI from this machine. Nothing you pair "
            "reaches another machine: the service only listens on 127.0.0.1.",
            "Cloud sync and community contribution do not exist in this build and will each "
            "require explicit opt-in when they do.",
        ],
    )


@router.get("/erase-preview", response_model=ErasePlan)
def erase_preview(session: SessionDep, storage: StorageDep, caller: CallerDep) -> ErasePlan:
    """What erasing would delete. Deletes nothing."""
    return plan_erase(session, storage)


@router.post("/export", response_model=ExportResult)
def export_everything(
    request: ExportRequest,
    state: StateDep,
    session: SessionDep,
    storage: StorageDep,
    caller: CallerDep,
) -> ExportResult:
    """Write an archive of everything this installation holds about you.

    Credentials are deliberately left out: they are access grants, not your data.
    """
    _require_owner(caller)
    destination = _export_destination(request.destination, storage)
    try:
        return export_data(
            session,
            state.engine,
            state.paths,
            storage,
            destination=destination,
            include_model_files=request.include_model_files,
        )
    except OSError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Could not write the export: {exc}"
        ) from exc


@router.post("/erase", response_model=EraseResult)
def erase_everything(
    request: EraseRequest, session: SessionDep, storage: StorageDep, caller: CallerDep
) -> EraseResult:
    """Delete everything. Requires the confirmation phrase, and cannot be undone."""
    _require_owner(caller)
    if request.confirm != ERASE_CONFIRMATION:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Type '{ERASE_CONFIRMATION}' to confirm. Nothing was deleted.",
        )
    return erase_data(session, storage, remove_files=request.remove_files)


def _export_destination(requested: str | None, storage: StorageDep) -> Path:
    if requested:
        return Path(requested).expanduser()
    config = storage.get_config()
    if config is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Choose a storage location first, or say where the export should be written.",
        )
    return storage.category_path(StorageCategory.EXPORTS)


def _require_owner(caller: CallerDep) -> None:
    if not caller.is_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only this installation can export or erase your data. Do it in the app on this "
            "machine.",
        )
