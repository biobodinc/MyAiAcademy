"""Stamping every change so it can be sent somewhere else (spec §16, §72).

The obvious way to do this is to have each service record what it changed. That fails in
one specific way and it fails silently: someone adds a feature, forgets the call, and the
edit simply never leaves the machine. Nothing breaks, no test goes red, and the user finds
out months later that one of their devices has been quietly out of date.

So nothing is asked of the services. A ``before_flush`` listener on SQLAlchemy's ``Session``
stamps anything about to be written, wherever it came from — a route, a background job, the
CLI, a migration-time fixup. Forgetting is not available.

Two things are stamped:

* an insert or update to a synced row gets the next number from this installation's clock;
* a delete leaves a tombstone carrying the same number, so the deletion travels too.

The listener is registered on the ``Session`` class rather than on one factory, because
sessions are also opened directly (``DeviceService`` opens its own to count a failed pairing
attempt outside the transaction that is about to roll back). A listener attached to a
factory would miss those.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session
from ulid import ULID

from myai_core.db import models
from myai_core.sync.registry import BY_MODEL, SyncedEntity

_INSTALLED = False


def new_install_id() -> str:
    return f"inst_{ULID()}"


def identity(session: Session) -> models.SyncIdentity:
    """This installation's sync identity, created on first use.

    Creating it lazily rather than at migration time means an installation that never syncs
    never acquires one, and the one it does acquire is not shared by two databases restored
    from the same backup file — the clock would then be meaningless in both.
    """
    found = _find_identity(session)
    if found is not None:
        return found
    created = models.SyncIdentity(id=1, install_id=new_install_id(), next_seq=1)
    session.add(created)
    session.flush()
    return created


def _find_identity(session: Session) -> models.SyncIdentity | None:
    """The identity row, including one created earlier in this same transaction.

    ``session.new`` has to be searched first because the row may have been added during a
    flush that has not finished: a query would go to the database, not find it, and make a
    second one.
    """
    for pending in session.new:
        if isinstance(pending, models.SyncIdentity):
            return pending
    return session.scalar(select(models.SyncIdentity).limit(1))


def _uid_of(entity: SyncedEntity, instance: models.SyncedBase) -> str:
    return str(getattr(instance, entity.uid_attr))


def _stamp(session: Session, _context: Any, _instances: Any) -> None:
    """Give every pending change a number, and every deletion a tombstone."""
    touched = [o for o in (*session.new, *session.dirty) if isinstance(o, models.SyncedBase)]
    removed = [o for o in session.deleted if isinstance(o, models.SyncedBase)]
    # Only rows whose synced columns actually changed are worth a new number: SQLAlchemy
    # marks an object dirty when any attribute is loaded and set, including to the value it
    # already had, and a run of no-op updates would otherwise push a peer's cursor forward
    # over nothing.
    changed = [obj for obj in touched if obj in session.new or _has_real_change(obj)]
    if not changed and not removed:
        return

    # Not `identity()`: that flushes to make the new row queryable, and a flush inside
    # before_flush is refused outright by SQLAlchemy. Adding it here is enough — it is
    # written by the very flush this listener is running for.
    me = _find_identity(session)
    if me is None:
        me = models.SyncIdentity(id=1, install_id=new_install_id(), next_seq=1)
        session.add(me)
    seq = me.next_seq
    for instance in changed:
        instance.sync_seq = seq
        if getattr(instance, "sync_origin", None) is None:
            instance.sync_origin = me.install_id
        seq += 1
    for instance in removed:
        entity = BY_MODEL[type(instance)]
        session.add(
            models.SyncTombstone(
                entity=entity.name,
                uid=_uid_of(entity, instance),
                sync_seq=seq,
                sync_origin=getattr(instance, "sync_origin", None) or me.install_id,
                version=int(getattr(instance, "version", 1) or 1),
            )
        )
        seq += 1
    me.next_seq = seq


def _has_real_change(instance: models.SyncedBase) -> bool:
    """True when a column that actually travels changed value.

    SQLAlchemy marks an object dirty as soon as an attribute is assigned, even to the value
    it already held, and it does so for local-only columns too. Asking the attribute history
    instead means a run that rewrites a row without changing anything a peer would see does
    not push that peer's cursor forward over nothing.
    """
    entity = BY_MODEL[type(instance)]
    attributes = sa_inspect(instance).attrs
    return any(
        name in attributes and attributes[name].history.has_changes() for name in entity.fields
    )


def install_change_tracking() -> None:
    """Attach the listener. Idempotent: importing this module twice must not double-stamp."""
    global _INSTALLED
    if _INSTALLED:
        return
    event.listen(Session, "before_flush", _stamp)
    _INSTALLED = True
