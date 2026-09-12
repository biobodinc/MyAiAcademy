"""Model catalog, hardware fit, downloader (against a local range-capable server),
model service, llama.cpp provider control flow and the inference runtime."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
from sqlalchemy.orm import Session

from myai_core.hardware.models import (
    AcceleratorBackend,
    CpuInfo,
    GpuInfo,
    HardwareReport,
    HardwareTier,
    MemoryInfo,
    OsInfo,
    TierEstimate,
)
from myai_core.hardware.volumes import probe_volumes
from myai_core.models.catalog import all_catalog_models, get_catalog_model
from myai_core.models.download import (
    HOST_ETAG,
    PINNED,
    PUBLISHER,
    UNVERIFIED,
    DownloadCancelled,
    IntegrityError,
    ModelDownloader,
    read_host_info,
)
from myai_core.models.llama_cpp_provider import LlamaCppProvider
from myai_core.models.provider import (
    ChatMessage,
    GenerationOptions,
    LoadConfig,
    ProviderError,
)
from myai_core.models.runtime import InferenceRuntime, load_config_for
from myai_core.models.service import ModelError, ModelService, hardware_fit, recommended_for
from myai_core.preferences.schemas import ComputePreset
from myai_core.storage import StorageManager

GiB = 1024**3


def _report(ram_gib: int, vram_gib: float | None, tier: HardwareTier) -> HardwareReport:
    gpus = (
        [
            GpuInfo(
                index=0,
                name="GPU",
                vram_total_bytes=int(vram_gib * GiB),
                backend=AcceleratorBackend.CUDA,
                source="t",
            )
        ]
        if vram_gib
        else []
    )
    return HardwareReport(
        detected_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        os=OsInfo(system="TestOS"),
        cpu=CpuInfo(physical_cores=8),
        memory=MemoryInfo(total_bytes=ram_gib * GiB),
        gpus=gpus,
        tier=TierEstimate(tier=tier, method="specification-estimate"),
    )


# --- catalog ------------------------------------------------------------------------------


def test_catalog_entries_are_complete_and_licensed() -> None:
    ids = [m.id for m in all_catalog_models()]
    assert len(ids) == len(set(ids))
    for m in all_catalog_models():
        assert m.license.url.startswith("https://")
        assert m.hf_filename.endswith(".gguf")
        assert m.download_url == f"https://huggingface.co/{m.hf_repo}/resolve/main/{m.hf_filename}"
        assert m.recommended_tiers


def test_hardware_fit_and_recommendation() -> None:
    small = get_catalog_model("qwen2.5-0.5b-instruct-q4km")
    big = get_catalog_model("qwen2.5-7b-instruct-q4km")
    assert small and big
    weak = _report(4, None, HardwareTier.ENTRY)
    assert hardware_fit(small, weak).ok
    fit_big = hardware_fit(big, weak)
    assert not fit_big.ok and any("RAM" in r for r in fit_big.reasons)
    strong = _report(64, 24, HardwareTier.WORKSTATION)
    assert hardware_fit(big, strong).recommended
    assert (
        recommended_for(weak).id == "smollm2-1.7b-instruct-q4km"
        or recommended_for(weak).parameters_billion <= 1.7
    )
    assert recommended_for(strong).id == "qwen2.5-7b-instruct-q4km"
    assert hardware_fit(small, None).ok


# --- downloader -------------------------------------------------------------------------


class _RangeHandler(BaseHTTPRequestHandler):
    payload = b""
    etag: str | None = None
    """The host's opaque validator. Advisory only: never fails a download."""
    linked_etag: str | None = None
    """``X-Linked-Etag``: the hash the publisher promises. May fail a download."""
    honour_range = True
    fail_after: int | None = None

    def log_message(self, *args: object) -> None:  # silence
        pass

    def _headers(self, status: int, length: int, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(length))
        if self.etag:
            self.send_header("ETag", f'"{self.etag}"')
        if self.linked_etag:
            self.send_header("X-Linked-Etag", f'"{self.linked_etag}"')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def do_HEAD(self) -> None:
        self._headers(200, len(self.payload))

    def do_GET(self) -> None:
        data = self.payload
        rng = self.headers.get("Range")
        if rng and self.honour_range:
            start = int(rng.split("=")[1].rstrip("-"))
            body = data[start:]
            self._headers(
                206, len(body), {"Content-Range": f"bytes {start}-{len(data) - 1}/{len(data)}"}
            )
        else:
            body = data
            self._headers(200, len(body))
        if self.fail_after is not None and len(body) > self.fail_after:
            self.wfile.write(body[: self.fail_after])
            self.wfile.flush()
            self.connection.close()
            return
        self.wfile.write(body)


@pytest.fixture
def file_server() -> Iterator[tuple[str, type[_RangeHandler]]]:
    class Handler(_RangeHandler):
        pass

    Handler.payload = bytes(range(256)) * 40_000  # ~10 MB
    Handler.etag = hashlib.sha256(Handler.payload).hexdigest()
    Handler.linked_etag = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/model.gguf", Handler
    server.shutdown()


def _downloader() -> ModelDownloader:
    return ModelDownloader(lambda: httpx.Client(timeout=10.0))


def test_download_verifies_against_host_declared_hash(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    dest = tmp_path / "m.gguf"
    progress: list[tuple[int, int | None]] = []
    result = _downloader().download(url, dest, on_progress=lambda d, t: progress.append((d, t)))
    assert dest.is_file() and dest.stat().st_size == len(handler.payload)
    assert result.sha256 == handler.etag
    assert result.verified_against == HOST_ETAG
    assert progress[-1] == (len(handler.payload), len(handler.payload))
    assert not dest.with_name("m.gguf.part").exists()


def test_download_resumes_partial_file(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    dest = tmp_path / "m.gguf"
    part = dest.with_name("m.gguf.part")
    part.write_bytes(handler.payload[: 3 * 1024 * 1024])
    seen: list[int] = []
    result = _downloader().download(url, dest, on_progress=lambda d, t: seen.append(d))
    assert result.sha256 == handler.etag
    assert seen[0] >= 3 * 1024 * 1024  # resumed, did not restart from zero


def test_download_restarts_when_server_ignores_range(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    handler.honour_range = False
    dest = tmp_path / "m.gguf"
    dest.with_name("m.gguf.part").write_bytes(b"garbage" * 1000)
    result = _downloader().download(url, dest)
    assert result.sha256 == handler.etag


def test_download_integrity_failure_deletes_partial(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, _ = file_server
    dest = tmp_path / "m.gguf"
    with pytest.raises(IntegrityError):
        _downloader().download(url, dest, expected_sha256="0" * 64)
    assert not dest.exists() and not dest.with_name("m.gguf.part").exists()


def test_download_truncated_stream_is_an_error(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    handler.fail_after = 1024 * 1024
    with pytest.raises(Exception):  # noqa: B017 - httpx raises its own transport error
        _downloader().download(url, tmp_path / "m.gguf")
    assert not (tmp_path / "m.gguf").exists()


def test_download_cancel(file_server: tuple[str, type[_RangeHandler]], tmp_path: Path) -> None:
    url, _ = file_server
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(DownloadCancelled):
        _downloader().download(url, tmp_path / "m.gguf", cancel=cancel)


def _response(
    headers: dict[str, str], history: list[dict[str, str]] | None = None
) -> httpx.Response:
    request = httpx.Request("HEAD", "https://cdn.example/file.gguf")
    return httpx.Response(
        200,
        headers=headers,
        request=request,
        history=[
            httpx.Response(
                302, headers=h, request=httpx.Request("HEAD", "https://origin.example/file.gguf")
            )
            for h in (history or [])
        ],
    )


def test_host_info_reads_the_publisher_hash_from_before_the_redirect() -> None:
    """Hugging Face puts X-Linked-Etag on its own response, then redirects to a CDN."""
    publisher = "a" * 64
    cdn_id = "b" * 64
    info = read_host_info(
        _response(
            {"ETag": f'"{cdn_id}"', "Content-Length": "10"},
            history=[{"X-Linked-Etag": f'"{publisher}"', "X-Linked-Size": "4096"}],
        )
    )
    assert info.publisher_sha256 == publisher
    assert info.etag_sha256 == cdn_id
    assert info.size_bytes == 4096  # the publisher's size wins over the CDN's


def test_host_info_ignores_values_that_are_not_hashes() -> None:
    info = read_host_info(_response({"ETag": '"not-a-hash"'}))
    assert info.publisher_sha256 is None and info.etag_sha256 is None
    weak = read_host_info(_response({"X-Linked-Etag": f'W/"{"c" * 64}"'}))
    assert weak.publisher_sha256 == "c" * 64


def test_download_survives_an_etag_that_is_not_a_content_hash(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    """The bug this guards against: Hugging Face's Xet CDN returns a 64-character
    hexadecimal id that is not the file's SHA-256. Treating it as one failed every
    download of a perfectly good file and deleted it."""
    url, handler = file_server
    handler.etag = "f" * 64  # looks like a hash, is not the content hash
    dest = tmp_path / "m.gguf"

    result = _downloader().download(url, dest)

    assert dest.is_file() and dest.stat().st_size == len(handler.payload)
    assert result.sha256 == hashlib.sha256(handler.payload).hexdigest()
    assert result.verified_against == UNVERIFIED and result.verified is False


def test_download_fails_when_the_publisher_hash_does_not_match(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    handler.linked_etag = "d" * 64
    dest = tmp_path / "m.gguf"

    with pytest.raises(IntegrityError) as excinfo:
        _downloader().download(url, dest)

    message = str(excinfo.value)
    assert "d" * 64 in message  # what was expected
    assert hashlib.sha256(handler.payload).hexdigest() in message  # what we got
    assert "publisher" in message
    assert not dest.exists() and not dest.with_name("m.gguf.part").exists()


def test_download_verifies_against_the_publisher_hash(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    handler.linked_etag = hashlib.sha256(handler.payload).hexdigest()
    handler.etag = "e" * 64  # a wrong ETag must not matter when a real hash exists
    result = _downloader().download(url, tmp_path / "m.gguf")
    assert result.verified_against == PUBLISHER and result.verified is True


def test_pinned_hash_outranks_the_host(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    digest = hashlib.sha256(handler.payload).hexdigest()
    result = _downloader().download(url, tmp_path / "m.gguf", expected_sha256=digest)
    assert result.verified_against == PINNED and result.verified is True

    with pytest.raises(IntegrityError, match="pinned catalog hash"):
        _downloader().download(url, tmp_path / "other.gguf", expected_sha256="9" * 64)


def test_inspect_reports_what_the_host_declares_without_downloading(
    file_server: tuple[str, type[_RangeHandler]], tmp_path: Path
) -> None:
    url, handler = file_server
    handler.linked_etag = "1" * 64
    info = _downloader().inspect(url)
    assert info.publisher_sha256 == "1" * 64
    assert info.size_bytes == len(handler.payload)
    assert not (tmp_path / "m.gguf").exists()


# --- model service ----------------------------------------------------------------------


@pytest.fixture
def storage(session: Session, tmp_path: Path) -> StorageManager:
    manager = StorageManager(session, probe_volumes)
    manager.configure_root(str(tmp_path / "MyAI"))
    return manager


def test_model_service_requires_license_then_installs(
    session: Session, storage: StorageManager, tmp_path: Path
) -> None:
    svc = ModelService(session, storage)
    model = get_catalog_model("qwen2.5-0.5b-instruct-q4km")
    assert model
    with pytest.raises(ModelError, match="Accept"):
        svc.prepare_download(model.id)
    svc.accept_license(model.id)
    _, dest, job = svc.prepare_download(model.id)
    assert dest == tmp_path / "MyAI" / "Models" / model.family / model.hf_filename
    assert job.status == "queued"
    with pytest.raises(ModelError, match="already downloading"):
        svc.prepare_download(model.id)

    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"gguf")
    svc.record_installed(model, dest, 4, "abc", PUBLISHER)
    assert svc.active_model_id() == model.id  # first install becomes active
    entries = {e.catalog.id: e for e in svc.entries(None)}
    assert entries[model.id].installed and entries[model.id].active
    assert entries[model.id].license_accepted

    svc.remove(model.id)
    assert not dest.exists()
    assert svc.active_model_id() is None
    with pytest.raises(ModelError):
        svc.set_active(model.id)


def test_download_requires_storage(session: Session) -> None:
    svc = ModelService(session, StorageManager(session, probe_volumes))
    svc.accept_license("qwen2.5-0.5b-instruct-q4km")
    with pytest.raises(ModelError, match="storage"):
        svc.prepare_download("qwen2.5-0.5b-instruct-q4km")


# --- provider / runtime -------------------------------------------------------------------


class FakeLlama:
    instances: ClassVar[list[FakeLlama]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.closed = False
        FakeLlama.instances.append(self)

    def create_chat_completion(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        assert kwargs["stream"] is True
        last = kwargs["messages"][-1]["content"]
        for word in f"echo: {last}".split(" "):
            yield {"choices": [{"delta": {"content": word + " "}, "finish_reason": None}]}
        yield {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        }

    def close(self) -> None:
        self.closed = True


def test_llama_provider_streams_and_reports_usage(tmp_path: Path) -> None:
    model_file = tmp_path / "m.gguf"
    model_file.write_bytes(b"x")
    provider = LlamaCppProvider(llama_factory=FakeLlama)
    assert provider.availability()[0]
    provider.load(model_file, LoadConfig(model_id="m", n_threads=3, n_gpu_layers=-1))
    assert provider.loaded_model_id() == "m" and provider.backend_name() == "gpu"
    assert FakeLlama.instances[-1].kwargs["n_threads"] == 3

    chunks = list(
        provider.generate([ChatMessage(role="user", content="hi there")], GenerationOptions())
    )
    assert "".join(c.text for c in chunks).strip() == "echo: hi there"
    assert chunks[-1].done and chunks[-1].finish_reason == "stop"
    assert chunks[-1].prompt_tokens == 10
    instance = FakeLlama.instances[-1]
    provider.unload()
    assert instance.closed and provider.loaded_model_id() is None
    with pytest.raises(ProviderError, match="No model"):
        list(provider.generate([], GenerationOptions()))


def test_llama_provider_missing_file_and_missing_runtime(tmp_path: Path) -> None:
    provider = LlamaCppProvider(llama_factory=FakeLlama)
    with pytest.raises(ProviderError, match="not found"):
        provider.load(tmp_path / "nope.gguf", LoadConfig(model_id="m"))


def test_runtime_reuses_loaded_model(tmp_path: Path) -> None:
    model_file = tmp_path / "m.gguf"
    model_file.write_bytes(b"x")
    provider = LlamaCppProvider(llama_factory=FakeLlama)
    runtime = InferenceRuntime(provider)
    before = len(FakeLlama.instances)
    runtime.ensure_loaded(model_file, LoadConfig(model_id="m"))
    runtime.ensure_loaded(model_file, LoadConfig(model_id="m"))
    assert len(FakeLlama.instances) == before + 1
    assert runtime.status().loaded_model_id == "m"


def test_load_config_from_preset() -> None:
    gpu = _report(32, 12, HardwareTier.CAPABLE)
    cfg = load_config_for("m", gpu, ComputePreset.BALANCED)
    assert cfg.n_threads == 4 and cfg.n_gpu_layers == -1
    cpu = _report(16, None, HardwareTier.ENTRY)
    cfg = load_config_for("m", cpu, ComputePreset.MAXIMUM)
    assert cfg.n_threads == 8 and cfg.n_gpu_layers == 0
    assert load_config_for("m", None, ComputePreset.LOW).n_threads == 1
