"""The `.myai` portable package: round trips, and every way one can go wrong.

A backup is only worth having if it refuses to open when it is damaged rather than opening
half-way, and if it says what will not work on the machine it lands on. Most of what follows
is about those two things.

The encryption tests use deliberately weak Argon2 parameters. That is safe here because
nothing is being protected — the point is to exercise the code path, and the real parameters
would add a second of grinding to every test.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db import models
from myai_core.db.base import make_engine, make_session_factory
from myai_core.db.migrate import upgrade_to_head
from myai_core.hardware.models import HardwareReport, MemoryInfo
from myai_core.portable import (
    PackageError,
    Verdict,
    WrongPasswordError,
    check_compatibility,
    crypto,
    import_package,
    needs_password,
    open_package,
    preview_import,
    write_package,
)
from myai_core.portable.package import HEADER_NAME, MANIFEST_NAME
from myai_core.sync import install_change_tracking

install_change_tracking()

PASSWORD = "correct horse battery staple"
# Argon2id requires memory_cost >= 8 * lanes; one lane keeps this valid and quick.
_TEST_PARAMS = crypto.KdfParams(salt=b"0123456789abcdef", memory_kib=32, iterations=1, lanes=1)


@pytest.fixture(autouse=True)
def _fast_kdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Argon2 at real settings costs a second per call; nothing here is worth protecting."""
    monkeypatch.setattr(crypto, "new_params", lambda: _TEST_PARAMS)


def _populate(session: Session) -> None:
    session.add(
        models.AIProfile(
            ai_id="myai_source",
            name="Nova",
            personality="Curious",
            goals=["learn Welsh"],
            owner_name="Alex",
        )
    )
    session.flush()
    session.add(models.Project(id="prj_1", ai_id="myai_source", name="Kitchen rebuild"))
    session.flush()
    session.add(
        models.Memory(
            uid="mem_1",
            ai_id="myai_source",
            content="Allergic to penicillin",
            project_id="prj_1",
        )
    )
    session.add(
        models.Conversation(id="conv_1", ai_id="myai_source", title="Planning", project_id="prj_1")
    )
    session.flush()
    session.add(
        models.Message(uid="msg_1", conversation_id="conv_1", role="user", content="Hello there")
    )
    session.add(
        models.SkillState(ai_id="myai_source", skill_id="writing", status="learned", level=42)
    )
    session.add(
        models.InstalledModel(
            id="tiny-1b",
            display_name="Tiny 1B",
            family="tiny",
            file_path="/models/tiny.gguf",
            size_bytes=800_000_000,
            license_id="apache-2.0",
        )
    )
    session.commit()


def _database(path: Path, *, populate: bool = False) -> Session:
    engine = make_engine(path)
    upgrade_to_head(engine)
    session = make_session_factory(engine)()
    if populate:
        _populate(session)
    return session


@pytest.fixture
def source(tmp_path: Path) -> Iterator[Session]:
    session = _database(tmp_path / "source.sqlite3", populate=True)
    yield session
    session.close()


@pytest.fixture
def destination(tmp_path: Path) -> Iterator[Session]:
    session = _database(tmp_path / "destination.sqlite3")
    yield session
    session.close()


def _hardware(total_bytes: int) -> HardwareReport:
    return HardwareReport.model_construct(
        detected_at=datetime.now(tz=UTC), memory=MemoryInfo(total_bytes=total_bytes), gpus=[]
    )


# ---------------------------------------------------------------------------------------
# Round trips.
# ---------------------------------------------------------------------------------------


def test_an_ai_survives_a_round_trip_to_another_machine(
    source: Session, destination: Session, tmp_path: Path
) -> None:
    """The whole promise of the phase: two separate databases, one AI."""
    written = write_package(source, destination=tmp_path / "nova")
    assert written.path.suffix == ".myai" and written.size_bytes > 0

    with open_package(written.path) as package:
        import_package(destination, package)

    profile = destination.scalar(select(models.AIProfile))
    assert profile is not None and profile.name == "Nova"
    assert profile.goals == ["learn Welsh"]
    assert [m.content for m in destination.scalars(select(models.Memory)).all()] == [
        "Allergic to penicillin"
    ]
    assert destination.scalar(select(models.Conversation)).title == "Planning"
    assert destination.scalar(select(models.Message)).content == "Hello there"
    assert destination.scalar(select(models.SkillState)).level == 42

    # Grouping survives too: a project that arrived with nothing filed under it would be a
    # package that technically round-tripped and practically lost the user's organisation.
    project = destination.scalar(select(models.Project))
    assert project is not None and project.name == "Kitchen rebuild"
    assert destination.scalar(select(models.Conversation)).project_id == project.id
    assert destination.scalar(select(models.Memory)).project_id == project.id


def test_a_locked_package_needs_its_password_and_nothing_else_opens_it(
    source: Session, tmp_path: Path
) -> None:
    written = write_package(source, destination=tmp_path / "locked", password=PASSWORD)
    assert written.encrypted and needs_password(written.path)

    with pytest.raises(WrongPasswordError):
        open_package(written.path)
    with pytest.raises(WrongPasswordError):
        open_package(written.path, password="not the password")

    with open_package(written.path, password=PASSWORD) as package:
        assert package.manifest.ai["name"] == "Nova"


def test_a_locked_package_gives_away_nothing_to_someone_who_finds_the_drive(
    source: Session, tmp_path: Path
) -> None:
    """The draft format left the manifest in the clear. This is why it does not."""
    written = write_package(source, destination=tmp_path / "locked", password=PASSWORD)
    raw = written.path.read_bytes()

    for secret in (b"Nova", b"Alex", b"penicillin", b"Planning", b"Hello there", b"learn Welsh"):
        assert secret not in raw, f"{secret!r} is readable in a locked package"
    # Even the skill list, which the draft manifest would have published.
    assert b"writing" not in raw

    header = json.loads(zipfile.ZipFile(written.path).read(HEADER_NAME))
    assert header["encryption"]["enabled"] is True
    assert header["encryption"]["kdf"]["algorithm"] == "argon2id"


def test_an_unlocked_package_says_so_rather_than_implying_safety(
    source: Session, tmp_path: Path
) -> None:
    written = write_package(source, destination=tmp_path / "open")
    assert any("not encrypted" in note for note in written.notes)
    assert any("Set a password" in note for note in written.notes)


# ---------------------------------------------------------------------------------------
# Damage and tampering. A backup that opens when it is broken is not a backup.
# ---------------------------------------------------------------------------------------


def _rewrite(path: Path, entry: str, payload: bytes) -> None:
    original = zipfile.ZipFile(path)
    items = [(i, original.read(i.filename)) for i in original.infolist()]
    original.close()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for info, data in items:
            archive.writestr(info.filename, payload if info.filename == entry else data)


def test_a_damaged_entry_is_refused_before_anything_is_imported(
    source: Session, destination: Session, tmp_path: Path
) -> None:
    written = write_package(source, destination=tmp_path / "nova")
    _rewrite(written.path, "memory/memories.json", b'[{"uid":"mem_x","content":"forged"}]')

    with pytest.raises(PackageError, match="does not match its checksum"):
        open_package(written.path)
    # And nothing was written on the way to finding out.
    assert destination.scalar(select(models.Memory)) is None


def test_an_entry_nobody_vouched_for_is_refused(source: Session, tmp_path: Path) -> None:
    """An archive assembled by something other than this program is not opened."""
    written = write_package(source, destination=tmp_path / "nova")
    with zipfile.ZipFile(written.path, "a") as archive:
        archive.writestr("memory/extra.json", b"[]")

    with pytest.raises(PackageError, match="does not list"):
        open_package(written.path)


def test_a_missing_entry_is_refused(source: Session, tmp_path: Path) -> None:
    written = write_package(source, destination=tmp_path / "nova")
    original = zipfile.ZipFile(written.path)
    keep = [
        (i.filename, original.read(i.filename))
        for i in original.infolist()
        if i.filename != "skills/state.json"
    ]
    original.close()
    with zipfile.ZipFile(written.path, "w") as archive:
        for name, data in keep:
            archive.writestr(name, data)

    with pytest.raises(PackageError, match="incomplete"):
        open_package(written.path)


def test_a_locked_entry_cannot_be_moved_to_another_place_in_the_package(
    source: Session, tmp_path: Path
) -> None:
    """The path is bound into the encryption, so a swap fails even with the right key."""
    written = write_package(source, destination=tmp_path / "locked", password=PASSWORD)
    archive = zipfile.ZipFile(written.path)
    memories = archive.read("memory/memories.json")
    archive.close()
    _rewrite(written.path, "identity/profile.json", memories)

    # The digest check catches it first, which is the outer of the two defences.
    with pytest.raises(PackageError):
        open_package(written.path, password=PASSWORD)

    # And the inner one holds on its own: the same bytes will not unseal at another path.
    key = crypto.derive_key(PASSWORD, _TEST_PARAMS)
    with pytest.raises(WrongPasswordError):
        crypto.unseal(key, "identity/profile.json", memories)


def test_something_that_is_not_a_package_is_named_as_such(tmp_path: Path) -> None:
    stranger = tmp_path / "holiday.myai"
    stranger.write_bytes(b"not a zip at all")
    with pytest.raises(PackageError, match="not a MyAI package"):
        open_package(stranger)

    with zipfile.ZipFile(tmp_path / "other.myai", "w") as archive:
        archive.writestr(HEADER_NAME, json.dumps({"format": "something-else"}))
    with pytest.raises(PackageError, match="not a MyAI package"):
        open_package(tmp_path / "other.myai")


def test_a_package_from_a_newer_version_says_to_update(source: Session, tmp_path: Path) -> None:
    written = write_package(source, destination=tmp_path / "future")
    header = json.loads(zipfile.ZipFile(written.path).read(HEADER_NAME))
    header["format_version"] = 99
    _rewrite(written.path, HEADER_NAME, json.dumps(header).encode())

    with pytest.raises(PackageError, match="newer version"):
        open_package(written.path)


# ---------------------------------------------------------------------------------------
# What is deliberately not in a package.
# ---------------------------------------------------------------------------------------


def test_no_credential_is_ever_written_into_a_package(source: Session, tmp_path: Path) -> None:
    """A package is data. An access grant travelling in it would be a key under the mat."""
    source.add(
        models.Device(
            id="dev_1",
            name="A CLI",
            kind="cli",
            token_hash="a" * 64,
            created_at=datetime.now(tz=UTC),
        )
    )
    source.commit()

    written = write_package(source, destination=tmp_path / "nova")
    raw = written.path.read_bytes()
    assert b"a" * 64 not in raw
    assert b"token_hash" not in raw
    assert any("Credentials are never included" in note for note in written.notes)

    with open_package(written.path) as package:
        assert "security/devices.json" not in package.manifest.integrity


def test_model_weights_are_referenced_with_the_reason_rather_than_copied(
    source: Session, tmp_path: Path
) -> None:
    written = write_package(source, destination=tmp_path / "nova")
    assert written.size_bytes < 1_000_000, "an 800 MB model was copied into the package"

    listed = written.manifest.models
    assert [m["id"] for m in listed] == ["tiny-1b"]
    assert listed[0]["included"] is False
    assert "licence" in listed[0]["reason"] and "downloadable" in listed[0]["reason"]


# ---------------------------------------------------------------------------------------
# Landing on a different machine.
# ---------------------------------------------------------------------------------------


def test_the_preview_says_what_will_not_run_here_before_importing(
    source: Session, tmp_path: Path
) -> None:
    written = write_package(source, destination=tmp_path / "nova")
    with open_package(written.path) as package:
        # A laptop with 1 GB cannot load an 800 MB model with room to work.
        cramped = preview_import(package, _hardware(1_000_000_000))
        roomy = preview_import(package, _hardware(64_000_000_000))

    def verdict_for(preview, name: str) -> Verdict:
        return next(c.verdict for c in preview.capabilities if c.name == name)

    assert verdict_for(cramped, "Tiny 1B") is Verdict.STORED_ONLY
    assert "will not run here" in next(
        c.detail for c in cramped.capabilities if c.name == "Tiny 1B"
    )
    assert verdict_for(roomy, "Tiny 1B") is Verdict.MISSING

    # The records themselves always work, on any machine.
    assert verdict_for(cramped, "Identity, memories and conversations") is Verdict.SUPPORTED
    assert cramped.can_import, "a model that cannot run must not block the rest"
    assert cramped.ai_name == "Nova"


def test_a_check_with_no_hardware_report_does_not_pretend_to_know(
    source: Session, tmp_path: Path
) -> None:
    written = write_package(source, destination=tmp_path / "nova")
    with open_package(written.path) as package:
        checks = check_compatibility(package.manifest, None)
    assert all(c.verdict is not Verdict.STORED_ONLY for c in checks)


def test_a_restored_installation_becomes_a_new_device_to_its_peers(
    source: Session, destination: Session, tmp_path: Path
) -> None:
    """The gap ADR-0016 recorded, closed here.

    A restored database's counter is behind what its peers have already read past, so every
    change it went on to make would be skipped. It starts a new identity instead.
    """
    from myai_core.sync import identity

    destination.add(models.SyncPeer(peer_install_id="inst_old_peer", name="Laptop"))
    before = identity(destination).install_id
    destination.commit()

    written = write_package(source, destination=tmp_path / "nova")
    with open_package(written.path) as package:
        result = import_package(destination, package)

    assert result.new_install_id != before
    assert identity(destination).install_id == result.new_install_id
    assert destination.scalar(select(models.SyncPeer)) is None, "stale cursors must not survive"
    assert any("new sync identity" in note for note in result.notes)
    assert any("Pair it with your other devices again" in note for note in result.notes)


def test_importing_replaces_rather_than_merges_and_says_so(
    source: Session, destination: Session, tmp_path: Path
) -> None:
    """Restoring a backup and merging two machines are different asks with different answers."""
    destination.add(models.AIProfile(ai_id="myai_local", name="Someone else"))
    destination.flush()
    destination.add(models.Memory(uid="mem_local", ai_id="myai_local", content="Local note"))
    destination.commit()

    written = write_package(source, destination=tmp_path / "nova")
    with open_package(written.path) as package:
        import_package(destination, package)

    names = [p.name for p in destination.scalars(select(models.AIProfile)).all()]
    assert names == ["Nova"]
    assert [m.content for m in destination.scalars(select(models.Memory)).all()] == [
        "Allergic to penicillin"
    ]


def test_a_field_this_version_does_not_know_is_ignored_rather_than_fatal(
    source: Session, destination: Session, tmp_path: Path
) -> None:
    """A package from a later version of the same format must still restore what it can."""
    written = write_package(source, destination=tmp_path / "nova")
    with open_package(written.path) as package:
        rows = package.section("memory/memories.json")
    rows[0]["mood_ring_colour"] = "turquoise"

    archive = zipfile.ZipFile(written.path)
    manifest = json.loads(archive.read(MANIFEST_NAME))
    archive.close()
    body = json.dumps(rows).encode()
    import hashlib

    manifest["integrity"]["files"]["memory/memories.json"] = hashlib.sha256(body).hexdigest()
    _rewrite(written.path, "memory/memories.json", body)
    _rewrite(written.path, MANIFEST_NAME, json.dumps(manifest).encode())
    header = json.loads(zipfile.ZipFile(written.path).read(HEADER_NAME))
    header["manifest_sha256"] = hashlib.sha256(json.dumps(manifest).encode()).hexdigest()
    _rewrite(written.path, HEADER_NAME, json.dumps(header).encode())

    with open_package(written.path) as package:
        import_package(destination, package)
    assert destination.scalar(select(models.Memory)).content == "Allergic to penicillin"


# ---------------------------------------------------------------------------------------
# Through the API, where the confirmation and the owner boundary live.
# ---------------------------------------------------------------------------------------


def test_the_api_writes_previews_and_restores_a_package(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from myai_core.api.app import create_app
    from myai_core.config import CoreSettings
    from myai_core.paths import AppPaths

    token = "owner-token"
    app = create_app(CoreSettings(), AppPaths(data_dir=tmp_path / "install").ensure(), token=token)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers.update({"Authorization": f"Bearer {token}"})
        client.post("/api/profile", json={"name": "Nova"})
        client.post("/api/memory", json={"content": "Allergic to penicillin"})

        # No destination given: it has to land somewhere sensible on its own.
        default = client.post("/api/portable", json={})
        assert default.status_code == 201, default.text
        assert Path(default.json()["path"]).is_file()

        written = client.post("/api/portable", json={"destination": str(tmp_path / "out" / "nova")})
        assert written.status_code == 201, written.text
        body = written.json()
        assert body["path"].endswith(".myai") and body["encrypted"] is False
        assert any("not encrypted" in note for note in body["notes"])

        looked = client.get("/api/portable/inspect", params={"path": body["path"]}).json()
        assert looked["is_package"] is True and looked["needs_password"] is False

        preview = client.post("/api/portable/preview", json={"path": body["path"]}).json()
        assert preview["ai_name"] == "Nova"
        assert preview["replaces_ai"] == "Nova"
        assert preview["confirmation_phrase"] == "REPLACE MY AI"

        # Importing replaces, so it needs the phrase typed exactly.
        refused = client.post(
            "/api/portable/import", json={"path": body["path"], "confirm": "yes please"}
        )
        assert refused.status_code == 400 and "replaces the AI" in refused.json()["detail"]

        done = client.post(
            "/api/portable/import", json={"path": body["path"], "confirm": "REPLACE MY AI"}
        )
        assert done.status_code == 200, done.text
        assert done.json()["new_install_id"].startswith("inst_")

        actions = [e["action"] for e in client.get("/api/audit").json()]
        assert "portable_package_written" in actions
        assert "portable_package_imported" in actions


def test_a_paired_device_cannot_copy_or_replace_the_ai(tmp_path: Path) -> None:
    """A phone may use the AI. It may not write the whole of it to a file."""
    from fastapi.testclient import TestClient

    from myai_core.api.app import create_app
    from myai_core.config import CoreSettings
    from myai_core.paths import AppPaths

    token = "owner-token"
    app = create_app(CoreSettings(), AppPaths(data_dir=tmp_path / "install").ensure(), token=token)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers.update({"Authorization": f"Bearer {token}"})
        client.post("/api/profile", json={"name": "Nova"})
        code = client.post("/api/security/pairing-codes", json={"label": "Phone"}).json()["code"]
        issued = client.post(
            "/api/security/pair", json={"code": code, "name": "Phone", "kind": "mobile"}
        ).json()

        client.headers.update({"Authorization": f"Bearer {issued['token']}"})
        assert client.post("/api/portable", json={}).status_code == 403
        assert client.post("/api/portable/preview", json={"path": "x"}).status_code == 403
        assert (
            client.post(
                "/api/portable/import", json={"path": "x", "confirm": "REPLACE MY AI"}
            ).status_code
            == 403
        )


def test_a_locked_package_is_refused_through_the_api_without_its_password(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from myai_core.api.app import create_app
    from myai_core.config import CoreSettings
    from myai_core.paths import AppPaths

    token = "owner-token"
    app = create_app(CoreSettings(), AppPaths(data_dir=tmp_path / "install").ensure(), token=token)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers.update({"Authorization": f"Bearer {token}"})
        client.post("/api/profile", json={"name": "Nova"})
        written = client.post(
            "/api/portable",
            json={"destination": str(tmp_path / "locked"), "password": PASSWORD},
        ).json()
        assert written["encrypted"] is True

        assert client.get("/api/portable/inspect", params={"path": written["path"]}).json()[
            "needs_password"
        ]
        refused = client.post("/api/portable/preview", json={"path": written["path"]})
        assert refused.status_code == 401

        opened = client.post(
            "/api/portable/preview", json={"path": written["path"], "password": PASSWORD}
        )
        assert opened.status_code == 200 and opened.json()["encrypted"] is True
