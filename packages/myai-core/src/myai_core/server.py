"""Process entry point: pick a loopback port, write the discovery file, run uvicorn."""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
from pathlib import Path

import uvicorn

from myai_core import __version__
from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.paths import AppPaths, resolve_app_paths

log = logging.getLogger("myai_core.server")


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def choose_port(host: str, preferred: int) -> int:
    if _port_is_free(host, preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def write_discovery_file(paths: AppPaths, host: str, port: int) -> None:
    """Tell local clients (desktop shell, CLI) where the service is.

    Contains no secret: the token lives in its own owner-only file. A client must read
    both, so a process that can read this file but not the token still cannot call the
    API.
    """
    payload = {
        "host": host,
        "port": port,
        "pid": os.getpid(),
        "version": __version__,
        "api_base": f"http://{host}:{port}/api",
    }
    tmp = paths.discovery_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(paths.discovery_file)


def remove_discovery_file(paths: AppPaths) -> None:
    paths.discovery_file.unlink(missing_ok=True)


READY_PREFIX = "MYAI_CORE_READY "
"""A supervising process (the desktop shell) reads this single stdout line to learn where
the service listens and where its data directory is, instead of re-implementing the
platform data-dir convention in another language."""


def ready_line(paths: AppPaths, host: str, port: int) -> str:
    payload = {
        "api_base": f"http://{host}:{port}/api",
        "base_url": f"http://{host}:{port}",
        "data_dir": str(paths.data_dir),
        "token_file": str(paths.token_file),
        "pid": os.getpid(),
        "version": __version__,
    }
    return READY_PREFIX + json.dumps(payload)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="myai-core", description="MyAI Academy local service")
    parser.add_argument(
        "--data-dir", type=Path, default=None, help="Override the app data directory."
    )
    parser.add_argument("--port", type=int, default=None, help="Preferred loopback port.")
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--version", action="version", version=f"myai-core {__version__}")
    args = parser.parse_args(argv)

    overrides: dict[str, object] = {}
    if args.port is not None:
        overrides["port"] = args.port
    if args.log_level:
        overrides["log_level"] = args.log_level
    settings = CoreSettings(**overrides)  # type: ignore[arg-type]
    paths = resolve_app_paths(args.data_dir).ensure()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    port = choose_port(settings.host, settings.port)
    app = create_app(settings, paths)
    write_discovery_file(paths, settings.host, port)
    log.info("Listening on http://%s:%d (loopback only)", settings.host, port)
    print(ready_line(paths, settings.host, port), flush=True)  # noqa: T201 - protocol, not logging
    try:
        uvicorn.run(
            app, host=settings.host, port=port, log_level=settings.log_level, access_log=False
        )
    finally:
        remove_discovery_file(paths)


if __name__ == "__main__":
    main()
