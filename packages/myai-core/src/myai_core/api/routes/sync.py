"""Keeping a user's own devices in step (spec §16, §18, §72).

The two halves of a sync are deliberately separate endpoints. A device *pulls* what this
installation has done since a number it names, and *pushes* what it has done itself. Either
can be run alone, both are safe to repeat, and an interrupted sync resumes from the cursor
rather than starting again.

Both are open to a paired device, because syncing between a user's own machines is the whole
point. Neither grants anything an owner keeps to themselves: the payloads carry the rows the
registry lists and nothing else, so a peer cannot use sync to read a credential or an audit
log it would be refused directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, select

from myai_core.api.deps import SessionDep, StateDep
from myai_core.audit.service import AuditCategory, AuditService
from myai_core.db import models
from myai_core.schemas import ApiModel
from myai_core.security.auth import CallerDep
from myai_core.sync import (
    BATCH_LIMIT,
    NOT_SYNCED,
    SYNCED,
    Change,
    apply_changes,
    changes_since,
    identity,
    peer_for,
)

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncedKind(ApiModel):
    name: str
    travels: list[str] = Field(description="The columns that leave this machine.")


class PeerRead(ApiModel):
    peer_install_id: str
    name: str
    device_id: str | None
    received_through: int
    sent_through: int
    last_synced_at: datetime | None


class SyncOverview(ApiModel):
    """What syncing is, and what this installation has done so far."""

    install_id: str
    next_seq: int = Field(description="This installation's logical clock.")
    peers: list[PeerRead]
    unresolved_conflicts: int
    syncs: list[SyncedKind]
    stays_local: dict[str, str] = Field(
        description="Every table that never leaves, and why not.",
    )
    detail: str


class ChangeBatch(ApiModel):
    """A page of changes, and the cursor to ask with next time."""

    install_id: str
    changes: list[dict[str, Any]]
    cursor: int = Field(description="Pass this back as `since` to continue where this ended.")
    more: bool = Field(description="True when the batch was truncated and another is waiting.")


class PushRequest(ApiModel):
    install_id: str = Field(min_length=1, max_length=64, description="Who these changes are from.")
    name: str = Field(default="", max_length=120)
    changes: list[dict[str, Any]] = Field(default_factory=list)


class PushResult(ApiModel):
    applied: int
    skipped: int
    conflicts: int
    received_through: int
    detail: str


class ConflictRead(ApiModel):
    id: int
    entity: str
    uid: str
    kept: str
    losing_payload: dict[str, Any]
    losing_version: int
    losing_origin: str | None
    losing_updated_at: datetime | None
    detected_at: datetime
    resolved_at: datetime | None


@router.get("", response_model=SyncOverview)
def read_overview(session: SessionDep, caller: CallerDep) -> SyncOverview:
    me = identity(session)
    peers = session.scalars(select(models.SyncPeer).order_by(models.SyncPeer.created_at)).all()
    unresolved = (
        session.scalar(
            select(func.count())
            .select_from(models.SyncConflict)
            .where(models.SyncConflict.resolved_at.is_(None))
        )
        or 0
    )
    return SyncOverview(
        install_id=me.install_id,
        next_seq=me.next_seq,
        peers=[PeerRead.model_validate(p) for p in peers],
        unresolved_conflicts=int(unresolved),
        syncs=[SyncedKind(name=e.name, travels=list(e.fields)) for e in SYNCED],
        stays_local=dict(NOT_SYNCED),
        detail=(
            "Syncing runs between your own devices, over the same pinned connection pairing "
            "uses. There is no server in the middle: nothing is uploaded anywhere, and a "
            "device that has not been paired cannot ask for any of this."
        ),
    )


@router.get("/changes", response_model=ChangeBatch)
def read_changes(
    session: SessionDep,
    caller: CallerDep,
    since: Annotated[int, Query(ge=0, description="The last number you already have.")] = 0,
    limit: Annotated[int, Query(ge=1, le=BATCH_LIMIT)] = BATCH_LIMIT,
) -> ChangeBatch:
    """Everything this installation has changed after `since`, oldest first."""
    me = identity(session)
    batch = changes_since(session, since, limit=limit)
    cursor = max((c.seq for c in batch), default=since)
    return ChangeBatch(
        install_id=me.install_id,
        changes=[c.to_json() for c in batch],
        cursor=cursor,
        more=len(batch) == limit,
    )


@router.post("/changes", response_model=PushResult)
def write_changes(
    body: PushRequest, session: SessionDep, caller: CallerDep, state: StateDep
) -> PushResult:
    """Accept a batch from another of the user's installations."""
    me = identity(session)
    if body.install_id == me.install_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That batch says it came from this installation. Two devices cannot share one "
            "identity; restore one of them from its own backup, or pair it again.",
        )

    try:
        parsed = [Change.from_json(raw) for raw in body.changes]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unreadable change: {exc}"
        ) from exc

    peer = peer_for(
        session,
        body.install_id,
        name=body.name,
        device_id="" if caller.is_owner else (caller.device_id or ""),
    )
    report = apply_changes(session, parsed, peer=body.install_id)
    peer.received_through = max(peer.received_through, report.highest_seq)
    peer.last_synced_at = datetime.now(tz=UTC)

    if report.conflicts:
        AuditService(session).record(
            AuditCategory.SECURITY,
            "sync_conflict",
            f"{report.conflicts} change(s) from another device replaced one made here.",
            details={"peer": body.install_id, "conflicts": report.conflicts},
            device_id=caller.device_id,
        )
    session.commit()

    return PushResult(
        applied=report.applied,
        skipped=report.skipped,
        conflicts=report.conflicts,
        received_through=peer.received_through,
        detail=(
            f"Applied {report.applied}."
            + (
                f" {report.conflicts} clashed with a change made here; the version that was "
                "replaced is kept under Conflicts so you can put it back."
                if report.conflicts
                else ""
            )
        ),
    )


@router.get("/conflicts", response_model=list[ConflictRead])
def list_conflicts(
    session: SessionDep,
    caller: CallerDep,
    include_resolved: Annotated[bool, Query()] = False,
) -> list[ConflictRead]:
    """What was overwritten when two devices changed the same thing. Nothing is thrown away."""
    query = select(models.SyncConflict).order_by(models.SyncConflict.detected_at.desc())
    if not include_resolved:
        query = query.where(models.SyncConflict.resolved_at.is_(None))
    return [ConflictRead.model_validate(row) for row in session.scalars(query).all()]


@router.post("/conflicts/{conflict_id}/dismiss", response_model=ConflictRead)
def dismiss_conflict(conflict_id: int, session: SessionDep, caller: CallerDep) -> ConflictRead:
    """Mark a conflict as seen. The record stays; only the prompt goes away."""
    row = session.get(models.SyncConflict, conflict_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such conflict.")
    row.resolved_at = datetime.now(tz=UTC)
    session.commit()
    return ConflictRead.model_validate(row)
