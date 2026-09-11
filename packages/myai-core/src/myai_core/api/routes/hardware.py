from __future__ import annotations

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import StateDep
from myai_core.hardware import HardwareReport, detect_hardware

router = APIRouter(tags=["hardware"])


@router.get("/hardware", response_model=HardwareReport)
async def read_hardware(
    state: StateDep,
    refresh: bool = Query(
        default=False, description="Re-run all probes instead of using the cache."
    ),
) -> HardwareReport:
    if state.hardware_cache is None or refresh:
        # Probes shell out to nvidia-smi etc.; keep the event loop free.
        state.hardware_cache = await run_in_threadpool(detect_hardware)
    return state.hardware_cache
