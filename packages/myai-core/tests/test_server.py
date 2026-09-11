import json
import socket
from pathlib import Path

from myai_core.paths import AppPaths
from myai_core.server import choose_port, remove_discovery_file, write_discovery_file


def test_choose_port_falls_back_when_busy() -> None:
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        busy = blocker.getsockname()[1]
        chosen = choose_port("127.0.0.1", busy)
        assert chosen != busy
        assert 1024 <= chosen <= 65535


def test_discovery_file_has_no_secret(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path).ensure()
    write_discovery_file(paths, "127.0.0.1", 41337)
    data = json.loads(paths.discovery_file.read_text())
    assert data["api_base"] == "http://127.0.0.1:41337/api"
    assert "token" not in json.dumps(data).lower()
    remove_discovery_file(paths)
    assert not paths.discovery_file.exists()
