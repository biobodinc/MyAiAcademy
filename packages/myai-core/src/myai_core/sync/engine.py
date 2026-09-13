"""Building a batch of changes, and applying one from another device (spec §16, §72).

The shape of the exchange
-------------------------

Each installation keeps a counter and stamps every change with it. To sync, a device asks
another "what have you done since number N?", applies what comes back, and remembers the
highest number it saw. There is no shared clock, no server deciding the order, and no
requirement that the two machines agree about the time — which they will not.

Conflicts
---------

Two devices can change the same thing while apart. Something has to be chosen, and the
choice must be the same on both machines or they will never converge: if each kept its own
version, every sync would hand the other side "news" and the two would swap forever.

So the rule is deterministic and symmetric — higher ``version`` wins; then the later
``updated_at``; then the higher install id, purely to break the tie the same way on both
sides. What matters more than the rule is what happens to the loser: it is written whole
into ``sync_conflicts``, with its payload, so the user can see what was replaced and put it
back. A person's writing is not something to discard because two clocks disagreed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, select
from sqlalchemy.orm import Session

from myai_core.db import models
from myai_core.sync.changes import identity
from myai_core.sync.registry import BY_NAME, SYNCED, SyncedEntity

BATCH_LIMIT = 500
"""Changes per exchange. A sync is many small round trips, not one enormous one: an
interrupted transfer should cost a few seconds of work, not all of it."""


@dataclass(frozen=True, slots=True)
class Change:
    """One row as it travels. ``fields`` is empty for a deletion."""

    entity: str
    uid: str
    seq: int
    deleted: bool
    version: int
    origin: str | None
    updated_at: datetime | None
    fields: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "uid": self.uid,
            "seq": self.seq,
            "deleted": self.deleted,
            "version": self.version,
            "origin": self.origin,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "fields": {k: _encode(v) for k, v in self.fields.items()},
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Change:
        entity = str(raw.get("entity", ""))
        if entity not in BY_NAME:
            raise ValueError(f"Unknown kind of change: {entity!r}")
        updated = raw.get("updated_at")
        return cls(
            entity=entity,
            uid=str(raw["uid"]),
            seq=int(raw.get("seq", 0)),
            deleted=bool(raw.get("deleted", False)),
            version=int(raw.get("version", 1)),
            origin=str(raw["origin"]) if raw.get("origin") else None,
            updated_at=_parse_time(updated) if isinstance(updated, str) else None,
            fields=dict(raw.get("fields") or {}),
        )


@dataclass(frozen=True, slots=True)
class ApplyReport:
    applied: int = 0
    skipped: int = 0
    conflicts: int = 0
    highest_seq: int = 0


def _encode(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _parse_time(text: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _as_utc(value: Any) -> Any:
    """Make a timestamp comparable however it arrived.

    SQLite has no timezone type: a column declared ``DateTime(timezone=True)`` is written
    with an offset and read back *without* one. So a time loaded from the table is naive
    while the same time parsed from a peer's JSON is aware, and comparing them raises —
    or, worse, would count as a difference and manufacture a conflict on every sync. Both
    sides are UTC; this says so.
    """
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _decode(entity: SyncedEntity, name: str, value: Any) -> Any:
    """Turn a JSON value back into what the column expects."""
    column = entity.model.__table__.columns.get(name)
    if column is None or value is None:
        return value
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return _parse_time(value)
    return value


def changes_since(session: Session, cursor: int, *, limit: int = BATCH_LIMIT) -> list[Change]:
    """Everything this installation has changed after ``cursor``, in the order it happened.

    Ordering by the counter — not by table — is what makes the batch safe to apply as it
    stands: a conversation created before the message in it has a lower number, so it
    arrives first.
    """
    collected: list[Change] = []
    for entity in SYNCED:
        rows = session.scalars(
            select(entity.model)
            .where(entity.model.sync_seq.isnot(None), entity.model.sync_seq > cursor)
            .order_by(entity.model.sync_seq)
            .limit(limit)
        ).all()
        for row in rows:
            collected.append(
                Change(
                    entity=entity.name,
                    uid=str(getattr(row, entity.uid_attr)),
                    seq=int(row.sync_seq or 0),
                    deleted=False,
                    version=int(getattr(row, "version", 1) or 1),
                    origin=getattr(row, "sync_origin", None),
                    updated_at=getattr(row, "updated_at", None),
                    fields={name: getattr(row, name) for name in entity.fields},
                )
            )

    stones = session.scalars(
        select(models.SyncTombstone)
        .where(models.SyncTombstone.sync_seq > cursor)
        .order_by(models.SyncTombstone.sync_seq)
        .limit(limit)
    ).all()
    for stone in stones:
        collected.append(
            Change(
                entity=stone.entity,
                uid=stone.uid,
                seq=stone.sync_seq,
                deleted=True,
                version=stone.version,
                origin=stone.sync_origin,
                updated_at=stone.deleted_at,
            )
        )

    collected.sort(key=lambda change: change.seq)
    return collected[:limit]


def _existing(session: Session, entity: SyncedEntity, uid: str) -> Any:
    column = getattr(entity.model, entity.uid_attr)
    return session.scalar(select(entity.model).where(column == uid))


def _remote_wins(incoming: Change, local: Any, local_origin: str | None) -> bool:
    """The same comparison on both machines, so the two agree on the outcome."""
    local_version = int(getattr(local, "version", 1) or 1)
    if incoming.version != local_version:
        return bool(incoming.version > local_version)

    local_time = _as_utc(getattr(local, "updated_at", None))
    incoming_time = _as_utc(incoming.updated_at)
    if incoming_time is not None and local_time is not None:
        if incoming_time != local_time:
            return bool(incoming_time > local_time)
    elif incoming_time != local_time:
        return incoming_time is not None

    # Identical as far as anything meaningful goes. Pick by install id, not because one
    # device is better, but because both sides must pick the same one.
    return bool((incoming.origin or "") > (local_origin or ""))


def apply_changes(session: Session, incoming: list[Change], *, peer: str) -> ApplyReport:
    """Apply a batch from ``peer``, keeping whatever a conflict displaces."""
    me = identity(session)
    applied = skipped = conflicts = 0
    highest = 0

    for change in sorted(incoming, key=lambda c: c.seq):
        highest = max(highest, change.seq)
        entity = BY_NAME.get(change.entity)
        if entity is None:
            skipped += 1
            continue
        if change.origin == me.install_id:
            # Our own change, come back to us around a ring of devices. Applying it would
            # stamp it with a new number and send it round again, forever.
            skipped += 1
            continue

        local = _existing(session, entity, change.uid)

        if change.deleted:
            if local is not None:
                session.delete(local)
                applied += 1
            else:
                _remember_tombstone(session, change, me.install_id)
                skipped += 1
            continue

        # A row deleted here must not be resurrected by a peer that had not heard yet.
        if local is None and _tombstoned(session, entity.name, change.uid, change.version):
            skipped += 1
            continue

        if local is None:
            session.add(_build(session, entity, change))
            applied += 1
            continue

        local_origin = getattr(local, "sync_origin", None)
        if not _differs(session, entity, local, change):
            skipped += 1
            continue

        if _remote_wins(change, local, local_origin):
            _record_conflict(session, entity, change, local, kept="remote")
            conflicts += 1
            _overwrite(session, entity, local, change)
            applied += 1
        else:
            _record_conflict(session, entity, change, local, kept="local")
            conflicts += 1
            skipped += 1

    return ApplyReport(applied=applied, skipped=skipped, conflicts=conflicts, highest_seq=highest)


def _differs(session: Session, entity: SyncedEntity, local: Any, change: Change) -> bool:
    """Whether anything that travels actually holds a different value here.

    ``ai_id`` is compared after re-binding, or a row that is already correct on this machine
    would look changed on every single sync purely because the two installations name their
    own AI profile differently.
    """
    values = {name: _decode(entity, name, value) for name, value in change.fields.items()}
    for name, value in _rebind(session, entity, values).items():
        if _as_utc(value) != _as_utc(getattr(local, name, None)):
            return True
    return False


def _local_ai_id(session: Session) -> str | None:
    return session.scalar(select(models.AIProfile.ai_id).limit(1))


def _rebind(session: Session, entity: SyncedEntity, values: dict[str, Any]) -> dict[str, Any]:
    """Point a row at the AI that lives on *this* machine.

    ``ai_profile.ai_id`` is generated per installation, so the id attached to a memory on a
    desktop names nothing on a laptop — the foreign key simply fails. The row is not about
    that key, though; it is about the user's AI, and each installation has its own row for
    it. So the key is replaced on arrival.

    This is also the line past which "one AI on two machines" stops being automatic. The two
    installations agree about what the AI knows; making them agree about who it *is* — one
    name, one set of goals, one identity — is the account question, and is not answered here.
    """
    if not entity.rebind_ai or "ai_id" not in values:
        return values
    local_id = _local_ai_id(session)
    return values if local_id is None else {**values, "ai_id": local_id}


def _build(session: Session, entity: SyncedEntity, change: Change) -> Any:
    values = {name: _decode(entity, name, value) for name, value in change.fields.items()}
    instance = entity.model(**_rebind(session, entity, values))
    instance.sync_origin = change.origin
    return instance


def _overwrite(session: Session, entity: SyncedEntity, local: Any, change: Change) -> None:
    values = {name: _decode(entity, name, value) for name, value in change.fields.items()}
    for name, value in _rebind(session, entity, values).items():
        setattr(local, name, value)
    local.sync_origin = change.origin


def _tombstoned(session: Session, entity: str, uid: str, version: int) -> bool:
    stone = session.scalar(
        select(models.SyncTombstone).where(
            models.SyncTombstone.entity == entity, models.SyncTombstone.uid == uid
        )
    )
    # A later edit elsewhere does outrank an older deletion here; an equal or older one
    # does not, or a delete would never stick.
    return stone is not None and version <= stone.version


def _remember_tombstone(session: Session, change: Change, fallback_origin: str) -> None:
    """Record a deletion for something we never had, so we do not accept it back later."""
    existing = session.scalar(
        select(models.SyncTombstone).where(
            models.SyncTombstone.entity == change.entity, models.SyncTombstone.uid == change.uid
        )
    )
    if existing is not None:
        return
    me = identity(session)
    session.add(
        models.SyncTombstone(
            entity=change.entity,
            uid=change.uid,
            sync_seq=me.next_seq,
            sync_origin=change.origin or fallback_origin,
            version=change.version,
        )
    )
    me.next_seq += 1


def _record_conflict(
    session: Session, entity: SyncedEntity, change: Change, local: Any, *, kept: str
) -> None:
    if kept == "remote":
        payload = {name: _encode(getattr(local, name, None)) for name in entity.fields}
        session.add(
            models.SyncConflict(
                entity=entity.name,
                uid=change.uid,
                kept="remote",
                losing_payload=payload,
                losing_version=int(getattr(local, "version", 1) or 1),
                losing_origin=getattr(local, "sync_origin", None),
                losing_updated_at=getattr(local, "updated_at", None),
            )
        )
    else:
        session.add(
            models.SyncConflict(
                entity=entity.name,
                uid=change.uid,
                kept="local",
                losing_payload={k: _encode(v) for k, v in change.fields.items()},
                losing_version=change.version,
                losing_origin=change.origin,
                losing_updated_at=change.updated_at,
            )
        )


def peer_for(session: Session, install_id: str, *, name: str = "", device_id: str = "") -> Any:
    """The record of one other installation, created the first time we hear from it."""
    found = session.scalar(
        select(models.SyncPeer).where(models.SyncPeer.peer_install_id == install_id)
    )
    if found is None:
        found = models.SyncPeer(
            peer_install_id=install_id,
            name=name or "Another device",
            device_id=device_id or None,
        )
        session.add(found)
        session.flush()
    elif name and found.name != name:
        found.name = name
    return found
