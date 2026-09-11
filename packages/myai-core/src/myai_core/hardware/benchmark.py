"""A short, honest hardware benchmark (spec §30).

What is measured and why:

* **Memory copy bandwidth** (single thread, C-level ``memcpy`` through ``bytearray``
  slice assignment). Token generation for local LLMs is memory-bandwidth-bound, so this
  is the cheapest proxy that correlates with real inference speed on the CPU path. It is
  labelled as a single-thread figure; multi-channel systems can do better.
* **Memory pressure**: how much RAM is free right now versus installed.
* **Inference throughput**, only when the runtime and an installed model exist: prompt
  processing and generation tokens per second measured with the real model. Nothing is
  estimated from a table; if it was not measured the field is ``None`` and a note says why.

The whole thing takes a few seconds and never changes any state other than recording its
result. Tiers stay specification-based; the measurements are shown next to them.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import psutil
from pydantic import Field

from myai_core.models.provider import ChatMessage, GenerationChunk, GenerationOptions
from myai_core.schemas import ApiModel

MiB = 1024**2
DEFAULT_COPY_BYTES = 256 * MiB
COPY_ROUNDS = 3
INFERENCE_PROMPT = (
    "Reply with a short paragraph describing what a personal AI that runs on the owner's "
    "own computer can do offline."
)
INFERENCE_MAX_TOKENS = 48


class InferenceBenchmark(ApiModel):
    model_id: str
    prompt_tokens: int | None
    completion_tokens: int
    prompt_seconds: float = Field(description="Time to the first generated token.")
    generation_tokens_per_second: float
    backend: str | None


class BenchmarkResult(ApiModel):
    ran_at: datetime
    duration_seconds: float
    memory_copy_gbps: float | None = Field(
        description="Single-thread memcpy bandwidth in GB/s (decimal gigabytes)."
    )
    memory_total_bytes: int | None
    memory_available_bytes: int | None
    memory_pressure_percent: float | None = Field(
        description="Share of RAM in use at benchmark time (whole machine)."
    )
    inference: InferenceBenchmark | None
    inference_note: str
    notes: list[str]


Generate = Callable[[list[ChatMessage], GenerationOptions], Iterator[GenerationChunk]]
"""The shape of ``InferenceRuntime.generate``."""


def measure_memory_copy(size_bytes: int = DEFAULT_COPY_BYTES, rounds: int = COPY_ROUNDS) -> float:
    """Best-of-N single-thread copy bandwidth in GB/s."""
    src = bytearray(size_bytes)
    dst = bytearray(size_bytes)
    dst[:] = src  # warm-up: page in both buffers
    best = 0.0
    for _ in range(max(1, rounds)):
        start = time.perf_counter()
        dst[:] = src
        elapsed = time.perf_counter() - start
        if elapsed > 0:
            best = max(best, size_bytes / elapsed / 1e9)
    return round(best, 2)


def measure_inference(generate: Generate, model_id: str, backend: str | None) -> InferenceBenchmark:
    messages = [ChatMessage(role="user", content=INFERENCE_PROMPT)]
    options = GenerationOptions(max_tokens=INFERENCE_MAX_TOKENS, temperature=0.0)
    start = time.perf_counter()
    first_token_at: float | None = None
    completion_tokens = 0
    prompt_tokens: int | None = None
    chunk_count = 0
    for chunk in generate(messages, options):
        if chunk.text:
            chunk_count += 1
            if first_token_at is None:
                first_token_at = time.perf_counter()
        if chunk.done:
            prompt_tokens = chunk.prompt_tokens
            if chunk.completion_tokens:
                completion_tokens = chunk.completion_tokens
    end = time.perf_counter()
    if completion_tokens == 0:
        completion_tokens = chunk_count  # streaming backends emit roughly one token per chunk
    prompt_seconds = (first_token_at or end) - start
    generation_seconds = end - (first_token_at or end)
    tps = completion_tokens / generation_seconds if generation_seconds > 0 else 0.0
    return InferenceBenchmark(
        model_id=model_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt_seconds=round(prompt_seconds, 3),
        generation_tokens_per_second=round(tps, 2),
        backend=backend,
    )


def run_benchmark(
    *,
    inference: Callable[[], tuple[Generate, str, str | None] | str] | None = None,
    copy_bytes: int = DEFAULT_COPY_BYTES,
) -> BenchmarkResult:
    """Run every measurement that is possible on this machine.

    ``inference`` returns either ``(generate, model_id, backend)`` when a model can be
    exercised, or a string explaining why not. It is a callable so loading the model
    happens inside the timed benchmark only when it is actually wanted.
    """
    started = time.perf_counter()
    notes: list[str] = []

    copy_gbps: float | None
    try:
        copy_gbps = measure_memory_copy(copy_bytes)
        notes.append("Memory bandwidth is a single-thread copy; multi-channel systems do better.")
    except (MemoryError, OSError) as exc:
        copy_gbps = None
        notes.append(f"Memory copy benchmark skipped: {exc}")

    total: int | None = None
    available: int | None = None
    pressure: float | None = None
    try:
        vm = psutil.virtual_memory()
        total, available = int(vm.total), int(vm.available)
        pressure = round((total - available) / total * 100, 1) if total else None
    except Exception as exc:
        notes.append(f"Memory pressure unavailable: {exc}")

    result: InferenceBenchmark | None = None
    if inference is None:
        inference_note = "Inference was not measured."
    else:
        try:
            prepared = inference()
        except Exception as exc:
            prepared = f"Could not load the model for measurement: {exc}"
        if isinstance(prepared, str):
            inference_note = prepared
        else:
            generate, model_id, backend = prepared
            try:
                result = measure_inference(generate, model_id, backend)
                inference_note = (
                    f"Measured with {model_id}: {result.generation_tokens_per_second} tokens/s "
                    f"generation after {result.prompt_seconds}s to the first token."
                )
            except Exception as exc:
                inference_note = f"Inference measurement failed: {exc}"

    return BenchmarkResult(
        ran_at=datetime.now(tz=UTC),
        duration_seconds=round(time.perf_counter() - started, 2),
        memory_copy_gbps=copy_gbps,
        memory_total_bytes=total,
        memory_available_bytes=available,
        memory_pressure_percent=pressure,
        inference=result,
        inference_note=inference_note,
        notes=notes,
    )
