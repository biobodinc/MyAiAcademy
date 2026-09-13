"""Per-client credentials, pairing, revocation, secret storage, export and erase.

These tests are about properties that have to hold, not about wiring: a revoked client
stops working, a pairing code works once, a guessed code is bounded, a client cannot grant
itself more access, an export contains the data and none of the keys, and erase erases.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.db.models import AuditEvent, Device, Memory, PairingCode
from myai_core.paths import AppPaths
from myai_core.privacy.portability import ERASE_CONFIRMATION, MANIFEST_NAME
from myai_core.security.devices import MAX_CODE_ATTEMPTS, hash_secret
from myai_core.security.storage_checks import check_secret_storage, repair_secret_storage

TOKEN = "owner-token"


@pytest.fixture
def client(app_paths: AppPaths, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(CoreSettings(), app_paths, token=TOKEN)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": f"Bearer {TOKEN}"})
        c.post("/api/profile", json={"name": "Nova"})
        c.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
        yield c


def _as(client: TestClient, token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pair(
    client: TestClient,
    name: str = "My CLI",
    kind: str = "cli",
    *,
    preset: str = "full",
) -> tuple[str, str]:
    """Owner creates a code; a client with no credential redeems it. Returns (id, token).

    These tests are about credentials rather than scope, so the code carries a full client
    grant by default — what a paired client could do before Phase 9 narrowed it. Scope is
    tested on its own in `test_capabilities.py`.
    """
    code = client.post(
        "/api/security/pairing-codes", json={"label": name, "preset": preset}
    ).json()["code"]
    issued = client.post("/api/security/pair", json={"code": code, "name": name, "kind": kind})
    assert issued.status_code == 201, issued.text
    body = issued.json()
    return body["device"]["id"], body["token"]


# --- credentials ------------------------------------------------------------------------------


def test_a_paired_client_can_use_the_api_and_is_named_in_the_overview(
    client: TestClient,
) -> None:
    device_id, token = _pair(client)
    overview = client.get("/api/security", headers=_as(client, token)).json()
    assert overview["caller_is_owner"] is False
    assert overview["caller_name"] == "My CLI"
    assert overview["active_clients"] == 1
    # It can do ordinary work, not just read about itself.
    assert client.get("/api/status", headers=_as(client, token)).status_code == 200
    assert client.get("/api/security/devices").json()[0]["id"] == device_id


def test_an_unknown_credential_is_refused(client: TestClient) -> None:
    assert client.get("/api/status", headers=_as(client, "not-a-real-token")).status_code == 401
    assert client.get("/api/status", headers=_as(client, "")).status_code == 401


def test_revoking_a_client_stops_it_on_its_next_request(client: TestClient) -> None:
    device_id, token = _pair(client)
    assert client.get("/api/status", headers=_as(client, token)).status_code == 200

    revoked = client.post(
        f"/api/security/devices/{device_id}/revoke", json={"reason": "lost the laptop"}
    )
    assert revoked.status_code == 200 and revoked.json()["revoked_at"] is not None
    assert client.get("/api/status", headers=_as(client, token)).status_code == 401
    # The owner's own token is untouched by revoking someone else's.
    assert client.get("/api/status").status_code == 200


def test_a_client_cannot_grant_or_revoke_access(client: TestClient) -> None:
    """A compromised client must not be able to quietly issue itself a spare key."""
    device_id, token = _pair(client)
    headers = _as(client, token)
    assert client.post("/api/security/pairing-codes", json={}, headers=headers).status_code == 403
    assert (
        client.post("/api/security/devices", json={"name": "x"}, headers=headers).status_code == 403
    )
    assert (
        client.post(
            f"/api/security/devices/{device_id}/revoke", json={}, headers=headers
        ).status_code
        == 403
    )
    assert client.post("/api/privacy/export", json={}, headers=headers).status_code == 403
    assert (
        client.post(
            "/api/privacy/erase", json={"confirm": ERASE_CONFIRMATION}, headers=headers
        ).status_code
        == 403
    )


def test_the_credential_itself_is_never_stored(client: TestClient) -> None:
    device_id, token = _pair(client)
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        row = session.get(Device, device_id)
        assert row is not None
        assert token not in row.token_hash
        assert row.token_hash == hash_secret(token)
        # Nor is any code kept in the clear.
        for code in session.scalars(select(PairingCode)).all():
            assert len(code.code_hash) == 64


# --- pairing codes ----------------------------------------------------------------------------


def test_a_pairing_code_works_exactly_once(client: TestClient) -> None:
    code = client.post("/api/security/pairing-codes", json={}).json()["code"]
    first = client.post("/api/security/pair", json={"code": code, "name": "A"})
    assert first.status_code == 201
    second = client.post("/api/security/pair", json={"code": code, "name": "B"})
    assert second.status_code == 403 and "already been used" in second.json()["detail"]
    assert client.get("/api/security/devices").json().__len__() == 1


def test_an_expired_code_is_refused(client: TestClient) -> None:
    code = client.post("/api/security/pairing-codes", json={}).json()["code"]
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        row = session.scalar(select(PairingCode))
        assert row is not None
        row.expires_at = datetime.now(tz=UTC) - timedelta(seconds=1)
        session.commit()
    res = client.post("/api/security/pair", json={"code": code, "name": "A"})
    assert res.status_code == 403 and "expired" in res.json()["detail"]


def test_guessing_burns_the_code_it_is_guessing_at(client: TestClient) -> None:
    """Wrong guesses are charged against every live code, so guessing is bounded."""
    code = client.post("/api/security/pairing-codes", json={}).json()["code"]
    for _ in range(MAX_CODE_ATTEMPTS):
        assert (
            client.post("/api/security/pair", json={"code": "00000000", "name": "x"}).status_code
            == 403
        )
    res = client.post("/api/security/pair", json={"code": code, "name": "A"})
    assert res.status_code == 403 and "too many times" in res.json()["detail"]

    events = client.get("/api/audit", params={"category": "security"}).json()
    assert any(e["action"] == "pairing_code_rejected" for e in events)


def test_pairing_is_written_to_the_audit_log(client: TestClient) -> None:
    device_id, _ = _pair(client, name="Studio tool", kind="integration")
    client.post(f"/api/security/devices/{device_id}/revoke", json={"reason": "done"})
    actions = [
        e["action"] for e in client.get("/api/audit", params={"category": "security"}).json()
    ]
    assert "pairing_code_created" in actions
    assert "device_authorised" in actions
    assert "device_revoked" in actions


def test_what_a_client_does_is_recorded_against_it(client: TestClient, tmp_path: Path) -> None:
    """The audit log has to answer "who did this", not only "this happened"."""
    device_id, token = _pair(client)
    doc = tmp_path / "notes.txt"
    doc.write_text("a document added by a paired client", encoding="utf-8")
    added = client.post("/api/knowledge/files", json={"path": str(doc)}, headers=_as(client, token))
    assert added.status_code in {200, 201}, added.text

    by_client = client.get("/api/audit", params={"device_id": device_id}).json()
    assert by_client, "nothing was attributed to the client that did it"
    assert all(e["device_id"] == device_id for e in by_client)

    # The owner's own actions are attributed to the installation, not left blank.
    client.post("/api/memory", json={"content": "added by the owner"})
    by_owner = client.get("/api/audit", params={"device_id": "owner"}).json()
    assert by_owner and all(e["device_id"] == "owner" for e in by_owner)
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        assert session.scalar(select(Memory)) is not None


# --- secret storage ---------------------------------------------------------------------------


def test_secret_storage_is_reported_and_repaired(app_paths: AppPaths) -> None:
    report = check_secret_storage(app_paths)
    if not report.checked:  # Windows: ACLs, not mode bits
        assert "ACLs" in report.detail
        return
    app_paths.token_file.write_text("x", encoding="utf-8")
    app_paths.token_file.chmod(0o644)
    loose = check_secret_storage(app_paths)
    assert loose.owner_only is False
    assert loose.problems and "read by other users" in loose.problems[0]

    changed = repair_secret_storage(app_paths)
    assert changed
    fixed = check_secret_storage(app_paths)
    assert fixed.owner_only is True and fixed.problems == []


def test_the_overview_reports_the_posture_without_leaking_a_secret(client: TestClient) -> None:
    body = client.get("/api/security").text
    assert TOKEN not in body
    overview = json.loads(body)
    assert overview["bound_to_loopback"] is True
    assert overview["account"]["linked"] is False and overview["account"]["available"] is False
    assert "no accounts" in overview["account"]["detail"]


# --- export and erase -------------------------------------------------------------------------


def test_export_contains_the_data_and_none_of_the_keys(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/memory", json={"content": "remember the export test"})
    _device_id, token = _pair(client)

    result = client.post("/api/privacy/export", json={}).json()
    archive = Path(result["path"])
    assert archive.is_file() and result["size_bytes"] > 0

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert MANIFEST_NAME in names
        assert "database/myai-core.sqlite3" in names
        manifest = json.loads(zf.read(MANIFEST_NAME))
        blob = zf.read("database/myai-core.sqlite3")
    assert manifest["row_counts"]["memories"] == 1
    assert any("credentials" in line for line in manifest["excludes"])
    # The secrets themselves are not in the archive, in any entry.
    assert TOKEN.encode() not in blob
    assert token.encode() not in blob


def test_erase_needs_the_phrase_and_then_removes_everything(
    client: TestClient, tmp_path: Path
) -> None:
    client.post("/api/memory", json={"content": "this will be erased"})
    _pair(client)
    plan = client.get("/api/privacy/erase-preview").json()
    assert plan["row_counts"]["memories"] == 1
    assert plan["confirmation_phrase"] == ERASE_CONFIRMATION
    assert any("cannot be undone" in w for w in plan["warnings"])

    refused = client.post("/api/privacy/erase", json={"confirm": "yes"})
    assert refused.status_code == 400 and "Nothing was deleted" in refused.json()["detail"]
    assert client.get("/api/memory").json() != []

    done = client.post("/api/privacy/erase", json={"confirm": ERASE_CONFIRMATION}).json()
    assert done["rows_deleted"]["memories"] == 1
    # First-run state: there is no profile, so the things that belong to one are gone.
    assert client.get("/api/profile").json() is None
    assert client.get("/api/memory").status_code == 409
    assert client.get("/api/security/devices").json() == []

    # The erasure itself is the one thing the log keeps, so the user can see it happened.
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        events = session.scalars(select(AuditEvent)).all()
        assert [e.action for e in events] == ["data_erased"]


def test_erase_can_leave_the_files_alone_or_delete_them(client: TestClient, tmp_path: Path) -> None:
    junk = tmp_path / "MyAI" / "Models" / "big.gguf"
    junk.parent.mkdir(parents=True, exist_ok=True)
    junk.write_bytes(b"x" * 32)

    kept = client.post("/api/privacy/erase", json={"confirm": ERASE_CONFIRMATION}).json()
    assert kept["files_deleted"] == 0 and junk.is_file()
    assert any("left alone" in note for note in kept["notes"])

    client.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
    removed = client.post(
        "/api/privacy/erase", json={"confirm": ERASE_CONFIRMATION, "remove_files": True}
    ).json()
    assert removed["files_deleted"] >= 1 and not junk.exists()


def test_every_table_of_user_data_is_covered_by_erase() -> None:
    """A table added later must be considered here, not silently survive an erase."""
    from myai_core.db.base import Base
    from myai_core.privacy.portability import _ERASABLE

    erasable = {name for name, _model in _ERASABLE}
    infrastructure = {
        "alembic_version",  # migration bookkeeping, not user data
        "preferences",  # settings, deliberately kept so the app restarts configured
        "storage_config",  # where the storage root is, kept for the same reason
        "hardware_benchmarks",  # measurements of this machine, not about the user
        "jobs",  # cleared with the skills they belong to below
    }
    missing = set(Base.metadata.tables) - erasable - infrastructure
    assert not missing, f"tables neither erased nor explicitly excluded: {sorted(missing)}"


def test_pairing_keeps_the_browser_protections_it_cannot_keep_a_credential(
    client: TestClient,
) -> None:
    """Pairing has no credential by definition, so the other layers have to still apply.

    Without this, a web page the user visits could walk them through pairing itself and
    end up holding a working credential.
    """
    code = client.post("/api/security/pairing-codes", json={}).json()["code"]
    body = {"code": code, "name": "From a web page"}

    from_a_page = client.post(
        "/api/security/pair", json=body, headers={"Origin": "https://evil.example"}
    )
    assert from_a_page.status_code == 403

    wrong_host = client.post("/api/security/pair", json=body, headers={"Host": "myai.example"})
    assert wrong_host.status_code == 421

    # The code was not consumed by either attempt, so the real client can still use it.
    assert client.post("/api/security/pair", json=body).status_code == 201
