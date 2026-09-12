"""End-to-end through the *real* llama.cpp runtime with a synthetic model.

Skipped when ``llama_cpp`` (the optional ``local-inference`` extra) or the ``gguf``
writer is not installed. The model's output is random; these tests prove that loading,
chat templating, streaming, the benchmark's inference measurement and unloading work
with the actual backend, not a fake.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("llama_cpp")
pytest.importorskip("gguf")

from tests_conftest_shim import build_tiny_gguf

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.db.models import InstalledModel
from myai_core.models.llama_cpp_provider import LlamaCppProvider
from myai_core.models.provider import ChatMessage, GenerationOptions, LoadConfig
from myai_core.paths import AppPaths


@pytest.fixture(scope="module")
def tiny_model(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_tiny_gguf(tmp_path_factory.mktemp("model") / "tiny.gguf")


def test_provider_loads_and_streams(tiny_model: Path) -> None:
    provider = LlamaCppProvider()
    ok, detail = provider.availability()
    assert ok and "llama.cpp" in detail
    provider.load(tiny_model, LoadConfig(model_id="tiny", n_ctx=128, n_threads=2))
    assert provider.loaded_model_id() == "tiny" and provider.backend_name() == "cpu"
    chunks = list(
        provider.generate(
            [ChatMessage(role="user", content="hello world")],
            GenerationOptions(max_tokens=8, temperature=0.0),
        )
    )
    assert any(c.text for c in chunks)
    assert chunks[-1].done and chunks[-1].finish_reason in {"length", "stop"}
    provider.unload()
    assert provider.loaded_model_id() is None


@pytest.fixture
def client(app_paths: AppPaths, tmp_path: Path, tiny_model: Path) -> Iterator[TestClient]:
    app = create_app(CoreSettings(), app_paths, token="t", provider=LlamaCppProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": "Bearer t"})
        c.post("/api/profile", json={"name": "Nova", "owner_name": "Alex"})
        c.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
        dest = tmp_path / "MyAI" / "Models" / "tiny" / "tiny.gguf"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(tiny_model.read_bytes())
        with app.state.core.session_factory() as session:
            session.add(
                InstalledModel(
                    id="tiny",
                    display_name="Tiny test model",
                    family="tiny",
                    file_path=str(dest),
                    size_bytes=dest.stat().st_size,
                    sha256=None,
                    license_id="apache-2.0",
                )
            )
            session.commit()
        c.post("/api/models/active", json={"model_id": "tiny"})
        yield c


def test_api_chat_benchmark_and_unload_with_real_runtime(client: TestClient) -> None:
    status = client.get("/api/status").json()
    assert status["ai"] == "available" and status["active_model_id"] == "tiny"

    loaded = client.post("/api/models/load").json()
    assert loaded["loaded_model_id"] == "tiny" and loaded["backend"] == "cpu"

    client.patch("/api/preferences", json={"chat_max_tokens": 32})
    conv = client.post("/api/chat/conversations", json={}).json()
    r = client.post(f"/api/chat/conversations/{conv['id']}/messages", json={"content": "hello"})
    assert r.status_code == 200
    kinds = [line[7:] for line in r.text.splitlines() if line.startswith("event: ")]
    assert kinds[0] == "meta" and "delta" in kinds and kinds[-1] == "done"
    done = json.loads(r.text.split("event: done\ndata: ")[1].split("\n")[0])
    assert done["finish_reason"] in {"length", "stop"} and done["completion_tokens"] >= 1
    msgs = client.get(f"/api/chat/conversations/{conv['id']}/messages").json()
    assert msgs[-1]["role"] == "assistant" and msgs[-1]["model_id"] == "tiny"

    bench = client.post("/api/hardware/benchmark").json()
    assert bench["inference"] is not None
    assert bench["inference"]["model_id"] == "tiny"
    assert bench["inference"]["generation_tokens_per_second"] > 0

    assert client.post("/api/models/unload").json()["loaded_model_id"] is None


def test_learn_science_with_real_runtime(client: TestClient) -> None:
    """The whole learning pipeline against the real backend. The tiny model answers
    nonsense, so the only assertions are that the benchmark ran and set a level."""
    job = client.post("/api/skills/conversation/learn").json()
    state = client.app.state.core  # type: ignore[attr-defined]
    state.jobs.wait(job["id"], 120)
    job = client.get(f"/api/jobs/{job['id']}").json()
    assert job["status"] == "completed", job
    assert job["progress_done"] == job["progress_total"] == 12
    skill = client.get("/api/skills/conversation").json()
    assert skill["learned"] and 1 <= skill["level"] <= 100
    history = client.get("/api/skills/conversation/evaluations").json()
    assert history[0]["model_id"] == "tiny" and len(history[0]["task_results"]) == 12
