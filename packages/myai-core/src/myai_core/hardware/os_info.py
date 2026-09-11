from __future__ import annotations

import platform

from myai_core.hardware.models import OsInfo


def probe_os() -> OsInfo:
    return OsInfo(
        system=platform.system() or "unknown",
        release=platform.release() or None,
        version=platform.version() or None,
        machine=platform.machine() or None,
        python_version=platform.python_version(),
    )
