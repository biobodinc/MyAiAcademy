"""Route-level tests for models, chat (SSE), memory and knowledge with a fake provider."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.models.llama_cpp_provider import LlamaCppProvider
from myai_core.paths import AppPaths

TOKEN = "t"


class FakeLlama:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def create_chat_completion(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        system = kwargs["messages"][0]["content"]
        reply = "I remember that." if "likes horses" in system else "Hi!"
        for word in reply.split(" "):
            yield {"choices": [{"delta": {"content": word + " "}, "finish_reason": None}]}
        yield {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }


@pytest.fixture
def client(app_paths: AppPaths, tmp_path: Path) -> Iterator[TestClient]:
    provider = LlamaCppProvider(llama_factory=FakeLlama)
    app = create_app(CoreSettings(), app_paths, token=TOKEN, provider=provider)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": f"Bearer {TOKEN}"})
        c.post("/api/profile", json={"name": "Nova", "owner_name": "Alex"})
        c.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
        yield c


def _install_fake_model(client: TestClient, tmp_path: Path) -> str:
    """Bypass the network: write a file where the download would land and register it."""
    from myai_core.db.models import InstalledModel

    model_id = "qwen2.5-0.5b-instruct-q4km"
    path = tmp_path / "MyAI" / "Models" / "qwen2.5" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake")
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        session.add(
            InstalledModel(
                id=model_id,
                display_name="Qwen",
                family="qwen2.5",
                file_path=str(path),
                size_bytes=4,
                sha256=None,
                license_id="apache-2.0",
            )
        )
        session.commit()
    client.post("/api/models/active", json={"model_id": model_id})
    return model_id


def _sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        kind = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                kind = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if kind is not None and data is not None:
            events.append((kind, data))
    return events


def test_models_overview_and_license_gate(client: TestClient) -> None:
    data = client.get("/api/models").json()
    assert data["runtime_available"] is True and data["active_model_id"] is None
    ids = [m["catalog"]["id"] for m in data["models"]]
    assert "qwen2.5-1.5b-instruct-q4km" in ids
    assert client.get("/api/models/recommended").json()["id"] in ids

    r = client.post("/api/models/qwen2.5-0.5b-instruct-q4km/download")
    assert r.status_code == 409 and "Accept" in r.json()["detail"]
    r = client.post("/api/models/qwen2.5-0.5b-instruct-q4km/accept-license")
    assert r.status_code == 200 and r.json()["license_accepted"] is True
    events = client.get("/api/audit").json()
    assert any(e["action"] == "model_license_accepted" for e in events)
    assert client.post("/api/models/nope/accept-license").status_code == 404
    assert (
        client.post(
            "/api/models/active", json={"model_id": "qwen2.5-0.5b-instruct-q4km"}
        ).status_code
        == 409
    )


def test_status_reports_ai_state(client: TestClient, tmp_path: Path) -> None:
    before = client.get("/api/status").json()
    assert before["ai"] == "not_configured"
    model_id = _install_fake_model(client, tmp_path)
    after = client.get("/api/status").json()
    assert after["ai"] == "available" and after["active_model_id"] == model_id
    assert after["loaded_model_id"] is None
    assert client.post("/api/models/load").status_code == 200
    assert client.get("/api/status").json()["loaded_model_id"] == model_id


def test_chat_stream_with_memory_and_commands(client: TestClient, tmp_path: Path) -> None:
    conv = client.post("/api/chat/conversations", json={}).json()
    r = client.post(f"/api/chat/conversations/{conv['id']}/messages", json={"content": "hello"})
    assert r.status_code == 409  # no model yet: says so instead of pretending

    _install_fake_model(client, tmp_path)
    client.post("/api/memory", json={"content": "Alex likes horses"})
    r = client.post(f"/api/chat/conversations/{conv['id']}/messages", json={"content": "hello"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = _sse(r.text)
    assert events[0][0] == "meta" and events[0][1]["model_id"] == "qwen2.5-0.5b-instruct-q4km"
    text = "".join(d["text"] for k, d in events if k == "delta").strip()
    assert text == "I remember that."
    assert events[-1][0] == "done" and events[-1][1]["prompt_tokens"] == 5

    msgs = client.get(f"/api/chat/conversations/{conv['id']}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert client.get("/api/chat/conversations").json()[0]["title"] == "hello"

    r = client.post(f"/api/chat/conversations/{conv['id']}/messages", json={"content": "/memory"})
    ((kind, payload),) = _sse(r.text)
    assert kind == "command" and payload["outcome"] == "ok" and "horses" in payload["message"]

    assert client.delete(f"/api/chat/conversations/{conv['id']}").status_code == 204
    assert client.get(f"/api/chat/conversations/{conv['id']}/messages").status_code == 404


def test_memory_and_knowledge_routes(client: TestClient, tmp_path: Path) -> None:
    m = client.post(
        "/api/memory", json={"content": "Alex prefers concise answers", "category": "preference"}
    )
    assert m.status_code == 201
    assert client.get("/api/memory", params={"q": "concise"}).json()[0]["id"] == m.json()["id"]
    assert (
        client.patch(
            f"/api/memory/{m.json()['id']}", json={"content": "x", "expected_version": 9}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/memory/{m.json()['id']}").status_code == 204
    assert client.delete("/api/memory").json() == {"deleted": 0}

    doc = tmp_path / "notes.md"
    doc.write_text("Lighting for the horse scene should be golden hour.", encoding="utf-8")
    r = client.post("/api/knowledge/files", json={"path": str(doc)})
    assert r.status_code == 201 and r.json()["chunk_count"] == 1
    assert (
        client.post("/api/knowledge/files", json={"path": str(tmp_path / "x.png")}).status_code
        == 422
    )
    r = client.post(
        "/api/knowledge/text", json={"title": "Snippet", "text": "Pancakes need flour."}
    )
    assert r.status_code == 201
    overview = client.get("/api/knowledge").json()
    assert overview["document_count"] == 2 and "lexical" in overview["retrieval_method"]
    hits = client.get("/api/knowledge/search", params={"q": "golden hour lighting"}).json()
    assert hits[0]["document_title"] == "notes.md"
    assert client.delete(f"/api/knowledge/{r.json()['id']}").status_code == 204
    assert client.get("/api/knowledge").json()["document_count"] == 1


def test_commands_console_routes_chat_to_chat_page(client: TestClient) -> None:
    res = client.post("/api/commands", json={"text": "hello nova"}).json()
    assert res["outcome"] == "unavailable" and res["data"]["navigate"] == "/chat"
    res = client.post("/api/commands", json={"text": "/memory"}).json()
    assert res["outcome"] == "ok" and "don't remember anything yet" in res["message"]


def test_conversation_rename_and_model_unload(client: TestClient, tmp_path: Path) -> None:
    conv = client.post("/api/chat/conversations", json={"title": None}).json()
    r = client.patch(f"/api/chat/conversations/{conv['id']}", json={"title": "  Trip   plan "})
    assert r.status_code == 200 and r.json()["title"] == "Trip plan"
    assert (
        client.patch(f"/api/chat/conversations/{conv['id']}", json={"title": "  "}).status_code
        == 422
    )
    assert client.patch("/api/chat/conversations/nope", json={"title": "x"}).status_code == 404
    titles = [c["title"] for c in client.get("/api/chat/conversations").json()]
    assert "Trip plan" in titles

    _install_fake_model(client, tmp_path)
    assert (
        client.post("/api/models/unload").json()["loaded_model_id"] is None
    )  # nothing loaded: no-op
    loaded = client.post("/api/models/load").json()
    assert loaded["loaded_model_id"] is not None
    unloaded = client.post("/api/models/unload").json()
    assert unloaded["loaded_model_id"] is None
    assert any(e["action"] == "model_unloaded" for e in client.get("/api/audit").json())


def test_chat_generation_defaults_come_from_preferences(client: TestClient, tmp_path: Path) -> None:
    from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions

    _install_fake_model(client, tmp_path)
    seen: list[GenerationOptions] = []
    state = client.app.state.core  # type: ignore[attr-defined]

    def recording_generate(messages: list[ChatMessage], options: GenerationOptions):
        seen.append(options)
        yield GenerationChunk(text="ok", done=True, finish_reason="stop")

    state.runtime.generate = recording_generate
    client.patch("/api/preferences", json={"chat_max_tokens": 64, "chat_temperature": 0.2})
    conv = client.post("/api/chat/conversations", json={"title": None}).json()
    client.post(f"/api/chat/conversations/{conv['id']}/messages", json={"content": "hi"})
    assert seen[-1].max_tokens == 64 and seen[-1].temperature == 0.2
    client.post(
        f"/api/chat/conversations/{conv['id']}/messages",
        json={"content": "hi", "options": {"max_tokens": 40}},
    )
    assert seen[-1].max_tokens == 40  # explicit client options still win
    assert client.patch("/api/preferences", json={"chat_max_tokens": 1}).status_code == 422


def test_import_local_gguf_and_providers(client: TestClient, tmp_path: Path) -> None:
    providers = client.get("/api/models/providers").json()
    assert providers[0]["id"] == "llama-cpp" and providers[0]["status"] == "available"
    assert {p["status"] for p in providers[1:]} == {"planned"}

    outside = tmp_path / "downloads" / "My Model.Q4.gguf"
    outside.parent.mkdir()
    outside.write_bytes(b"g" * 4096)
    r = client.post("/api/models/import", json={"path": str(outside)})
    assert r.status_code == 422 and "right to use" in r.json()["detail"]
    r = client.post(
        "/api/models/import", json={"path": str(tmp_path / "nope.gguf"), "rights_confirmed": True}
    )
    assert r.status_code == 422 and "No such file" in r.json()["detail"]
    r = client.post("/api/models/import", json={"path": str(outside), "rights_confirmed": True})
    assert r.status_code == 201, r.text
    data = r.json()
    entry = next(m for m in data["models"] if m["source"] == "imported")
    assert entry["id"] == "local-my-model-q4" and entry["name"] == "My Model.Q4"
    assert entry["catalog"] is None and entry["license"]["id"] == "user-supplied"
    assert entry["active"] is True and data["active_model_id"] == entry["id"]
    copied = Path(entry["file_path"])
    assert copied.parent.name == "imported" and copied.exists() and outside.exists()
    assert entry["file_sha256"] is not None
    # An imported file was not checked against any publisher, and says so.
    assert entry["verification"] == "imported"
    assert "did not verify" in entry["verification_detail"]

    # Same bytes again: refused as a duplicate, not silently re-copied.
    r = client.post("/api/models/import", json={"path": str(outside), "rights_confirmed": True})
    assert r.status_code == 422 and "already installed" in r.json()["detail"]

    # A file already inside Models/ is registered in place.
    inside = tmp_path / "MyAI" / "Models" / "hand-copied.gguf"
    inside.write_bytes(b"h" * 4096)
    plan = client.get("/api/storage/cleanup").json()
    assert [c["kind"] for c in plan["candidates"]] == ["orphaned_model"]
    r = client.post("/api/models/import", json={"path": str(inside), "rights_confirmed": True})
    assert r.status_code == 201
    entry2 = next(m for m in r.json()["models"] if m["id"] == "local-hand-copied")
    assert entry2["file_path"] == str(inside)
    assert client.get("/api/storage/cleanup").json()["candidates"] == []
    assert any(e["action"] == "model_imported" for e in client.get("/api/audit").json())

    # Removing an imported model deletes the registered copy, never the original.
    client.delete(f"/api/models/{entry['id']}")
    assert not copied.exists() and outside.exists()
