"""Tiny helper to run external probe tools with a timeout and no shell."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence

PROBE_TIMEOUT_S = 5.0


class ProbeUnavailableError(Exception):
    """The tool is not installed or did not respond usefully."""


def run_tool(argv: Sequence[str], *, timeout: float = PROBE_TIMEOUT_S) -> str:
    """Run ``argv[0]`` if it exists on PATH and return stdout. Never uses a shell."""
    executable = shutil.which(argv[0])
    if executable is None:
        raise ProbeUnavailableError(f"{argv[0]} not found on PATH")
    try:
        completed = subprocess.run(
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeUnavailableError(f"{argv[0]} failed: {exc}") from exc
    if completed.returncode != 0:
        raise ProbeUnavailableError(f"{argv[0]} exited with {completed.returncode}")
    return completed.stdout
