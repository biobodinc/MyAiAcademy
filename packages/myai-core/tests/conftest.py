from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.db.base import make_engine, make_session_factory
from myai_core.db.migrate import upgrade_to_head
from myai_core.paths import AppPaths

TEST_TOKEN = "test-token-not-secret"


@pytest.fixture
def test_token() -> str:
    return TEST_TOKEN


@pytest.fixture
def app_paths(tmp_path: Path) -> AppPaths:
    return AppPaths(tmp_path / "data").ensure()


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(tmp_path / "unit.sqlite3")
    upgrade_to_head(engine)
    factory = make_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


class _NoRuntime:
    """A provider whose runtime is absent: keeps route tests independent of llama_cpp."""

    id = "test-missing"

    def availability(self) -> tuple[bool, str]:
        return False, "runtime not installed in tests"

    def load(self, model_path: Path, config: object) -> None:  # pragma: no cover
        raise RuntimeError("unavailable")

    def unload(self) -> None:
        return None

    def loaded_model_id(self) -> str | None:
        return None

    def backend_name(self) -> str | None:
        return None

    def generate(self, messages: object, options: object) -> Iterator[object]:  # pragma: no cover
        raise RuntimeError("unavailable")


@pytest.fixture
def client(app_paths: AppPaths) -> Iterator[TestClient]:
    app = create_app(CoreSettings(), app_paths, token=TEST_TOKEN, provider=_NoRuntime())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": f"Bearer {TEST_TOKEN}"})
        yield c


@pytest.fixture
def anon_client(app_paths: AppPaths) -> Iterator[TestClient]:
    app = create_app(CoreSettings(), app_paths, token=TEST_TOKEN, provider=_NoRuntime())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c
