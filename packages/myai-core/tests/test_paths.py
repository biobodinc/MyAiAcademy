from pathlib import Path

import pytest

from myai_core.paths import ENV_DATA_DIR, resolve_app_paths


def test_override_wins_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path / "env"))
    paths = resolve_app_paths(tmp_path / "explicit")
    assert paths.data_dir == (tmp_path / "explicit").resolve()


def test_env_var_is_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path / "env"))
    assert resolve_app_paths().data_dir == (tmp_path / "env").resolve()


def test_platform_default_is_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DATA_DIR, raising=False)
    assert resolve_app_paths().data_dir.is_absolute()


def test_ensure_creates_tree_with_owner_only_perms(tmp_path: Path) -> None:
    paths = resolve_app_paths(tmp_path / "d").ensure()
    assert paths.log_dir.is_dir()
    import os

    if os.name == "posix":
        assert (paths.data_dir.stat().st_mode & 0o777) == 0o700
