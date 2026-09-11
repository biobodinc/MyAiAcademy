from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from myai_cli.main import app

runner = CliRunner()


def _run(*args: str, data_dir: Path) -> tuple[int, str]:
    result = runner.invoke(app, [*args, "--data-dir", str(data_dir)])
    return result.exit_code, result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0 and "myai 0." in result.output


def test_status_when_service_missing(tmp_path: Path) -> None:
    code, _ = _run("status", data_dir=tmp_path / "nothing")
    assert code == 2


def test_status_and_hardware(running_service: Path) -> None:
    code, out = _run("status", data_dir=running_service)
    assert code == 0 and "AI:" in out and "model" in out.lower()
    code, out = _run("hardware", "--json", data_dir=running_service)
    assert code == 0
    assert json.loads(out)["tier"]["method"] == "specification-estimate"


def test_profile_and_skills_flow(running_service: Path) -> None:
    code, out = _run("profile", "show", data_dir=running_service)
    assert code == 0 and "No AI yet" in out
    code, out = _run(
        "profile",
        "create",
        "--name",
        "Nova",
        "--owner",
        "Alex",
        "--interest",
        "video",
        data_dir=running_service,
    )
    assert code == 0 and "Created Nova" in out
    code, out = _run("profile", "set", "--personality", "curious", data_dir=running_service)
    assert code == 0 and "v2" in out
    code, out = _run("skills", data_dir=running_service)
    assert code == 0 and "overall level 0" in out


def test_run_command_shows_mapping(running_service: Path) -> None:
    code, out = _run("run", "teach yourself video", data_dir=running_service)
    assert code == 0
    assert "/learn video" in out and "natural language" in out
    assert "not available yet" in out


def test_storage_flow(running_service: Path, tmp_path: Path) -> None:
    root = tmp_path / "MyAI"
    code, out = _run("storage", "check", str(root), data_dir=running_service)
    assert code == 0 and "OK" in out
    code, out = _run("storage", "set-root", str(root), data_dir=running_service)
    assert code == 0
    code, out = _run("storage", "show", data_dir=running_service)
    assert code == 0 and "Checkpoints" in out
    code, out = _run("audit", data_dir=running_service)
    assert code == 0 and "storage location set" in out


def test_ask_and_settings(running_service: Path) -> None:
    code, out = _run("ask", "what is training?", data_dir=running_service)
    assert code == 0 and "Training" in out and "Built-in guide" in out
    code, out = _run(
        "settings", "set", "--mode", "advanced", "--cpu", "50", data_dir=running_service
    )
    assert code == 0 and "Mode advanced" in out
    code, out = _run("settings", "show", data_dir=running_service)
    assert code == 0 and "50" in out
    code, out = _run("settings", "set", "--cpu", "0", data_dir=running_service)
    assert code == 0
    code, out = _run("settings", "show", "--json", data_dir=running_service)
    assert json.loads(out)["cpu_utilization_percent"] is None


def test_storage_cleanup_and_benchmark(running_service: Path, tmp_path: Path) -> None:
    root = tmp_path / "MyAI-cleanup"
    _run("storage", "set-root", str(root), data_dir=running_service)
    stale = root / "Models" / "half.gguf.part"
    stale.write_bytes(b"x" * 10)
    code, out = _run("storage", "cleanup", data_dir=running_service)
    assert code == 0 and "partial download" in out and stale.exists()
    code, out = _run("storage", "cleanup", "--delete", data_dir=running_service)
    assert code == 0 and "Deleted 1" in out and not stale.exists()
    code, out = _run("hardware", "--benchmark", data_dir=running_service)
    assert code == 0 and "Benchmark (" in out


def test_models_unload_is_safe_when_nothing_loaded(running_service: Path) -> None:
    code, out = _run("models", "unload", data_dir=running_service)
    assert code == 0 and "unloaded" in out
