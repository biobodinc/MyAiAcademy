"""Stopping a reply must actually stop generation, persist the partial reply, and free
the runtime for the next message (a suspended generator would otherwise hold the lock)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn

from myai_core.api.app import create_app
from myai_core.chat.service import ChatService, SendMessage
from myai_core.config import CoreSettings
from myai_core.db.models import AIProfile, InstalledModel
from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions
from myai_core.paths import AppPaths
from myai_core.profile.identity import new_ai_id
from myai_core.server import choose_port


class SlowProvider:
    """Emits a word every 50 ms and records whether its generator was closed."""

    id = "slow"

    def __init__(self) -> None:
        self.closed = threading.Event()
        self.started = threading.Event()
        self._model: str | None = None

    def availability(self) -> tuple[bool, str]:
        return True, "slow test provider"

    def load(self, model_path: Path, config: object) -> None:
        self._model = getattr(config, "model_id", "m")

    def unload(self) -> None:
        self._model = None

    def loaded_model_id(self) -> str | None:
        return self._model

    def backend_name(self) -> str | None:
        return "cpu"

    def generate(
        self, messages: list[ChatMessage], options: GenerationOptions
    ) -> Iterator[GenerationChunk]:
        self.started.set()
        try:
            for i in range(200):
                time.sleep(0.05)
                yield GenerationChunk(text=f"w{i} ")
            yield GenerationChunk(done=True, finish_reason="stop")
        finally:
            self.closed.set()


def test_cancel_flag_persists_partial_reply(session, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    profile = AIProfile(ai_id=new_ai_id(), name="Nova")
    session.add(profile)
    session.flush()
    provider = SlowProvider()
    chat = ChatService(session, profile)
    conv = chat.create_conversation()
    cancel = threading.Event()
    seen = 0
    for event in chat.send(
        conv.id, SendMessage(content="go"), generate=provider.generate, model_id="m", cancel=cancel
    ):
        if event.kind == "delta":
            seen += 1
            if seen == 3:
                cancel.set()
    assert provider.closed.is_set()
    reply = chat.messages(conv.id)[-1]
    assert reply.role == "assistant" and reply.finish_reason == "cancelled"
    assert reply.content.startswith("w0 w1 w2")


def test_consumer_closing_the_stream_persists_partial_reply(session) -> None:  # type: ignore[no-untyped-def]
    profile = AIProfile(ai_id=new_ai_id(), name="Nova")
    session.add(profile)
    session.flush()
    provider = SlowProvider()
    chat = ChatService(session, profile)
    conv = chat.create_conversation()
    stream = chat.send(conv.id, SendMessage(content="go"), generate=provider.generate, model_id="m")
    next(stream)  # meta
    next(stream)  # first delta
    stream.close()
    assert provider.closed.is_set()
    assert chat.messages(conv.id)[-1].finish_reason == "cancelled"


@pytest.fixture
def live(tmp_path: Path) -> Iterator[tuple[httpx.Client, SlowProvider]]:
    paths = AppPaths(tmp_path / "data").ensure()
    provider = SlowProvider()
    port = choose_port("127.0.0.1", 41888)
    app = create_app(CoreSettings(port=port), paths, token="t", provider=provider)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    client = httpx.Client(
        base_url=f"http://127.0.0.1:{port}", headers={"Authorization": "Bearer t"}
    )
    client.post("/api/profile", json={"name": "Nova"})
    client.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
    model_file = tmp_path / "MyAI" / "Models" / "m.gguf"
    model_file.write_bytes(b"x")
    with app.state.core.session_factory() as s:
        s.add(
            InstalledModel(
                id="m",
                display_name="m",
                family="f",
                file_path=str(model_file),
                size_bytes=1,
                license_id="l",
            )
        )
        s.commit()
    client.post("/api/models/active", json={"model_id": "m"})
    try:
        yield client, provider
    finally:
        client.close()
        server.should_exit = True
        thread.join(timeout=5)


def test_client_disconnect_stops_generation_and_frees_runtime(
    live: tuple[httpx.Client, SlowProvider],
) -> None:
    client, provider = live
    conv = client.post("/api/chat/conversations", json={}).json()
    url = f"/api/chat/conversations/{conv['id']}/messages"
    deltas = 0
    with client.stream("POST", url, json={"content": "hi"}) as response:
        for line in response.iter_lines():
            if line.startswith("event: delta"):
                deltas += 1
            if deltas >= 3:
                break  # abort: leaving the context closes the connection
    assert provider.closed.wait(timeout=5), "generation kept running after the client left"

    for _ in range(50):  # the worker persists shortly after noticing the cancel flag
        msgs = client.get(url).json()
        if len(msgs) == 2:
            break
        time.sleep(0.1)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["finish_reason"] == "cancelled" and msgs[1]["content"].startswith("w0")

    # The runtime lock must be free: a second message streams normally within seconds.
    provider.closed.clear()
    started = time.monotonic()
    with client.stream("POST", url, json={"content": "again"}) as response:
        first = next(line for line in response.iter_lines() if line.startswith("event: delta"))
    assert first and time.monotonic() - started < 5
