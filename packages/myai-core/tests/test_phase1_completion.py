"""Metrics, benchmark, cleanup, advanced compute settings and the guide (spec §30, §31,
§63, §65, §66, §84)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from myai_core.guide import ask, topics
from myai_core.hardware import benchmark as bench
from myai_core.hardware import metrics as metrics_mod
from myai_core.hardware.benchmark import measure_memory_copy, run_benchmark
from myai_core.hardware.benchmark_store import BenchmarkStore
from myai_core.hardware.models import CpuInfo, HardwareReport, MemoryInfo, OsInfo, TierEstimate
from myai_core.hardware.tiers import HardwareTier
from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions
from myai_core.models.runtime import load_config_for, memory_budget_problem
from myai_core.preferences.schemas import ComputePreset, Preferences, PreferencesUpdate
from myai_core.preferences.service import PreferencesService
from myai_core.storage import StorageCategory, StorageManager
from myai_core.storage.cleanup import (
    CleanupKind,
    CleanupRequest,
    ProtectedDeletionError,
    delete_candidates,
    find_candidates,
)

GiB = 1024**3


# --- metrics --------------------------------------------------------------------------------


def test_metrics_never_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object, **__: object) -> object:
        raise RuntimeError("no sensors")

    monkeypatch.setattr(metrics_mod.psutil, "cpu_percent", boom)
    monkeypatch.setattr(metrics_mod.psutil, "virtual_memory", boom)
    monkeypatch.setattr(metrics_mod.psutil, "sensors_battery", boom)
    monkeypatch.setattr(metrics_mod, "_probe_nvidia_smi", boom)
    sample = metrics_mod.probe_metrics()
    assert sample.cpu_percent is None and sample.memory_used_bytes is None
    assert sample.gpu is None and sample.battery is None
    assert len(sample.warnings) == 4


def test_metrics_real_smoke() -> None:
    sample = metrics_mod.probe_metrics()
    assert sample.memory.total_bytes and sample.memory_used_bytes is not None
    assert sample.memory_percent is not None and 0 <= sample.memory_percent <= 100


def test_metrics_route(client: TestClient) -> None:
    data = client.get("/api/hardware/metrics").json()
    assert "memory_used_bytes" in data and "warnings" in data


# --- benchmark ------------------------------------------------------------------------------


def _fake_generate(
    messages: list[ChatMessage], options: GenerationOptions
) -> Iterator[GenerationChunk]:
    for _ in range(options.max_tokens):
        yield GenerationChunk(text="x")
    yield GenerationChunk(done=True, prompt_tokens=12, completion_tokens=options.max_tokens)


def test_memory_copy_is_positive() -> None:
    assert measure_memory_copy(size_bytes=4 * 1024**2, rounds=2) > 0


def test_benchmark_without_inference_says_so() -> None:
    result = run_benchmark(copy_bytes=1024**2)
    assert result.memory_copy_gbps and result.inference is None
    assert result.inference_note == "Inference was not measured."
    assert result.memory_pressure_percent is not None


def test_benchmark_measures_real_generation() -> None:
    result = run_benchmark(
        inference=lambda: (_fake_generate, "fake-model", "cpu"), copy_bytes=1024**2
    )
    assert result.inference is not None
    assert result.inference.completion_tokens == bench.INFERENCE_MAX_TOKENS
    assert result.inference.generation_tokens_per_second > 0
    assert "fake-model" in result.inference_note


def test_benchmark_reports_load_failure_instead_of_raising() -> None:
    def broken() -> tuple[object, str, str | None]:
        raise RuntimeError("no such model")

    result = run_benchmark(inference=broken, copy_bytes=1024**2)  # type: ignore[arg-type]
    assert result.inference is None and "no such model" in result.inference_note


def test_benchmark_store_roundtrip(session: Session) -> None:
    store = BenchmarkStore(session)
    assert store.latest() is None
    store.record(run_benchmark(copy_bytes=1024**2))
    latest = store.latest()
    assert latest is not None and latest.memory_copy_gbps is not None


def test_benchmark_route_attaches_to_report(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bench, "DEFAULT_COPY_BYTES", 1024**2)
    monkeypatch.setattr(
        "myai_core.api.routes.hardware.run_benchmark",
        lambda **kw: run_benchmark(**kw, copy_bytes=1024**2),
    )
    before = client.get("/api/hardware").json()
    assert before["benchmark"] is None and before["tier"]["benchmark_ran"] is False
    assert client.get("/api/hardware/benchmark").json() is None

    result = client.post("/api/hardware/benchmark").json()
    assert result["inference"] is None
    assert "runtime" in result["inference_note"]  # the test provider has no runtime
    after = client.get("/api/hardware").json()
    assert after["benchmark"]["ran_at"] == result["ran_at"]
    assert after["tier"]["benchmark_ran"] is True
    assert after["tier"]["method"] == "specification-estimate"  # tiers stay honest
    assert any(e["action"] == "benchmark_ran" for e in client.get("/api/audit").json())


# --- storage cleanup ------------------------------------------------------------------------


def _paths(root: Path) -> dict[StorageCategory, Path]:
    return {c: root / c.value.title() for c in StorageCategory}


def test_cleanup_candidates_and_protection(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    for p in paths.values():
        p.mkdir()
    tracked = paths[StorageCategory.MODELS] / "keep.gguf"
    tracked.write_bytes(b"k" * 10)
    orphan = paths[StorageCategory.MODELS] / "orphan.gguf"
    orphan.write_bytes(b"o" * 20)
    partial = paths[StorageCategory.MODELS] / "sub" / "big.gguf.part"
    partial.parent.mkdir()
    partial.write_bytes(b"p" * 30)
    protected_partial = paths[StorageCategory.CHECKPOINTS] / "ckpt.part"
    protected_partial.write_bytes(b"c" * 40)
    (paths[StorageCategory.KNOWLEDGE] / "notes.txt").write_text("user data, never a candidate")

    plan = find_candidates(paths, [str(tracked)])
    kinds = {c.path: c.kind for c in plan.candidates}
    assert kinds == {
        str(orphan): CleanupKind.ORPHANED_MODEL,
        str(partial): CleanupKind.PARTIAL_DOWNLOAD,
        str(protected_partial): CleanupKind.PARTIAL_DOWNLOAD,
    }
    assert plan.reclaimable_bytes == 90 and plan.protected_bytes == 40

    with pytest.raises(ProtectedDeletionError, match="protected"):
        delete_candidates(plan, CleanupRequest(paths=[str(protected_partial)]))
    assert protected_partial.exists()

    result = delete_candidates(
        plan,
        CleanupRequest(
            paths=[str(orphan), str(tmp_path / "outside.txt"), str(protected_partial)],
            acknowledge_protected=True,
        ),
    )
    assert result.deleted == [str(orphan), str(protected_partial)]
    assert result.freed_bytes == 60
    assert result.refused and "not in the current cleanup list" in result.refused[0]
    assert tracked.exists() and partial.exists()


def test_cleanup_ignores_symlinks(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths[StorageCategory.MODELS].mkdir()
    secret = tmp_path / "secret.gguf"
    secret.write_bytes(b"s")
    try:
        (paths[StorageCategory.MODELS] / "link.gguf").symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported here")
    plan = find_candidates(paths, [])
    assert plan.candidates == []


def test_cleanup_routes(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/api/storage/cleanup").json()["candidates"] == []  # unconfigured
    root = tmp_path / "MyAI"
    client.put("/api/storage/root", json={"root_path": str(root)})
    stale = root / "Models" / "x.gguf.part"
    stale.write_bytes(b"x" * 5)
    plan = client.get("/api/storage/cleanup").json()
    assert [c["path"] for c in plan["candidates"]] == [str(stale)]
    r = client.post("/api/storage/cleanup", json={"paths": [str(stale)]})
    assert r.status_code == 200 and r.json()["freed_bytes"] == 5 and not stale.exists()
    assert any(e["action"] == "cleanup" for e in client.get("/api/audit").json())


def test_storage_manager_category_paths(session: Session, tmp_path: Path) -> None:
    from myai_core.hardware.volumes import probe_volumes

    m = StorageManager(session, probe_volumes)
    m.configure_root(str(tmp_path / "MyAI"))
    assert set(m.category_paths()) == set(StorageCategory)


# --- advanced compute settings --------------------------------------------------------------


def test_advanced_settings_validate_and_clear(session: Session) -> None:
    svc = PreferencesService(session)
    out = svc.update(PreferencesUpdate(cpu_utilization_percent=40, ram_limit_gib=8))
    assert out.cpu_utilization_percent == 40 and out.ram_limit_gib == 8
    session.commit()
    assert svc.get().cpu_utilization_percent == 40
    cleared = svc.update(PreferencesUpdate(cpu_utilization_percent=None))
    assert cleared.cpu_utilization_percent is None and cleared.ram_limit_gib == 8
    with pytest.raises(ValueError):
        PreferencesUpdate(cpu_utilization_percent=5)
    with pytest.raises(ValueError):
        PreferencesUpdate(temperature_limit_c=120)


def test_advanced_settings_route(client: TestClient) -> None:
    assert client.get("/api/preferences").json()["ram_limit_gib"] is None
    r = client.patch("/api/preferences", json={"cpu_utilization_percent": 60})
    assert r.status_code == 200 and r.json()["cpu_utilization_percent"] == 60
    r = client.patch("/api/preferences", json={"cpu_utilization_percent": None})
    assert r.json()["cpu_utilization_percent"] is None
    assert (
        client.patch("/api/preferences", json={"gpu_utilization_percent": 101}).status_code == 422
    )


def _report(cores: int) -> HardwareReport:
    from datetime import UTC, datetime

    return HardwareReport(
        detected_at=datetime.now(tz=UTC),
        os=OsInfo(system="test"),
        cpu=CpuInfo(physical_cores=cores),
        memory=MemoryInfo(total_bytes=16 * GiB),
        tier=TierEstimate(tier=HardwareTier.ENTRY, method="specification-estimate"),
    )


def test_cpu_override_beats_preset() -> None:
    preset = load_config_for("m", _report(8), ComputePreset.MAXIMUM)
    assert preset.n_threads == 8
    capped = load_config_for("m", _report(8), ComputePreset.MAXIMUM, cpu_utilization_percent=25)
    assert capped.n_threads == 2
    assert load_config_for("m", _report(1), ComputePreset.LOW).n_threads == 1


def test_ram_limit_refuses_oversize_models() -> None:
    assert memory_budget_problem(3 * GiB, None) is None
    assert memory_budget_problem(3 * GiB, 4) is None
    problem = memory_budget_problem(5 * GiB, 4)
    assert problem and "RAM limit is 4 GB" in problem


def test_preferences_defaults_include_advanced_none() -> None:
    assert Preferences().time_limit_minutes is None


# --- guide ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("What is training?", "training"),
        ("Does more training make me universally smarter?", "training"),
        ("Where does my data go?", "privacy"),
        ("can I use it on a plane with no wifi", "offline"),
        ("how do I rename my AI", "name"),
        ("do i need an account", "account"),
        ("what does /learn do", "learning"),
    ],
)
def test_guide_matches(question: str, topic: str) -> None:
    answer = ask(question)
    assert answer.matched and answer.topic_id == topic
    assert answer.source.startswith("Built-in guide")


def test_guide_declines_unknown() -> None:
    answer = ask("what is the weather like")
    assert answer.matched is False and answer.confidence == 0.0
    assert answer.related  # offers something to try instead
    assert ask("   ").matched is False


def test_guide_topics_are_consistent() -> None:
    ids = {t.id for t in topics()}
    from myai_core.guide.topics import TOPICS

    for t in TOPICS:
        assert set(t.related) <= ids, t.id


def test_guide_routes_and_console_fallback(client: TestClient) -> None:
    assert len(client.get("/api/guide/topics").json()) >= 10
    a = client.post("/api/guide/ask", json={"question": "what is training"}).json()
    assert a["topic_id"] == "training"
    res = client.post("/api/commands", json={"text": "what is training?"}).json()
    assert res["outcome"] == "ok" and res["data"]["source"] == "guide"
    res = client.post("/api/commands", json={"text": "tell me a joke"}).json()
    assert res["outcome"] == "unavailable" and res["data"]["navigate"] == "/chat"
