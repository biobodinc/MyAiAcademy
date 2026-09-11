"""Shared "get the active model ready" step used by chat, warm-up and the benchmark.

Turns the user's preferences and hardware into a ``LoadConfig``, enforces the advanced
RAM limit, and maps every failure to an HTTP status the UI already knows how to show.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from myai_core.api.state import AppState
from myai_core.models.catalog import get_catalog_model
from myai_core.models.provider import LoadConfig, ProviderError
from myai_core.models.runtime import DEFAULT_CONTEXT, load_config_for, memory_budget_problem
from myai_core.models.service import ModelService
from myai_core.preferences.schemas import Preferences


@dataclass(frozen=True, slots=True)
class PreparedModel:
    model_id: str
    path: Path
    config: LoadConfig


class ModelNotReadyError(Exception):
    """The active model cannot be used right now; ``status_code`` maps it to HTTP."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def resolve_active_model(
    state: AppState, models: ModelService, preferences: Preferences
) -> PreparedModel:
    """Resolve the active model or raise :class:`ModelNotReadyError` (usable off the API)."""
    runtime_ok, runtime_detail = state.runtime.provider.availability()
    if not runtime_ok:
        raise ModelNotReadyError(status.HTTP_503_SERVICE_UNAVAILABLE, runtime_detail)
    active = models.active_model_id()
    if active is None:
        raise ModelNotReadyError(
            status.HTTP_409_CONFLICT, "No local model is set up. Download one under Models."
        )
    installed = models.get_installed(active)
    assert installed is not None
    problem = memory_budget_problem(installed.size_bytes, preferences.ram_limit_gib)
    if problem:
        raise ModelNotReadyError(status.HTTP_409_CONFLICT, problem)
    catalog = get_catalog_model(active)
    context = min(catalog.context_length, DEFAULT_CONTEXT) if catalog else DEFAULT_CONTEXT
    config = load_config_for(
        active,
        state.hardware_cache,
        preferences.compute_preset,
        context_length=context,
        cpu_utilization_percent=preferences.cpu_utilization_percent,
    )
    return PreparedModel(model_id=active, path=Path(installed.file_path), config=config)


def prepare_active_model(
    state: AppState, models: ModelService, preferences: Preferences
) -> PreparedModel:
    """Route helper: :func:`resolve_active_model` with HTTP status codes."""
    try:
        return resolve_active_model(state, models, preferences)
    except ModelNotReadyError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


def load_prepared(state: AppState, prepared: PreparedModel) -> None:
    """Load synchronously; a backend failure becomes a 503 with the backend's message."""
    try:
        state.runtime.ensure_loaded(prepared.path, prepared.config)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
