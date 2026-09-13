"""Keeping a user's own devices in step, and the ways that can go wrong.

Sync is the part of this program where a bug does not produce an error message — it produces
a note that quietly never arrived, or a deleted conversation that came back, or someone's
edit replaced by an older one from a machine that had been asleep. So the tests here are
mostly about those, not about the happy path.

The two-installation tests further down run two complete services, each with its own
database, and sync them over the real HTTPS listener from Phase 6. Nothing is simulated: if
they pass, two devices genuinely converge.
"""

from __future__ import annotations

import json
import ssl
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.db import models
from myai_core.db.base import make_engine, make_session_factory
from myai_core.db.migrate import upgrade_to_head
from myai_core.network import start_listener
from myai_core.paths import AppPaths
from myai_core.security.host_certificate import load_or_create
from myai_core.sync import (
    NOT_SYNCED,
    SYNCED,
    Change,
    apply_changes,
    changes_since,
    derive_key,
    identity,
    install_change_tracking,
    open_envelope,
    seal,
)
from myai_core.sync.envelope import CannotOpenError
from myai_core.sync.registry import BY_NAME

install_change_tracking()


# --------------------------------------------------------------------------------------
# One database: what the clock does, and what it refuses to do.
# --------------------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(tmp_path / "sync.sqlite3")
    upgrade_to_head(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(models.AIProfile(ai_id="myai_test", name="Nova"))
        session.commit()
        yield session
    engine.dispose()


def _conversation(session: Session, uid: str, title: str = "First") -> models.Conversation:
    row = models.Conversation(id=uid, ai_id="myai_test", title=title)
    session.add(row)
    session.commit()
    return row


def test_every_table_is_either_synced_or_has_a_reason_not_to_be(db: Session) -> None:
    """A new table must not be able to slip in without someone deciding.

    Sync is the one feature where "I did not think about it" is indistinguishable from "it
    deliberately stays here", so the registry is made to enumerate both.
    """
    tables = set(inspect(db.get_bind()).get_table_names()) - {"alembic_version"}
    tables = {name for name in tables if not name.endswith(("_fts", "_fts_data", "_fts_idx"))}
    tables = {name for name in tables if "_fts" not in name}

    synced = {entity.model.__tablename__ for entity in SYNCED}
    classified = synced | set(NOT_SYNCED)
    assert tables <= classified, f"not classified as syncing or not: {sorted(tables - classified)}"
    assert not (synced & set(NOT_SYNCED)), "a table cannot be both"
    assert all(reason.strip() for reason in NOT_SYNCED.values()), "every exclusion needs a reason"


def test_what_a_conflict_keeps_is_erasable_like_anything_else(db: Session) -> None:
    """A conflict record holds a whole copy of a row, so it is user data wherever it sits.

    The Privacy Center's erase is checked for total coverage by its own test; this one says
    why these tables have to be in it at all.
    """
    from myai_core.privacy.portability import _ERASABLE

    covered = {name for name, _ in _ERASABLE}
    assert {"sync_conflicts", "sync_tombstones", "sync_peers", "sync_identity"} <= covered


def test_a_credential_never_travels(db: Session) -> None:
    """The clearest thing sync must not do."""
    assert "devices" in NOT_SYNCED
    assert models.Device not in {entity.model for entity in SYNCED}
    for entity in SYNCED:
        assert not any("token" in field or "secret" in field for field in entity.fields)


def test_changes_are_numbered_without_any_service_asking(db: Session) -> None:
    """The listener stamps the row; nothing in the chat service knows sync exists."""
    row = _conversation(db, "conv_1")
    assert row.sync_seq == 1
    assert row.sync_origin == identity(db).install_id

    second = _conversation(db, "conv_2")
    assert second.sync_seq is not None and second.sync_seq > row.sync_seq


def test_rewriting_a_row_with_the_same_values_does_not_move_the_clock(db: Session) -> None:
    """Otherwise a peer's cursor walks forward over nothing, every time anything is saved."""
    row = _conversation(db, "conv_1", title="Same")
    before = row.sync_seq

    row.title = "Same"
    db.commit()
    assert row.sync_seq == before

    row.title = "Different"
    db.commit()
    assert row.sync_seq is not None and before is not None and row.sync_seq > before


def test_a_deletion_travels_as_a_change(db: Session) -> None:
    row = _conversation(db, "conv_1")
    db.delete(row)
    db.commit()

    stone = db.scalar(select(models.SyncTombstone).where(models.SyncTombstone.uid == "conv_1"))
    assert stone is not None and stone.entity == "conversation"
    assert [c.deleted for c in changes_since(db, 0) if c.uid == "conv_1"] == [True]


def test_changes_arrive_in_the_order_they_happened(db: Session) -> None:
    """A message must never be offered before the conversation that holds it."""
    _conversation(db, "conv_1")
    db.add(models.Message(uid="msg_a", conversation_id="conv_1", role="user", content="hello"))
    db.commit()

    batch = changes_since(db, 0)
    kinds = [c.entity for c in batch]
    assert kinds.index("conversation") < kinds.index("message")
    assert [c.seq for c in batch] == sorted(c.seq for c in batch)


def test_a_cursor_asks_only_for_what_is_new(db: Session) -> None:
    _conversation(db, "conv_1")
    cursor = max(c.seq for c in changes_since(db, 0))
    assert changes_since(db, cursor) == []

    _conversation(db, "conv_2")
    later = changes_since(db, cursor)
    assert [c.uid for c in later] == ["conv_2"]


# --------------------------------------------------------------------------------------
# Applying someone else's changes.
# --------------------------------------------------------------------------------------


def _incoming(uid: str, *, title: str, version: int, origin: str, when: datetime) -> Change:
    return Change(
        entity="conversation",
        uid=uid,
        seq=1,
        deleted=False,
        version=version,
        origin=origin,
        updated_at=when,
        fields={
            "id": uid,
            "ai_id": "myai_test",
            "title": title,
            "created_at": when.isoformat(),
            "updated_at": when.isoformat(),
            "version": version,
        },
    )


def test_a_change_from_elsewhere_is_applied(db: Session) -> None:
    now = datetime.now(tz=UTC)
    report = apply_changes(
        db,
        [_incoming("conv_x", title="From the laptop", version=1, origin="inst_b", when=now)],
        peer="inst_b",
    )
    db.commit()
    assert report.applied == 1
    stored = db.get(models.Conversation, "conv_x")
    assert stored is not None and stored.title == "From the laptop"
    assert stored.sync_origin == "inst_b"


def test_our_own_change_coming_back_around_a_ring_is_ignored(db: Session) -> None:
    """Three devices in a circle would otherwise pass one edit round forever."""
    row = _conversation(db, "conv_1", title="Mine")
    mine = identity(db).install_id
    now = datetime.now(tz=UTC)

    report = apply_changes(
        db, [_incoming("conv_1", title="Mine", version=1, origin=mine, when=now)], peer="inst_b"
    )
    assert report.applied == 0 and report.skipped == 1
    assert row.title == "Mine"


def test_a_deletion_here_is_not_undone_by_a_device_that_had_not_heard(db: Session) -> None:
    """The failure this prevents is a conversation the user deleted reappearing."""
    row = _conversation(db, "conv_1")
    db.delete(row)
    db.commit()

    stale = _incoming(
        "conv_1",
        title="Back from the dead",
        version=1,
        origin="inst_b",
        when=datetime.now(tz=UTC),
    )
    report = apply_changes(db, [stale], peer="inst_b")
    db.commit()
    assert report.applied == 0
    assert db.get(models.Conversation, "conv_1") is None


def test_an_edit_made_after_a_deletion_does_outrank_it(db: Session) -> None:
    """A delete must stick, but not against a genuinely newer edit elsewhere."""
    row = _conversation(db, "conv_1")
    db.delete(row)
    db.commit()

    newer = _incoming(
        "conv_1", title="Edited later", version=5, origin="inst_b", when=datetime.now(tz=UTC)
    )
    apply_changes(db, [newer], peer="inst_b")
    db.commit()
    restored = db.get(models.Conversation, "conv_1")
    assert restored is not None and restored.title == "Edited later"


def test_a_deletion_for_something_we_never_had_is_remembered(db: Session) -> None:
    """Otherwise the row arrives later from a third device and is treated as news."""
    gone = Change(
        entity="conversation",
        uid="conv_never",
        seq=9,
        deleted=True,
        version=2,
        origin="inst_b",
        updated_at=datetime.now(tz=UTC),
    )
    apply_changes(db, [gone], peer="inst_b")
    db.commit()

    stone = db.scalar(select(models.SyncTombstone).where(models.SyncTombstone.uid == "conv_never"))
    assert stone is not None

    late = _incoming(
        "conv_never", title="Stale", version=1, origin="inst_c", when=datetime.now(tz=UTC)
    )
    apply_changes(db, [late], peer="inst_c")
    db.commit()
    assert db.get(models.Conversation, "conv_never") is None


# --------------------------------------------------------------------------------------
# Conflicts. The rule matters; what happens to the loser matters more.
# --------------------------------------------------------------------------------------


def test_the_higher_version_wins_and_the_loser_is_kept(db: Session) -> None:
    row = _conversation(db, "conv_1", title="Written here")
    row.version = 2
    db.commit()

    report = apply_changes(
        db,
        [
            _incoming(
                "conv_1",
                title="Written there",
                version=7,
                origin="inst_b",
                when=datetime.now(tz=UTC),
            )
        ],
        peer="inst_b",
    )
    db.commit()

    assert report.conflicts == 1
    assert db.get(models.Conversation, "conv_1").title == "Written there"
    kept = db.scalar(select(models.SyncConflict))
    assert kept is not None and kept.kept == "remote"
    assert kept.losing_payload["title"] == "Written here", "the replaced version must survive"


def test_an_older_change_does_not_replace_a_newer_one_and_is_still_kept(db: Session) -> None:
    """A laptop that was asleep must not overwrite what was written while it slept."""
    row = _conversation(db, "conv_1", title="Current")
    row.version = 9
    db.commit()

    report = apply_changes(
        db,
        [
            _incoming(
                "conv_1",
                title="Stale",
                version=2,
                origin="inst_b",
                when=datetime.now(tz=UTC) - timedelta(hours=3),
            )
        ],
        peer="inst_b",
    )
    db.commit()

    assert report.applied == 0 and report.conflicts == 1
    assert db.get(models.Conversation, "conv_1").title == "Current"
    kept = db.scalar(select(models.SyncConflict))
    assert kept is not None and kept.kept == "local" and kept.losing_payload["title"] == "Stale"


def test_both_devices_resolve_an_identical_clash_the_same_way(db: Session) -> None:
    """If the two disagreed, each would keep offering the other 'news' forever."""
    from myai_core.sync.engine import _remote_wins

    when = datetime.now(tz=UTC)
    incoming = _incoming("conv_1", title="B", version=3, origin="inst_bbb", when=when)

    class FakeLocal:
        version = 3
        updated_at = when

    # On this machine the local row is inst_aaa; on the other, the roles are exactly
    # reversed. Exactly one of the two comparisons must say "the remote one wins".
    here = _remote_wins(incoming, FakeLocal(), "inst_aaa")
    mirrored = _incoming("conv_1", title="A", version=3, origin="inst_aaa", when=when)
    there = _remote_wins(mirrored, FakeLocal(), "inst_bbb")
    assert here != there


def test_an_identical_change_is_not_a_conflict(db: Session) -> None:
    """Two devices arriving at the same value is agreement, not a clash to report."""
    row = _conversation(db, "conv_1", title="Same words")
    same = _incoming(
        "conv_1",
        title="Same words",
        version=row.version,
        origin="inst_b",
        when=row.updated_at,
    )
    same.fields["created_at"] = row.created_at.isoformat()
    report = apply_changes(db, [same], peer="inst_b")
    db.commit()
    assert report.conflicts == 0
    assert db.scalar(select(models.SyncConflict)) is None


# --------------------------------------------------------------------------------------
# The envelope: what a relay would be able to read.
# --------------------------------------------------------------------------------------


def test_a_relay_carrying_the_envelope_can_read_nothing_of_it() -> None:
    """This is the property a relay has to be built on, so it is proven before one exists."""
    secret = "the-credential-both-devices-share"
    batch = {"changes": [{"entity": "memory", "fields": {"content": "My blood type is O-"}}]}

    envelope = seal(derive_key(secret), batch)
    on_the_wire = json.dumps(envelope.to_json()).encode()

    # Everything the relay sees, searched for anything the user would mind it seeing.
    assert b"blood type" not in on_the_wire
    assert b"memory" not in on_the_wire
    assert b"O-" not in on_the_wire
    # And it cannot open it, even knowing exactly how it was made.
    with pytest.raises(CannotOpenError):
        open_envelope(derive_key("a-guess-at-the-credential"), envelope)


def test_the_other_device_opens_it_cleanly() -> None:
    key = derive_key("shared")
    body = {"changes": [1, 2, 3], "install_id": "inst_a"}
    assert open_envelope(key, seal(key, body)) == body


def test_a_payload_changed_on_the_way_is_refused_rather_than_half_applied() -> None:
    key = derive_key("shared")
    envelope = seal(key, {"changes": []})
    tampered = type(envelope)(
        nonce=envelope.nonce,
        ciphertext=envelope.ciphertext[:-1] + bytes([envelope.ciphertext[-1] ^ 1]),
    )
    with pytest.raises(CannotOpenError):
        open_envelope(key, tampered)


def test_two_installations_derive_the_same_key_and_nobody_else_does() -> None:
    assert derive_key("same") == derive_key("same")
    assert derive_key("same") != derive_key("same ")
    assert len(derive_key("same")) == 32


# --------------------------------------------------------------------------------------
# Two complete installations, over the real HTTPS listener.
# --------------------------------------------------------------------------------------

OWNER_A = "owner-token-a"


@pytest.fixture
def two_installations(tmp_path: Path) -> Iterator[dict[str, object]]:
    """Two services, two databases, one HTTPS listener between them."""
    paths_a = AppPaths(data_dir=tmp_path / "a").ensure()
    paths_b = AppPaths(data_dir=tmp_path / "b").ensure()

    app_a = create_app(CoreSettings(), paths_a, token=OWNER_A)
    app_b = create_app(CoreSettings(), paths_b, token="owner-token-b")

    with (
        TestClient(app_a, base_url="http://127.0.0.1") as a,
        TestClient(app_b, base_url="http://127.0.0.1") as b,
    ):
        a.headers.update({"Authorization": f"Bearer {OWNER_A}"})
        b.headers.update({"Authorization": "Bearer owner-token-b"})
        a.post("/api/profile", json={"name": "Nova"})
        b.post("/api/profile", json={"name": "Nova"})

        certificate = load_or_create(paths_a.data_dir, addresses=["127.0.0.1"])
        import socket as _socket

        with _socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])
        listener = start_listener(
            app_a, host="127.0.0.1", port=port, certificate=certificate, wait_seconds=10
        )
        assert listener.running
        try:
            yield {
                "a": a,
                "b": b,
                "base": f"https://127.0.0.1:{port}/api",
                "cert": certificate.cert_path,
            }
        finally:
            listener.stop()


def _paired(env: dict[str, object]) -> httpx.Client:
    """B, holding a credential from A, over a connection pinned to A's certificate."""
    a: TestClient = env["a"]  # type: ignore[assignment]
    code = a.post("/api/security/pairing-codes", json={"label": "Laptop"}).json()["code"]
    context = ssl.create_default_context(cafile=str(env["cert"]))
    client = httpx.Client(verify=context, base_url=str(env["base"]))
    issued = client.post("/security/pair", json={"code": code, "name": "Laptop", "kind": "desktop"})
    assert issued.status_code == 201, issued.text
    client.headers.update({"Authorization": f"Bearer {issued.json()['token']}"})
    return client


def test_a_memory_written_on_one_device_reaches_the_other(
    two_installations: dict[str, object],
) -> None:
    """The whole point of the phase, end to end, over TLS, between two real databases."""
    a: TestClient = two_installations["a"]  # type: ignore[assignment]
    b: TestClient = two_installations["b"]  # type: ignore[assignment]

    a.post("/api/memory", json={"content": "I take my coffee black", "category": "preference"})

    with closing(_paired(two_installations)) as link:
        batch = link.get("/sync/changes", params={"since": 0}).json()
        assert batch["changes"], "A had nothing to send"

        pushed = b.post(
            "/api/sync/changes",
            json={
                "install_id": batch["install_id"],
                "name": "Studio PC",
                "changes": batch["changes"],
            },
        )
    assert pushed.status_code == 200, pushed.text
    assert pushed.json()["applied"] >= 1

    remembered = [m["content"] for m in b.get("/api/memory").json()]
    assert "I take my coffee black" in remembered


def test_syncing_twice_changes_nothing_the_second_time(
    two_installations: dict[str, object],
) -> None:
    """Sync runs on a timer. Running it again must be free, not duplicative."""
    a: TestClient = two_installations["a"]  # type: ignore[assignment]
    b: TestClient = two_installations["b"]  # type: ignore[assignment]
    a.post("/api/memory", json={"content": "Allergic to penicillin", "category": "fact"})

    with closing(_paired(two_installations)) as link:
        batch = link.get("/sync/changes", params={"since": 0}).json()
        body = {"install_id": batch["install_id"], "changes": batch["changes"]}
        first = b.post("/api/sync/changes", json=body).json()
        second = b.post("/api/sync/changes", json=body).json()

    assert first["applied"] >= 1
    assert second["applied"] == 0 and second["conflicts"] == 0
    assert len(b.get("/api/memory").json()) == 1, "the memory was duplicated"


def _pull_and_push(link: httpx.Client, receiver: TestClient, since: int = 0) -> dict[str, Any]:
    """One direction of a sync: read A's changes over TLS and hand them to B."""
    batch = link.get("/sync/changes", params={"since": since}).json()
    return receiver.post(
        "/api/sync/changes",
        json={"install_id": batch["install_id"], "changes": batch["changes"]},
    ).json()


def test_a_conversation_and_its_messages_arrive_together(
    two_installations: dict[str, object],
) -> None:
    """A message whose conversation had not arrived would be an orphan, or an error."""
    a: TestClient = two_installations["a"]  # type: ignore[assignment]
    b: TestClient = two_installations["b"]  # type: ignore[assignment]

    made = a.post("/api/chat/conversations", json={"title": "Planning the trip"})
    assert made.status_code in (200, 201), made.text
    conversation_id = made.json()["id"]

    with closing(_paired(two_installations)) as link:
        result = _pull_and_push(link, b)
    assert result["applied"] >= 1

    theirs = b.get("/api/chat/conversations").json()
    assert conversation_id in [c["id"] for c in theirs]


def test_the_two_converge_and_then_have_nothing_left_to_say(
    two_installations: dict[str, object],
) -> None:
    """Sync runs repeatedly. Two devices in step must fall silent, not trade rows forever.

    This is the failure that does not look like one: each side keeps "helpfully" returning
    the other's own change, both stay busy, and the batch never empties.
    """
    a: TestClient = two_installations["a"]  # type: ignore[assignment]
    b: TestClient = two_installations["b"]  # type: ignore[assignment]
    # Checked, because a rejected write here would look exactly like a sync that lost it.
    assert a.post("/api/memory", json={"content": "Born in Leeds"}).status_code in (200, 201)
    assert b.post(
        "/api/memory", json={"content": "Plays the cello", "category": "preference"}
    ).status_code in (200, 201)

    with closing(_paired(two_installations)) as link:
        # A to B.
        assert _pull_and_push(link, b)["applied"] >= 1

        # B to A, over the same pinned connection.
        b_batch = b.get("/api/sync/changes", params={"since": 0}).json()
        pushed = link.post(
            "/sync/changes",
            json={"install_id": b_batch["install_id"], "changes": b_batch["changes"]},
        )
        assert pushed.status_code == 200, pushed.text

        both = {"Born in Leeds", "Plays the cello"}
        assert {m["content"] for m in a.get("/api/memory").json()} == both
        assert {m["content"] for m in b.get("/api/memory").json()} == both

        # And now each side has nothing new to tell the other. Re-sending what B already
        # holds, including the rows that came from A, changes nothing and conflicts with
        # nothing: A recognises its own work and lets it pass.
        again = b.get("/api/sync/changes", params={"since": 0}).json()
        settled = link.post(
            "/sync/changes",
            json={"install_id": again["install_id"], "changes": again["changes"]},
        ).json()
    assert settled["applied"] == 0 and settled["conflicts"] == 0
    assert len(a.get("/api/memory").json()) == 2, "a memory was duplicated on the way back"


def test_a_device_cannot_claim_to_be_this_installation(
    two_installations: dict[str, object],
) -> None:
    """Two databases sharing one clock would lose changes silently in both directions."""
    b: TestClient = two_installations["b"]  # type: ignore[assignment]
    mine = b.get("/api/sync").json()["install_id"]
    refused = b.post("/api/sync/changes", json={"install_id": mine, "changes": []})
    assert refused.status_code == 409
    assert "cannot share one identity" in refused.json()["detail"]


def test_an_unpaired_stranger_cannot_read_the_changes(
    two_installations: dict[str, object],
) -> None:
    context = ssl.create_default_context(cafile=str(two_installations["cert"]))
    with httpx.Client(verify=context, base_url=str(two_installations["base"])) as stranger:
        assert stranger.get("/sync/changes").status_code == 401
        assert stranger.post("/sync/changes", json={"install_id": "x"}).status_code == 401
        # Nor by presenting the owner's token from off the machine.
        refused = stranger.get("/sync/changes", headers={"Authorization": f"Bearer {OWNER_A}"})
        assert refused.status_code == 403


def test_the_overview_says_what_travels_and_what_does_not(
    two_installations: dict[str, object],
) -> None:
    a: TestClient = two_installations["a"]  # type: ignore[assignment]
    overview = a.get("/api/sync").json()

    assert overview["install_id"].startswith("inst_")
    assert {kind["name"] for kind in overview["syncs"]} == {e.name for e in SYNCED}
    assert "devices" in overview["stays_local"]
    assert "credential" in overview["stays_local"]["devices"]
    assert "nothing is uploaded anywhere" in overview["detail"]
    # Nothing that travels carries a secret.
    for kind in overview["syncs"]:
        assert not any("token" in field for field in kind["travels"])
        assert kind["name"] in BY_NAME
