"""Hardware detection (spec §29–§30).

Every probe is best-effort: failures degrade to ``None``/``unknown`` fields plus a
human-readable warning, never an exception. The report is a *description* of the
machine; capability tiers derived from it are estimates, not guarantees.
"""

from myai_core.hardware.detect import detect_hardware
from myai_core.hardware.models import HardwareReport

__all__ = ["HardwareReport", "detect_hardware"]
