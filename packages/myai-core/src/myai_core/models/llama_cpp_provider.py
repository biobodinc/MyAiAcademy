"""Local inference through llama.cpp (``llama-cpp-python``).

The binding is an optional dependency (``myai-core[local-inference]``): the core service
must start, and say so honestly, on a machine where it is missing. The ``Llama`` class is
injectable so the provider's control flow is unit-tested without a model file.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from myai_core.models.provider import (
    ChatMessage,
    GenerationChunk,
    GenerationOptions,
    LoadConfig,
    ProviderError,
)

LlamaFactory = Callable[..., Any]


class LlamaCppProvider:
    id = "llama-cpp"

    def __init__(self, llama_factory: LlamaFactory | None = None) -> None:
        self._factory = llama_factory
        self._llama: Any | None = None
        self._model_id: str | None = None
        self._backend: str | None = None

    # --- availability -------------------------------------------------------------------

    def availability(self) -> tuple[bool, str]:
        if self._factory is not None:
            return True, "injected runtime"
        try:
            module = importlib.import_module("llama_cpp")
        except ImportError:
            return (
                False,
                "The local inference runtime (llama-cpp-python) is not installed in this build.",
            )
        version = getattr(module, "__version__", "unknown")
        return True, f"llama.cpp runtime {version}"

    def _resolve_factory(self) -> LlamaFactory:
        if self._factory is not None:
            return self._factory
        try:
            module = importlib.import_module("llama_cpp")
        except ImportError as exc:
            raise ProviderError(self.availability()[1]) from exc
        factory: LlamaFactory = module.Llama
        return factory

    # --- lifecycle ----------------------------------------------------------------------

    def load(self, model_path: Path, config: LoadConfig) -> None:
        if not model_path.is_file():
            raise ProviderError(f"Model file not found: {model_path}")
        factory = self._resolve_factory()
        self.unload()
        try:
            self._llama = factory(
                model_path=str(model_path),
                n_ctx=config.n_ctx,
                n_threads=config.n_threads,
                n_gpu_layers=config.n_gpu_layers,
                verbose=False,
            )
        except Exception as exc:
            raise ProviderError(f"Could not load the model: {exc}") from exc
        self._model_id = config.model_id
        self._backend = "gpu" if config.n_gpu_layers != 0 else "cpu"

    def unload(self) -> None:
        if self._llama is not None:
            close = getattr(self._llama, "close", None)
            if callable(close):
                close()
        self._llama = None
        self._model_id = None
        self._backend = None

    def loaded_model_id(self) -> str | None:
        return self._model_id

    def backend_name(self) -> str | None:
        return self._backend

    # --- generation ---------------------------------------------------------------------

    def generate(
        self, messages: list[ChatMessage], options: GenerationOptions
    ) -> Iterator[GenerationChunk]:
        if self._llama is None:
            raise ProviderError("No model is loaded.")
        try:
            stream = self._llama.create_chat_completion(
                messages=[m.model_dump() for m in messages],
                stream=True,
                max_tokens=options.max_tokens,
                temperature=options.temperature,
                top_p=options.top_p,
                stop=options.stop or None,
            )
            for part in stream:
                choice = (part.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                text = delta.get("content") or ""
                finish = choice.get("finish_reason")
                usage = part.get("usage") or {}
                yield GenerationChunk(
                    text=text,
                    done=finish is not None,
                    finish_reason=finish,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Generation failed: {exc}") from exc
