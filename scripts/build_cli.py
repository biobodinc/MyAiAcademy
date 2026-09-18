"""Build the standalone ``myai`` command.

The point of this binary is that someone can type ``myai`` in a terminal without having
Python, uv or a virtual environment — the same way ``git`` or ``claude`` work. The wheels
built alongside it are for people who do have Python and would rather ``pipx install``.

Usage:
    uv run --group bundle python scripts/build_cli.py [--out dist/bin]

This lives in a script rather than inline in the release workflow so it can be run — and
therefore proved — on a laptop, rather than only discovering it is wrong during a release.
``--collect-all llama_cpp`` is applied only when that package is actually installed: the
inference runtime is an optional extra, and a build machine without it should produce a CLI
that reports the runtime missing rather than failing to build at all.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "myai-core" / "src"
CLI_SRC = ROOT / "packages" / "myai-cli" / "src"
WORK_DIR = ROOT / "build" / "cli"

NAME = "myai"


def data_arg(source: Path, destination: str) -> str:
    separator = ";" if sys.platform.startswith("win") else ":"
    return f"{source}{separator}{destination}"


def build(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        NAME,
        "--distpath",
        str(out_dir),
        "--workpath",
        str(WORK_DIR / "work"),
        "--specpath",
        str(WORK_DIR),
        "--paths",
        str(CORE_SRC),
        "--paths",
        str(CLI_SRC),
        # Alembic reads migration scripts from disk, and skill packages are data files.
        "--add-data",
        data_arg(CORE_SRC / "myai_core" / "db" / "migrations", "myai_core/db/migrations"),
        "--add-data",
        data_arg(CORE_SRC / "myai_core" / "skills" / "packages", "myai_core/skills/packages"),
        "--hidden-import",
        "myai_core.db.migrations.env",
        # These import their own submodules by string name, so static analysis misses them.
        "--collect-submodules",
        "uvicorn",
        "--collect-submodules",
        "alembic",
        "--collect-submodules",
        "sqlalchemy.dialects.sqlite",
        "--collect-submodules",
        "pypdf",
        "--console",
    ]

    if importlib.util.find_spec("llama_cpp") is not None:
        # Ships native libraries inside its package directory, so the whole thing goes in.
        cmd += ["--collect-all", "llama_cpp"]
    else:
        print("llama_cpp is not installed; building a CLI that reports the runtime missing")

    # Build from `__main__.py`, which imports the module and then calls `entrypoint`.
    # Pointing PyInstaller at `main.py` runs it as a script instead, and its
    # `if __name__ == "__main__"` block then fires part-way down the file — see the note
    # in `myai_cli/__main__.py`.
    cmd.append(str(CLI_SRC / "myai_cli" / "__main__.py"))

    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)

    produced = out_dir / (NAME + (".exe" if sys.platform.startswith("win") else ""))
    if not produced.exists():
        raise SystemExit(f"expected {produced} to exist after PyInstaller")
    shutil.rmtree(WORK_DIR / "work", ignore_errors=True)
    return produced


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "dist" / "bin"))
    args = parser.parse_args()

    produced = build(Path(args.out))
    print(f"built {produced} ({produced.stat().st_size / 1024**2:.1f} MB)")


if __name__ == "__main__":
    main()
