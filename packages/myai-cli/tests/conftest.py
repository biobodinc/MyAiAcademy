from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.paths import AppPaths
from myai_core.server import choose_port, write_discovery_file


@pytest.fixture(scope="session")
def running_service(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A real myai-core on a loopback port, so the CLI is tested end-to-end."""
    data_dir = tmp_path_factory.mktemp("data")
    paths = AppPaths(data_dir).ensure()
    port = choose_port("127.0.0.1", 41999)
    app = create_app(CoreSettings(port=port), paths)
    write_discovery_file(paths, "127.0.0.1", port)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    import time

    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield data_dir
    server.should_exit = True
    thread.join(timeout=5)
