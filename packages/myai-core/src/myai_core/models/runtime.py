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


def load_config_for(
    model_id: str,
    hardware: HardwareReport | None,
    preset: ComputePreset,
    context_length: int = DEFAULT_CONTEXT,
) -> LoadConfig:
    """Translate the user's compute preset into backend knobs (spec §31)."""
    cores = (hardware.cpu.physical_cores if hardware else None) or 4
    share = COMPUTE_PRESET_PERCENT[preset] / 100
    threads = max(1, int(cores * share))
    gpu = hardware.primary_gpu if hardware else None
    accelerated = gpu is not None and gpu.backend is not AcceleratorBackend.NONE
    return LoadConfig(
        model_id=model_id,
        n_ctx=context_length,
        n_threads=threads,
        n_gpu_layers=-1 if accelerated else 0,
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
