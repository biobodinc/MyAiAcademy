"""Process-wide inference runtime: one loaded model, one generation at a time."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

from myai_core.hardware.models import AcceleratorBackend, HardwareReport
from myai_core.models.provider import (
    ChatMessage,
    GenerationChunk,
    GenerationOptions,
    LoadConfig,
    ModelProvider,
    ProviderStatus,
)
from myai_core.preferences.schemas import COMPUTE_PRESET_PERCENT, ComputePreset

DEFAULT_CONTEXT = 4096
GiB = 1024**3


def load_config_for(
    model_id: str,
    hardware: HardwareReport | None,
    preset: ComputePreset,
    context_length: int = DEFAULT_CONTEXT,
    *,
    cpu_utilization_percent: int | None = None,
) -> LoadConfig:
    """Translate the user's compute preset into backend knobs (spec §31).

    An explicit advanced ``cpu_utilization_percent`` wins over the preset's share.
    """
    cores = (hardware.cpu.physical_cores if hardware else None) or 4
    percent = cpu_utilization_percent or COMPUTE_PRESET_PERCENT[preset]
    threads = max(1, int(cores * percent / 100))
    gpu = hardware.primary_gpu if hardware else None
    accelerated = gpu is not None and gpu.backend is not AcceleratorBackend.NONE
    return LoadConfig(
        model_id=model_id,
        n_ctx=context_length,
        n_threads=threads,
        n_gpu_layers=-1 if accelerated else 0,
    )


def memory_budget_problem(model_size_bytes: int, ram_limit_gib: float | None) -> str | None:
    """Why loading a model of this size would break the user's RAM rule, or ``None``.

    The advanced RAM limit is a hard cap the user chose. Installed RAM is only a warning
    elsewhere (weights can be offloaded to a GPU), so it is not enforced here.
    """
    if ram_limit_gib is None or model_size_bytes <= int(ram_limit_gib * GiB):
        return None
    return (
        f"This model needs about {model_size_bytes / GiB:.1f} GB but your advanced RAM limit "
        f"is {ram_limit_gib:g} GB. Raise the limit in Settings or pick a smaller model."
    )


class InferenceRuntime:
    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider
        self._lock = threading.Lock()

    @property
    def provider(self) -> ModelProvider:
        return self._provider

    def status(self) -> ProviderStatus:
        available, detail = self._provider.availability()
        return ProviderStatus(
            provider_id=self._provider.id,
            available=available,
            detail=detail,
            loaded_model_id=self._provider.loaded_model_id(),
            backend=self._provider.backend_name(),
        )

    def ensure_loaded(self, model_path: Path, config: LoadConfig) -> None:
        with self._lock:
            if self._provider.loaded_model_id() == config.model_id:
                return
            self._provider.load(model_path, config)

    def unload(self) -> None:
        with self._lock:
            self._provider.unload()

    def generate(
        self, messages: list[ChatMessage], options: GenerationOptions
    ) -> Iterator[GenerationChunk]:
        # Hold the lock for the whole stream: llama.cpp contexts are not re-entrant.
        with self._lock:
            yield from self._provider.generate(messages, options)
