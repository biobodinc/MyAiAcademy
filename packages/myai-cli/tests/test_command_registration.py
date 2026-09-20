"""Every command the CLI claims to have is actually registered.

This exists because of a specific way the binary broke. PyInstaller was pointed at
`main.py`, which runs it as a script: its `if __name__ == "__main__"` block fired part-way
down the file, and every command defined below that line was never registered. The shipped
`myai projects` had no subcommands at all, and nothing failed at build time to say so.

The build now targets `myai_cli.__main__`, which imports the module first. These tests guard
the other half — that the module really does register everything, and that the guard stays
at the end of the file where a later append cannot get stranded behind it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.main import get_command

from myai_cli.main import app

MAIN = Path(__file__).resolve().parents[1] / "src" / "myai_cli" / "main.py"


def command_names() -> set[str]:
    return set(get_command(app).commands)  # type: ignore[attr-defined]


def test_the_top_level_commands_are_all_there():
    assert {"chat", "serve", "status", "skills", "projects", "run"} <= command_names()


@pytest.mark.parametrize(
    ("group", "expected"),
    [
        ("projects", {"list", "new", "archive", "delete"}),
        ("security", {"erase"}),
        ("portable", set()),
    ],
)
def test_each_group_registers_its_subcommands(group: str, expected: set[str]):
    """A group that registers nothing is the shape the packaging bug produced."""
    sub = get_command(app).commands[group]  # type: ignore[attr-defined]
    names = set(sub.commands)  # type: ignore[attr-defined]
    assert names, f"{group} registered no subcommands at all"
    assert expected <= names


def test_the_main_guard_is_the_last_thing_in_the_file():
    """Anything added after it is invisible when the module is run as a script."""
    lines = [line for line in MAIN.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines[-2:] == ['if __name__ == "__main__":', "    entrypoint()"]
