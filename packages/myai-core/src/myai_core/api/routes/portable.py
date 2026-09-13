"""Carrying your AI to another machine, and keeping it as a backup (spec §23-§27, §77).

Importing replaces what is here. That is the right behaviour for restoring a backup and the
wrong behaviour to do by accident, so it is split into two steps: a preview that says what is
in the package and what will not run on this machine, and an import that requires the typed
confirmation the preview hands back. The same shape the Privacy Center uses for erasing,
for the same reason.

Every one of these is owner-only. A paired phone may use the AI; it may not write a copy of
everything to a file, or replace it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from myai_core.api.deps import SessionDep, StateDep
from myai_core.audit.service import AuditCategory, AuditService
from myai_core.hardware.models import HardwareReport
from myai_core.portable import (
    SUFFIX,
    ImportPreview,
    PackageError,
    Verdict,
    WrongPasswordError,
    import_package,
    needs_password,
    open_package,
    preview_import,
    write_package,
)
from myai_core.schemas import ApiModel
from myai_core.security.auth import CallerDep
from myai_core.security.devices import Caller

router = APIRouter(prefix="/portable", tags=["portable"])

IMPORT_CONFIRMATION = "REPLACE MY AI"


def _require_owner(caller: Caller) -> None:
    if not caller.is_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only this installation's owner can write or restore a portable package.",
        )


class PackageRequest(ApiModel):
    destination: str = Field(default="", description="Where to write it. Blank uses the cache.")
    password: str = Field(
        default="",
        description="Locks the package. Without one, anyone who finds the file can read it.",
    )


class ManifestRead(ApiModel):
    format_version: int
    ai_name: str
    exported_at: datetime
    exported_by: str
    encrypted: bool
    counts: dict[str, int]
    models: list[dict[str, Any]]
    skills: list[dict[str, Any]]


class PackageWritten(ApiModel):
    path: str
    size_bytes: int
    encrypted: bool
    manifest: ManifestRead
    notes: list[str]


class CapabilityRead(ApiModel):
    name: str
    verdict: Verdict
    detail: str


class PreviewRequest(ApiModel):
    path: str
    password: str = ""


class ImportPreviewRead(ApiModel):
    """What a package holds, and what of it will work here."""

    ai_name: str
    exported_at: datetime | None
    exported_by: str
    encrypted: bool
    counts: dict[str, int]
    capabilities: list[CapabilityRead]
    replaces_ai: str | None = Field(
        default=None, description="The AI on this machine that importing would replace."
    )
    confirmation_phrase: str = IMPORT_CONFIRMATION
    warnings: list[str]


class RestoreRequest(ApiModel):
    path: str
    password: str = ""
    confirm: str = Field(description=f"Must be exactly {IMPORT_CONFIRMATION!r}.")


class ImportDone(ApiModel):
    rows_written: dict[str, int]
    new_install_id: str
    capabilities: list[CapabilityRead]
    notes: list[str]


def _manifest_read(manifest: Any, *, encrypted: bool) -> ManifestRead:
    return ManifestRead(
        format_version=manifest.format_version,
        ai_name=str((manifest.ai or {}).get("name") or "an unnamed AI"),
        exported_at=manifest.exported_at,
        exported_by=str((manifest.exported_by or {}).get("app_version") or "unknown"),
        encrypted=encrypted,
        counts=manifest.counts,
        models=manifest.models,
        skills=manifest.skills,
    )


def _hardware(state: StateDep) -> HardwareReport | None:
    return state.hardware_cache


@router.post("", response_model=PackageWritten, status_code=201)
def write(
    body: PackageRequest, session: SessionDep, state: StateDep, caller: CallerDep
) -> PackageWritten:
    """Write a `.myai` package of this AI."""
    _require_owner(caller)
    default_name = f"myai-{datetime.now(tz=UTC):%Y%m%d-%H%M%S}"
    destination = (
        Path(body.destination).expanduser()
        if body.destination
        else state.paths.export_dir / default_name
    )
    try:
        result = write_package(
            session,
            destination=destination,
            password=body.password or None,
            device_id=caller.device_id,
        )
    except OSError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Could not write there: {exc.strerror or exc}"
        ) from exc

    AuditService(session).record(
        AuditCategory.PRIVACY,
        "portable_package_written",
        f"Wrote a portable package{' (locked)' if result.encrypted else ''}.",
        details={"path": str(result.path), "encrypted": result.encrypted},
        device_id=caller.device_id,
    )
    session.commit()
    return PackageWritten(
        path=str(result.path),
        size_bytes=result.size_bytes,
        encrypted=result.encrypted,
        manifest=_manifest_read(result.manifest, encrypted=result.encrypted),
        notes=result.notes,
    )


@router.post("/preview", response_model=ImportPreviewRead)
def preview(
    body: PreviewRequest, session: SessionDep, state: StateDep, caller: CallerDep
) -> ImportPreviewRead:
    """Read a package and say what importing it would do. Nothing is changed."""
    _require_owner(caller)
    path = Path(body.path).expanduser()
    package = _open(path, body.password)
    try:
        from myai_core.portable.importer import current_ai_name

        found: ImportPreview = preview_import(package, _hardware(state))
        return ImportPreviewRead(
            ai_name=found.ai_name,
            exported_at=found.exported_at,
            exported_by=found.exported_by,
            encrypted=found.encrypted,
            counts=found.counts,
            capabilities=[
                CapabilityRead(name=c.name, verdict=c.verdict, detail=c.detail)
                for c in found.capabilities
            ],
            replaces_ai=current_ai_name(session),
            warnings=found.warnings,
        )
    finally:
        package.close()


@router.post("/import", response_model=ImportDone)
def restore(
    body: RestoreRequest, session: SessionDep, state: StateDep, caller: CallerDep
) -> ImportDone:
    """Replace this installation's AI with the one in a package."""
    _require_owner(caller)
    if body.confirm != IMPORT_CONFIRMATION:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Importing replaces the AI on this machine. Type {IMPORT_CONFIRMATION!r} to "
            "confirm you mean to do that.",
        )
    package = _open(Path(body.path).expanduser(), body.password)
    try:
        result = import_package(session, package, hardware=_hardware(state))
    finally:
        package.close()

    AuditService(session).record(
        AuditCategory.PRIVACY,
        "portable_package_imported",
        "Replaced this installation's AI from a portable package.",
        details={"path": body.path, "rows": sum(result.rows_written.values())},
        device_id=caller.device_id,
    )
    session.commit()
    return ImportDone(
        rows_written=result.rows_written,
        new_install_id=result.new_install_id,
        capabilities=[
            CapabilityRead(name=c.name, verdict=c.verdict, detail=c.detail)
            for c in result.capabilities
        ],
        notes=result.notes,
    )


@router.get("/inspect")
def inspect(
    path: Annotated[str, Field(description="A .myai file to look at.")],
    caller: CallerDep,
) -> dict[str, Any]:
    """Whether a file is a package at all, and whether it needs a password. No password used."""
    _require_owner(caller)
    target = Path(path).expanduser()
    try:
        return {
            "is_package": True,
            "needs_password": needs_password(target),
            "suffix": SUFFIX,
        }
    except PackageError as exc:
        return {"is_package": False, "needs_password": False, "detail": str(exc)}


def _open(path: Path, password: str) -> Any:
    try:
        return open_package(path, password=password or None)
    except WrongPasswordError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except PackageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
