from __future__ import annotations

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from myai_core.api.deps import AuditDep, PreferencesDep, SessionDep, StateDep, StorageDep
from myai_core.api.model_loading import prepare_active_model
from myai_core.audit.service import AuditCategory
from myai_core.hardware import HardwareReport, detect_hardware
from myai_core.hardware.benchmark import BenchmarkResult, Generate, run_benchmark
from myai_core.hardware.benchmark_store import BenchmarkStore
from myai_core.hardware.metrics import SystemMetrics, probe_metrics
from myai_core.models.service import ModelService

router = APIRouter(prefix="/hardware", tags=["hardware"])


def _with_benchmark(report: HardwareReport, session: SessionDep) -> HardwareReport:
    latest = BenchmarkStore(session).latest()
    if latest is None:
        return report
    tier = report.tier.model_copy(update={"benchmark_ran": True})
    return report.model_copy(update={"benchmark": latest, "tier": tier})


@router.get("", response_model=HardwareReport)
async def read_hardware(
    state: StateDep,
    session: SessionDep,
    refresh: bool = Query(
        default=False, description="Re-run all probes instead of using the cache."
    ),
) -> HardwareReport:
    if state.hardware_cache is None or refresh:
        # Probes shell out to nvidia-smi etc.; keep the event loop free.
        state.hardware_cache = await run_in_threadpool(detect_hardware)
    return _with_benchmark(state.hardware_cache, session)


@router.get("/metrics", response_model=SystemMetrics)
async def read_metrics(state: StateDep) -> SystemMetrics:
    """Live whole-machine utilisation for the dashboard. Cheap; safe to poll."""
    known = state.hardware_cache.gpus if state.hardware_cache else []
    return await run_in_threadpool(probe_metrics, known)


@router.get("/benchmark", response_model=BenchmarkResult | None)
def read_benchmark(session: SessionDep) -> BenchmarkResult | None:
    return BenchmarkStore(session).latest()


@router.post("/benchmark", response_model=BenchmarkResult)
async def run_hardware_benchmark(
    state: StateDep,
    session: SessionDep,
    storage: StorageDep,
    prefs: PreferencesDep,
    audit: AuditDep,
    include_inference: bool = Query(
        default=True, description="Also time the active local model, if one is installed."
    ),
) -> BenchmarkResult:
    """Run the short benchmark (spec §30) and record the result."""
    models = ModelService(session, storage)
    preferences = prefs.get()

    def inference() -> tuple[Generate, str, str | None] | str:
        runtime_ok, detail = state.runtime.provider.availability()
        if not runtime_ok:
            return f"Inference not measured: {detail}"
        if models.active_model_id() is None:
            return "Inference not measured: no local model is installed yet."
        try:
            prepared = prepare_active_model(state, models, preferences)
        except Exception as exc:
            detail_text = getattr(exc, "detail", str(exc))
            return f"Inference not measured: {detail_text}"
        state.runtime.ensure_loaded(prepared.path, prepared.config)
        backend = state.runtime.provider.backend_name()
        return state.runtime.generate, prepared.model_id, backend

    result = await run_in_threadpool(
        run_benchmark, inference=inference if include_inference else None
    )
    BenchmarkStore(session).record(result)
    audit.record(
        AuditCategory.SYSTEM,
        "benchmark_ran",
        "Hardware benchmark ran",
        {
            "memory_copy_gbps": result.memory_copy_gbps,
            "inference_measured": result.inference is not None,
        },
    )
    return result
