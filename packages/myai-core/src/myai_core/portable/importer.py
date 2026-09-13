"""Bringing a `.myai` package onto this machine (spec §26, §77).

Two rules shape this file.

**Say what will not work here, before importing anything.** A package made on a desktop with
64 GB of memory can be imported onto a laptop with 8, and most of it will be fine: the
memories, the conversations, the skill levels are just rows. The model it used may not load.
The honest thing is to say so in advance and per capability, rather than importing everything
and letting the user discover it the next time they ask a question.

**An import is never half-applied.** The package is verified in full first (``open_package``
checks every digest), and the rows go in inside one transaction. A partial import of somebody's
only backup would be the worst outcome this feature could produce.

The restored copy gets a new sync identity
------------------------------------------

This is the gap ADR-0016 recorded, and importing is where it has to be closed. A sync identity
is a counter plus an id, and peers remember how far through that counter they have read. A
database restored from a backup has a *lower* counter than its peers remember, so every change
it makes until it catches up would be silently skipped — the exact class of failure sync is
built to avoid. So a restored installation starts a new identity. It looks like a new device
to its peers, which is what it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from myai_core.db import models
from myai_core.hardware.models import HardwareReport
from myai_core.portable.package import Manifest, OpenPackage


class Verdict(StrEnum):
    SUPPORTED = "supported"
    STORED_ONLY = "stored_only"
    """It will come across, but it cannot run on this machine."""
    MISSING = "missing"
    """It is referenced but not present, and has to be fetched."""


@dataclass(frozen=True, slots=True)
class CapabilityCheck:
    name: str
    verdict: Verdict
    detail: str


@dataclass(frozen=True, slots=True)
class ImportPreview:
    """What would happen, before anything does."""

    ai_name: str
    exported_at: datetime | None
    exported_by: str
    encrypted: bool
    counts: dict[str, int]
    capabilities: list[CapabilityCheck]
    warnings: list[str] = field(default_factory=list)

    @property
    def can_import(self) -> bool:
        """Nothing here blocks an import. A model that cannot run is stored, not refused."""
        return True


@dataclass(frozen=True, slots=True)
class ImportResult:
    rows_written: dict[str, int]
    new_install_id: str
    capabilities: list[CapabilityCheck]
    notes: list[str]


def _readable(byte_count: int) -> str:
    gb = byte_count / 1_000_000_000
    return f"{gb:.1f} GB" if gb >= 0.1 else f"{byte_count / 1_000_000:.0f} MB"


def check_compatibility(
    manifest: Manifest, hardware: HardwareReport | None
) -> list[CapabilityCheck]:
    """A verdict per capability, in the words a person can act on."""
    checks: list[CapabilityCheck] = [
        CapabilityCheck(
            "Identity, memories and conversations",
            Verdict.SUPPORTED,
            "These are records, not programs. They work on any machine.",
        ),
        CapabilityCheck(
            "Skill levels and training history",
            Verdict.SUPPORTED,
            "Levels come across as they were measured. Re-running a benchmark here may give "
            "a different number, because the model and the machine are part of the result.",
        ),
    ]

    available = hardware.memory.total_bytes if hardware else None
    for model in manifest.models:
        name = str(model.get("display_name") or model.get("id") or "a model")
        size = int(model.get("size_bytes") or 0)
        if available is not None and size and size * 1.3 > available:
            checks.append(
                CapabilityCheck(
                    name,
                    Verdict.STORED_ONLY,
                    f"This model wants about {_readable(int(size * 1.3))} of memory to load "
                    f"and this machine has {_readable(available)}. It will be listed, and it "
                    "will not run here.",
                )
            )
        else:
            checks.append(
                CapabilityCheck(
                    name,
                    Verdict.MISSING,
                    "The file itself is not in the package — its licence does not allow "
                    "passing it on. It is downloaded again here, with the licence shown.",
                )
            )
    return checks


def preview_import(package: OpenPackage, hardware: HardwareReport | None = None) -> ImportPreview:
    manifest = package.manifest
    exported_by = str((manifest.exported_by or {}).get("app_version") or "an unknown version")
    warnings: list[str] = []
    if not package.encrypted:
        warnings.append(
            "This package is not encrypted, so anyone who had the file could read it. That "
            "does not affect the import."
        )
    return ImportPreview(
        ai_name=str((manifest.ai or {}).get("name") or "an unnamed AI"),
        exported_at=manifest.exported_at,
        exported_by=exported_by,
        encrypted=package.encrypted,
        counts=dict(manifest.counts),
        capabilities=check_compatibility(manifest, hardware),
        warnings=warnings,
    )


# The order rows go in: a parent before anything that points at it.
_ORDER: tuple[tuple[str, type[Any], str], ...] = (
    ("identity/profile.json", models.AIProfile, "ai_id"),
    ("skills/state.json", models.SkillState, ""),
    ("memory/memories.json", models.Memory, "uid"),
    ("conversations/conversations.json", models.Conversation, "id"),
    ("conversations/messages.json", models.Message, "uid"),
    ("knowledge/documents.json", models.Document, "id"),
    ("settings/preferences.json", models.Preference, "key"),
)


def _clear(session: Session) -> None:
    """Empty the tables an import replaces, children first."""
    for _entry, model, _key in reversed(_ORDER):
        session.execute(delete(model))
    session.execute(delete(models.Chunk))


def import_package(
    session: Session,
    package: OpenPackage,
    *,
    hardware: HardwareReport | None = None,
) -> ImportResult:
    """Replace this installation's AI with the one in the package.

    Destructive by design: restoring a backup onto a machine that has diverged and *merging*
    the two are different operations with different right answers, and quietly doing the
    second when the user asked for the first would lose the thing they were restoring. The
    caller confirms; this does what it says.
    """
    written: dict[str, int] = {}
    _clear(session)

    for entry, model, _key in _ORDER:
        rows = package.section(entry)
        if not isinstance(rows, list):
            continue
        for row in rows:
            session.add(model(**_coerce(model, row)))
        written[entry] = len(rows)

    # A restored database is a new device as far as sync is concerned. See the module
    # docstring: keeping the old counter would make every change it goes on to make invisible
    # to peers that had already read past it.
    session.execute(delete(models.SyncPeer))
    session.execute(delete(models.SyncIdentity))
    session.execute(delete(models.SyncTombstone))
    session.execute(delete(models.SyncConflict))
    session.flush()

    from myai_core.sync.changes import identity

    new_identity = identity(session)
    session.commit()

    return ImportResult(
        rows_written=written,
        new_install_id=new_identity.install_id,
        capabilities=check_compatibility(package.manifest, hardware),
        notes=[
            "Model files were not in the package and have to be downloaded again; their "
            "licences are shown before anything is fetched.",
            "This installation was given a new sync identity, because a restored copy is a "
            "new device to the ones it syncs with. Pair it with your other devices again.",
            "Nothing about access came across: credentials belong to the machine that issued "
            "them, and are not in a package.",
        ],
    )


def _coerce(model: type[Any], row: dict[str, Any]) -> dict[str, Any]:
    """Turn JSON back into column values, dropping anything this version does not have."""
    from sqlalchemy import DateTime

    columns = model.__table__.columns
    values: dict[str, Any] = {}
    for name, value in row.items():
        column = columns.get(name)
        if column is None:
            continue  # written by a newer version than this one; ignored rather than fatal
        if isinstance(column.type, DateTime) and isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                continue
            values[name] = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        else:
            values[name] = value
    return values


def current_ai_name(session: Session) -> str | None:
    profile = session.scalar(select(models.AIProfile))
    return profile.name if profile else None
