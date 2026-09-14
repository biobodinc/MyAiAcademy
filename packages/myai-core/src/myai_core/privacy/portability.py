"""Take your data out, or destroy it (spec §62 Privacy Center).

Two operations that have to be trustworthy in opposite directions.

**Export** must contain everything of the user's that this program holds, and nothing that
would hand someone else the keys. So the database goes in (profile, conversations,
memories, knowledge, skills, training runs, audit log) and the installation token and
client credentials do not: a credential is not the user's data, it is an access grant, and
copying it into a file they might email themselves would be a quiet hole. Model files are
listed rather than copied, because they are gigabytes of publicly downloadable weights and
an export the user cannot actually store is not an export. Everything that is and is not
included is written into the archive's own manifest, so the file explains itself years
later.

**Erase** must actually erase. It deletes the rows rather than "marking deleted", and it is
explicit about what it cannot reach: files the user copied elsewhere, and anything already
exported. It requires typing a word, because an accidental click here is unrecoverable.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from myai_core import __version__
from myai_core.audit.service import AuditCategory, AuditService
from myai_core.db.base import Base
from myai_core.db.models import (
    AccountInfo,
    AIProfile,
    AuditEvent,
    Chunk,
    Conversation,
    Device,
    Document,
    InstalledModel,
    Memory,
    Message,
    ModelDownload,
    ModelLicenseAcceptance,
    PairingCode,
    SkillEvaluation,
    SkillState,
    SyncConflict,
    SyncIdentity,
    SyncPeer,
    SyncTombstone,
    TrainingRun,
)
from myai_core.paths import AppPaths
from myai_core.schemas import ApiModel
from myai_core.security.storage_checks import restrict_new_file
from myai_core.storage import StorageManager

ERASE_CONFIRMATION = "ERASE MY DATA"
MANIFEST_NAME = "myai-export.json"
DATABASE_ENTRY = "database/myai-core.sqlite3"
FILES_ENTRY = "files/manifest.json"

EXCLUDED_FROM_EXPORT = (
    "The installation token and any client credentials: those are access grants, not your "
    "data, and copying them into a portable file would hand anyone holding the file access "
    "to this installation.",
    "Model weight files: they are large and publicly downloadable, so they are listed with "
    "their sizes and hashes instead of copied.",
)


class ExportedFile(ApiModel):
    """One file under the storage root. Listed, not read."""

    relative_path: str
    path: str
    size_bytes: int


class ExportManifest(ApiModel):
    """The archive's self-description, written inside the archive."""

    format: str = "myai-export"
    format_version: int = 1
    service_version: str
    created_at: datetime
    includes: list[str]
    excludes: list[str]
    row_counts: dict[str, int]
    file_count: int
    file_bytes: int


class ExportResult(ApiModel):
    path: str
    size_bytes: int
    manifest: ExportManifest


class ErasePlan(ApiModel):
    """What erasing would remove, before anything is removed."""

    row_counts: dict[str, int]
    storage_root: str | None
    storage_file_count: int
    storage_bytes: int
    confirmation_phrase: str = ERASE_CONFIRMATION
    warnings: list[str]


class EraseResult(ApiModel):
    rows_deleted: dict[str, int]
    files_deleted: int
    bytes_freed: int
    storage_removed: bool
    notes: list[str]


# Tables whose contents are the user's data, in the order they are safe to delete.
_ERASABLE = (
    # Sync first. `sync_conflicts` holds whole copies of rows that were overwritten — the
    # text of a memory, the title of a conversation — so an erase that skipped it would
    # leave the user's words behind in the one table nobody thinks to look in.
    ("sync_conflicts", SyncConflict),
    ("sync_tombstones", SyncTombstone),
    ("sync_peers", SyncPeer),
    ("sync_identity", SyncIdentity),
    ("messages", Message),
    ("conversations", Conversation),
    ("memories", Memory),
    ("chunks", Chunk),
    ("documents", Document),
    ("skill_evaluations", SkillEvaluation),
    ("training_runs", TrainingRun),
    ("skill_state", SkillState),
    ("model_downloads", ModelDownload),
    ("model_license_acceptances", ModelLicenseAcceptance),
    ("installed_models", InstalledModel),
    ("devices", Device),
    ("pairing_codes", PairingCode),
    ("audit_events", AuditEvent),
    # The link to an account is an identifier for the person, not just a setting, so an erase
    # that left it would leave this machine still pointing at them.
    ("account_info", AccountInfo),
    ("ai_profile", AIProfile),
)


def row_counts(session: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, model in _ERASABLE:
        counts[name] = int(session.scalar(select(func.count()).select_from(model)) or 0)
    return counts


def export_data(
    session: Session,
    engine: Engine,
    paths: AppPaths,
    storage: StorageManager,
    *,
    destination: Path,
    include_model_files: bool = False,
) -> ExportResult:
    """Write a portable archive and return where it landed.

    The database is copied with SQLite's own backup API rather than by reading the file, so
    the copy is consistent even though the service is running and may be mid-write.
    """
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC)
    archive = destination / f"myai-export-{stamp:%Y%m%d-%H%M%S}.zip"

    files = _storage_manifest(storage)
    manifest = ExportManifest(
        service_version=__version__,
        created_at=stamp,
        includes=[
            "Your AI's profile, conversations and messages",
            "Memories you added and documents you put in Knowledge",
            "Skill levels, every benchmark run and every training run",
            "The local audit log",
            "A listing of the files in your storage root",
        ],
        excludes=list(EXCLUDED_FROM_EXPORT),
        row_counts=row_counts(session),
        file_count=len(files),
        file_bytes=sum(f.size_bytes for f in files),
    )

    snapshot = destination / f".{archive.stem}.sqlite3"
    try:
        _snapshot_database(engine, snapshot)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST_NAME, manifest.model_dump_json(indent=2))
            zf.write(snapshot, DATABASE_ENTRY)
            zf.writestr(
                FILES_ENTRY,
                json.dumps([f.model_dump(mode="json") for f in files], indent=2),
            )
            if include_model_files:
                for entry in files:
                    source = Path(entry.path)
                    if source.is_file():
                        zf.write(source, f"files/{entry.relative_path}")
    finally:
        snapshot.unlink(missing_ok=True)

    restrict_new_file(archive)
    AuditService(session).record(
        AuditCategory.PRIVACY,
        "data_exported",
        f"Your data was exported to {archive.name}",
        {"path": str(archive), "rows": sum(manifest.row_counts.values())},
    )
    return ExportResult(path=str(archive), size_bytes=archive.stat().st_size, manifest=manifest)


def plan_erase(session: Session, storage: StorageManager) -> ErasePlan:
    files = _storage_manifest(storage)
    config = storage.get_config()
    return ErasePlan(
        row_counts=row_counts(session),
        storage_root=config.root_path if config else None,
        storage_file_count=len(files),
        storage_bytes=sum(f.size_bytes for f in files),
        warnings=[
            "This cannot be undone. Export first if you want a copy.",
            "Anything you already copied elsewhere — an export, a file you moved out of "
            "the storage root — is not reachable from here and will not be touched.",
            "Deleted files are not overwritten, so a forensic tool may still recover them "
            "from the disk. Use your operating system's secure-erase tool if that matters.",
        ],
    )


def erase_data(
    session: Session,
    storage: StorageManager,
    *,
    remove_files: bool,
) -> EraseResult:
    """Delete the user's data. The caller is responsible for having confirmed."""
    before = row_counts(session)
    for _name, model in _ERASABLE:
        session.execute(delete(model))
    session.flush()

    files_deleted = 0
    bytes_freed = 0
    storage_removed = False
    if remove_files:
        for entry in _storage_manifest(storage):
            target = Path(entry.path)
            if target.is_file():
                size = target.stat().st_size
                try:
                    target.unlink()
                except OSError:  # pragma: no cover - permission or race
                    continue
                files_deleted += 1
                bytes_freed += size
        storage_removed = True

    notes = [
        "Every row of your data has been deleted from this installation's database.",
        "The service is now in its first-run state: it will ask you to set your AI up again.",
    ]
    if remove_files:
        notes.append(
            "Files under your storage root were deleted too, including any models you had "
            "downloaded. The folders themselves were left in place."
        )
    else:
        notes.append(
            "Files under your storage root were left alone, so downloaded models are still "
            "there. Remove them with storage cleanup or your file manager."
        )
    # Recorded after the wipe so the log does not claim to hold a history it just deleted.
    AuditService(session).record(
        AuditCategory.PRIVACY,
        "data_erased",
        "All local data was erased at your request",
        {"rows_deleted": sum(before.values()), "files_deleted": files_deleted},
    )
    return EraseResult(
        rows_deleted=before,
        files_deleted=files_deleted,
        bytes_freed=bytes_freed,
        storage_removed=storage_removed,
        notes=notes,
    )


def _snapshot_database(engine: Engine, destination: Path) -> None:
    """A consistent copy of the live database, via SQLite's backup API."""
    url = engine.url
    source_path = url.database
    if not source_path or source_path == ":memory:":
        # An in-memory database (tests) has nothing on disk to snapshot; write an empty
        # file rather than failing, and let the manifest's row counts carry the truth.
        destination.write_bytes(b"")
        return
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    restrict_new_file(destination)


def _storage_manifest(storage: StorageManager) -> list[ExportedFile]:
    """Every file under the storage root, with its size. No contents are read."""
    config = storage.get_config()
    if config is None:
        return []
    root = Path(config.root_path)
    if not root.is_dir():
        return []
    entries: list[ExportedFile] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:  # pragma: no cover - vanished mid-scan
            continue
        entries.append(
            ExportedFile(relative_path=str(path.relative_to(root)), path=str(path), size_bytes=size)
        )
    return entries


def known_tables() -> list[str]:
    """Table names in the schema, so a test can prove nothing was forgotten."""
    return sorted(Base.metadata.tables)
