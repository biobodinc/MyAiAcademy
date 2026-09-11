import json
import socket
from pathlib import Path

from myai_core.paths import AppPaths
from myai_core.security.local_token import load_or_create_token
from myai_core.server import (
    READY_PREFIX,
    choose_port,
    ready_line,
    remove_discovery_file,
    write_discovery_file,
)


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


def test_ready_line_is_parseable_and_secret_free(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path).ensure()
    token = load_or_create_token(paths.token_file)
    line = ready_line(paths, "127.0.0.1", 41337)
    assert line.startswith(READY_PREFIX)
    payload = json.loads(line[len(READY_PREFIX) :])
    assert payload["base_url"] == "http://127.0.0.1:41337"
    assert payload["data_dir"] == str(paths.data_dir)
    assert payload["token_file"].endswith("local-api.token")
    assert token not in line  # the shell reads the token from the file, never from stdout
