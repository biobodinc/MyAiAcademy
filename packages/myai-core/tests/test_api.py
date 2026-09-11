"""Route-level integration tests through the real app (migrations, auth, services)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_status_shape_is_honest(client: TestClient) -> None:
    data = client.get("/api/status").json()
    assert data["ai"] == "not_configured"
    assert data["training"] == "unavailable"
    assert data["cloud_uploads"] == 0
    assert data["privacy_mode"] == "private"
    assert data["profile_exists"] is False


def test_profile_lifecycle(client: TestClient) -> None:
    assert client.get("/api/profile").json() is None
    created = client.post("/api/profile", json={"name": "Nova", "owner_name": "Alex"})
    assert created.status_code == 201
    ai_id = created.json()["ai_id"]
    assert ai_id.startswith("myai_")
    assert client.post("/api/profile", json={"name": "Again"}).status_code == 409

    updated = client.patch("/api/profile", json={"personality": "curious", "expected_version": 1})
    assert updated.status_code == 200 and updated.json()["version"] == 2
    stale = client.patch("/api/profile", json={"name": "X", "expected_version": 1})
    assert stale.status_code == 409

    events = client.get("/api/audit", params={"category": "profile"}).json()
    assert [e["action"] for e in events] == ["updated", "created"]
    assert "curious" not in str(events)  # audit stores facts, not content


def test_storage_flow(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "MyAI"
    check = client.get("/api/storage/check", params={"path": str(root)}).json()
    assert check["ok"] is True
    assert client.put("/api/storage/root", json={"root_path": str(root)}).status_code == 200
    overview = client.get("/api/storage").json()
    assert overview["configured"] and overview["root_path"] == str(root)
    assert {c["category"] for c in overview["categories"]} >= {"models", "checkpoints"}

    bad = client.put("/api/storage/root", json={"root_path": "relative"})
    assert bad.status_code == 422

    override = client.put(
        "/api/storage/overrides", json={"category": "models", "path": str(tmp_path / "ssd")}
    )
    assert override.json()["category_overrides"] == {"models": str(tmp_path / "ssd")}
    assert client.get("/api/status").json()["storage_configured"] is True


def test_preferences_and_consent_audit(client: TestClient) -> None:
    prefs = client.get("/api/preferences").json()
    assert prefs["contributor_mode"] is False
    r = client.patch("/api/preferences", json={"contributor_mode": True, "theme": "dark"})
    assert r.json()["contributor_mode"] is True and r.json()["theme"] == "dark"
    events = client.get("/api/audit", params={"category": "security"}).json()
    assert events and events[0]["action"] == "contributor_mode_changed"
    assert client.patch("/api/preferences", json={"theme": "neon"}).status_code == 422


def test_skills_endpoints(client: TestClient) -> None:
    summary = client.get("/api/skills").json()
    assert summary["overall_level"] == 0
    assert len(summary["skills"]) >= 9
    assert client.get("/api/skills/coding").json()["learned"] is False
    assert client.get("/api/skills/nope").status_code == 404


def test_commands_endpoint(client: TestClient) -> None:
    res = client.post("/api/commands", json={"text": "/status"}).json()
    assert res["outcome"] == "ok"
    res = client.post("/api/commands", json={"text": "teach yourself coding"}).json()
    assert res["command"]["natural_language"] is True
    assert res["outcome"] == "unavailable"
    assert client.post("/api/commands", json={"text": ""}).status_code == 422


def test_hardware_endpoint_caches(client: TestClient) -> None:
    first = client.get("/api/hardware").json()
    second = client.get("/api/hardware").json()
    assert first["detected_at"] == second["detected_at"]
    third = client.get("/api/hardware", params={"refresh": "true"}).json()
    assert third["detected_at"] >= first["detected_at"]


def test_privacy_center(client: TestClient) -> None:
    data = client.get("/api/privacy").json()
    assert data["cloud_ai_data_uploads"] == 0
    assert data["community_sharing"] is False
    assert data["connected_devices"] == 0
