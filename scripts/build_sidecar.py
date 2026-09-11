"""Build the `myai-core` sidecar binary that the desktop app bundles.

Produces ``apps/desktop/src-tauri/binaries/myai-core-<target-triple>[.exe]`` using
PyInstaller. Tauri's ``bundle.externalBin`` requires exactly this naming so the right
binary ships with each platform build.

Usage:
    uv run --group bundle python scripts/build_sidecar.py [--target-triple <triple>]

The default target triple is read from ``rustc -vV`` (host).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "myai-core" / "src"
OUT_DIR = ROOT / "apps" / "desktop" / "src-tauri" / "binaries"
WORK_DIR = ROOT / "build" / "sidecar"


def host_target_triple() -> str:
    out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("could not determine host target triple from rustc -vV")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-triple", default=None)
    args = parser.parse_args()
    triple = args.target_triple or host_target_triple()
    name = f"myai-core-{triple}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    migrations = CORE_SRC / "myai_core" / "db" / "migrations"
    sep = ";" if sys.platform.startswith("win") else ":"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(OUT_DIR),
        "--workpath",
        str(WORK_DIR / "work"),
        "--specpath",
        str(WORK_DIR),
        "--paths",
        str(CORE_SRC),
        # Alembic loads migration scripts from disk at runtime.
        "--add-data",
        f"{migrations}{sep}myai_core/db/migrations",
        "--hidden-import",
        "myai_core.db.migrations.env",
        # uvicorn's optional loop/protocol implementations are imported by string name.
        "--collect-submodules",
        "uvicorn",
        "--collect-submodules",
        "alembic",
        "--collect-submodules",
        "sqlalchemy.dialects.sqlite",
        "--console",
        str(CORE_SRC / "myai_core" / "__main__.py"),
    ]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)

    produced = OUT_DIR / (name + (".exe" if sys.platform.startswith("win") else ""))
    if not produced.exists():
        raise SystemExit(f"expected {produced} to exist after PyInstaller")
    print(f"built {produced} ({produced.stat().st_size / 1024**2:.1f} MB)")
    shutil.rmtree(WORK_DIR / "work", ignore_errors=True)


if __name__ == "__main__":
    main()
