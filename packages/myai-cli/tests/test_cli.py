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
    assert code == 0
    for label in ("Internet:", "AI:", "Training:", "Privacy mode:"):
        assert label in out

    # The AI line depends on the environment: the inference runtime is an optional
    # extra, so it is absent from a plain install and present in the build that runs
    # the real-runtime tests. Both readings must explain themselves, and neither may
    # claim the AI is ready. Asserting on the JSON avoids the panel's line wrapping.
    code, raw = _run("status", "--json", data_dir=running_service)
    assert code == 0
    status = json.loads(raw)
    detail = status["ai_detail"].lower()
    if status["ai"] == "unavailable":
        assert "runtime" in detail
    else:
        assert status["ai"] == "not_configured" and "model" in detail
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
    assert "cannot be learned yet" in out  # creative skills have no benchmark package


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


def test_models_import_and_providers(running_service: Path, tmp_path: Path) -> None:
    code, out = _run("models", "providers", data_dir=running_service)
    assert code == 0 and "planned" in out
    gguf = tmp_path / "mine.gguf"
    gguf.write_bytes(b"m" * 4096)
    code, out = _run("models", "import", str(gguf), data_dir=running_service)
    assert code == 1 and "confirm-rights" in out
    code, out = _run("models", "import", str(gguf), "--confirm-rights", data_dir=running_service)
    assert code == 0 and "local-mine" in out
    code, out = _run("models", "list", data_dir=running_service)
    assert code == 0 and "(imported)" in out
    code, out = _run("models", "show", "local-mine", data_dir=running_service)
    assert code == 0 and "Your own licence" in out


def test_learn_is_honest_without_a_model(running_service: Path) -> None:
    _run("profile", "create", "--name", "Nova", data_dir=running_service)  # no-op if it exists
    code, out = _run("learn", "science", "--yes", data_dir=running_service)  # locked by the tree
    assert code == 1 and "cannot be learned yet" in out and "Research" in out
    code, out = _run("learn", "video", "--yes", data_dir=running_service)
    assert code == 1 and "no measurable benchmark" in out
    code, out = _run("history", data_dir=running_service)
    assert code == 0 and "No benchmark runs yet" in out
    code, out = _run("jobs", "list", data_dir=running_service)
    assert code == 0
    code, out = _run("jobs", "stop", data_dir=running_service)
    assert code == 1 and "No job" in out


def test_train_is_honest_about_what_it_cannot_do_yet(running_service: Path) -> None:
    _run("profile", "create", "--name", "Nova", data_dir=running_service)  # no-op if it exists
    code, out = _run("train", "science", "--yes", data_dir=running_service)
    assert code == 1 and "cannot be trained yet" in out
    assert "Learn Science first" in out
    code, out = _run("train", "video", "--yes", data_dir=running_service)
    assert code == 1 and "cannot be trained yet" in out
    code, out = _run("training", "science", data_dir=running_service)
    assert code == 0 and "No training runs" in out
    # A duration that is not a duration is refused rather than silently defaulted.
    code, out = _run("train", "science", "--duration", "soon", data_dir=running_service)
    assert code == 2 and "Could not read a duration" in out
