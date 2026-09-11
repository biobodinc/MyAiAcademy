from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from myai_core.hardware.models import StorageVolume
from myai_core.storage import STORAGE_CATEGORIES, StorageCategory, StorageManager
from myai_core.storage.layout import ROOT_MARKER_FILE
from myai_core.storage.manager import StorageError


def _volumes(tmp_path: Path, free: int = 100 * 1024**3, removable: bool | None = False):
    def probe() -> tuple[list[StorageVolume], list[str]]:
        return (
            [
                StorageVolume(
                    mountpoint=str(tmp_path),
                    total_bytes=200 * 1024**3,
                    free_bytes=free,
                    is_removable=removable,
                ),
                StorageVolume(mountpoint="/", total_bytes=1, free_bytes=1, is_removable=False),
            ],
            [],
        )

    return probe


@pytest.fixture
def manager(session: Session, tmp_path: Path) -> StorageManager:
    return StorageManager(session, _volumes(tmp_path))


def test_unconfigured_overview(manager: StorageManager) -> None:
    ov = manager.overview()
    assert ov.configured is False
    assert ov.categories == []


def test_check_rejects_relative_and_files(manager: StorageManager, tmp_path: Path) -> None:
    assert not manager.check_location("relative/path").ok
    f = tmp_path / "file.txt"
    f.write_text("x")
    assert "not a directory" in " ".join(manager.check_location(str(f)).problems)


def test_check_rejects_non_empty_foreign_dir(manager: StorageManager, tmp_path: Path) -> None:
    d = tmp_path / "docs"
    d.mkdir()
    (d / "thesis.pdf").write_text("x")
    check = manager.check_location(str(d))
    assert not check.ok
    assert check.is_existing_myai_storage is False


def test_check_recognises_existing_storage(manager: StorageManager, tmp_path: Path) -> None:
    root = tmp_path / "MyAI"
    manager.configure_root(str(root))
    check = manager.check_location(str(root))
    assert check.ok and check.is_existing_myai_storage


def test_low_space_is_warning_not_blocker(session: Session, tmp_path: Path) -> None:
    m = StorageManager(session, _volumes(tmp_path, free=5 * 1024**3))
    check = m.check_location(str(tmp_path / "new"))
    assert check.ok
    assert any("Less than 20 GB" in p for p in check.problems)


def test_configure_creates_layout_and_marker(manager: StorageManager, tmp_path: Path) -> None:
    root = tmp_path / "MyAI"
    manager.configure_root(str(root))
    for folder in STORAGE_CATEGORIES.values():
        assert (root / folder).is_dir()
    assert (root / ROOT_MARKER_FILE).is_file()
    assert manager.category_path(StorageCategory.MODELS) == root / "Models"


def test_configure_rejects_bad_location(manager: StorageManager) -> None:
    with pytest.raises(StorageError):
        manager.configure_root("not/absolute")


def test_usage_accounting(manager: StorageManager, tmp_path: Path) -> None:
    root = tmp_path / "MyAI"
    manager.configure_root(str(root))
    (root / "Models" / "a.bin").write_bytes(b"x" * 1000)
    sub = root / "Models" / "nested"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"y" * 500)
    ov = manager.overview()
    models = next(c for c in ov.categories if c.category is StorageCategory.MODELS)
    assert models.bytes_used == 1500
    assert models.file_count == 2
    assert ov.total_bytes_used == 1500
    assert ov.volume_free_bytes == 100 * 1024**3
    checkpoints = next(c for c in ov.categories if c.category is StorageCategory.CHECKPOINTS)
    assert checkpoints.protected is True


def test_category_override(manager: StorageManager, tmp_path: Path) -> None:
    manager.configure_root(str(tmp_path / "MyAI"))
    external = tmp_path / "ssd" / "MyAI-Models"
    manager.set_category_override(StorageCategory.MODELS, str(external))
    assert manager.category_path(StorageCategory.MODELS) == external
    assert external.is_dir()
    manager.set_category_override(StorageCategory.MODELS, None)
    assert manager.category_path(StorageCategory.MODELS) == tmp_path / "MyAI" / "Models"
    with pytest.raises(StorageError):
        manager.set_category_override(StorageCategory.MODELS, "relative")


def test_external_candidates(session: Session, tmp_path: Path) -> None:
    m = StorageManager(session, _volumes(tmp_path, removable=True))
    assert [v.mountpoint for v in m.detect_external_candidates()] == [str(tmp_path)]
