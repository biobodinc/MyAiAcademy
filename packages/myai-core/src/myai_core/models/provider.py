"""The ``ModelProvider`` abstraction (spec §46).

A provider turns chat messages into a stream of text. The local llama.cpp backend is the
first implementation; external API providers (OpenAI, Anthropic, Google, custom) are
optional later additions that must implement the same protocol. Nothing above this layer
knows which backend is in use.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from myai_core.schemas import ApiModel

Role = Literal["system", "user", "assistant"]


class ChatMessage(ApiModel):
    role: Role
    content: str


class GenerationOptions(ApiModel):
    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    stop: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LoadConfig:
    model_id: str
    n_ctx: int = 4096
    n_threads: int = 4
    n_gpu_layers: int = 0


@dataclass(slots=True)
class GenerationChunk:
    text: str = ""
    done: bool = False
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    extra: dict[str, object] = field(default_factory=dict)


class ProviderStatus(ApiModel):
    provider_id: str
    available: bool
    detail: str
    loaded_model_id: str | None = None
    backend: str | None = None


class ModelProvider(Protocol):
    """Contract every inference backend fulfils."""

    id: str

    def availability(self) -> tuple[bool, str]:
        """Whether the runtime can be used at all, and a human-readable reason."""

    def load(self, model_path: Path, config: LoadConfig) -> None: ...

    def unload(self) -> None: ...

    def loaded_model_id(self) -> str | None: ...

    def backend_name(self) -> str | None: ...

    def generate(
        self, messages: list[ChatMessage], options: GenerationOptions
    ) -> Iterator[GenerationChunk]: ...


class ProviderError(RuntimeError):
    """A backend failed in a way the user needs to know about (never swallowed)."""
