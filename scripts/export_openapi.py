"""Dump the local service's OpenAPI document for TypeScript type generation.

Usage: uv run python scripts/export_openapi.py [output-path]
The generated TS types live in packages/api-client and are committed, so the frontends
build without Python installed; CI checks that the committed file is up to date.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from myai_core.api.app import create_app
from myai_core.paths import AppPaths

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "packages" / "api-client" / "openapi.json"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    app = create_app(paths=AppPaths(Path(tempfile.mkdtemp())), token="schema-export")
    document = app.openapi()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
