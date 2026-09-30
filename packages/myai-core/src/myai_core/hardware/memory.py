# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Biobodinc. Part of MyAI Academy.
from __future__ import annotations

import psutil

from myai_core.hardware.models import MemoryInfo


def probe_memory() -> MemoryInfo:
    vm = psutil.virtual_memory()
    return MemoryInfo(total_bytes=int(vm.total), available_bytes=int(vm.available))
