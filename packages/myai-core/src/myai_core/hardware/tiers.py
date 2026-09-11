"""Capability tier estimation (spec §30).

Phase 1 derives a tier purely from specifications. This is a *recommendation* used to
suggest defaults; it is explicitly labelled as an estimate in the report so the UI can
say so. A short real benchmark (inference tokens/s, training step time) arrives with the
training runtime in Phase 4 and will replace ``method``.

Thresholds are deliberately conservative and reflect what actually fits in memory for
local LLM inference and LoRA fine-tuning today:

* < 4 GiB VRAM or CPU-only with < 16 GiB RAM: entry (small quantised chat models only)
* 4–8 GiB VRAM: basic (7B-class quantised inference, tiny LoRA runs)
* 8–16 GiB VRAM: capable (7B/8B LoRA training in 4-bit, 13B inference)
* 16–24 GiB VRAM: powerful (13B LoRA, image/video models with offloading)
* ≥ 24 GiB VRAM (or ≥ 2 such GPUs): workstation
"""

from __future__ import annotations

from myai_core.hardware.models import (
    AcceleratorBackend,
    CpuInfo,
    GpuInfo,
    HardwareTier,
    MemoryInfo,
    TierEstimate,
)

GiB = 1024**3


def estimate_tier(cpu: CpuInfo, memory: MemoryInfo, gpus: list[GpuInfo]) -> TierEstimate:
    rationale: list[str] = []
    accelerated = [
        g for g in gpus if g.backend is not AcceleratorBackend.NONE and g.vram_total_bytes
    ]
    ram_gib = (memory.total_bytes or 0) / GiB
    cores = cpu.physical_cores or cpu.logical_threads or 0

    if not accelerated:
        if gpus:
            rationale.append(
                "A GPU was found but no compute backend (CUDA/ROCm/Metal) was verified; "
                "treating the machine as CPU-only until a runtime is installed."
            )
        else:
            rationale.append("No GPU detected; CPU-only estimate.")
        rationale.append(f"{ram_gib:.0f} GiB RAM, {cores} CPU cores.")
        tier = HardwareTier.BASIC if ram_gib >= 32 and cores >= 8 else HardwareTier.ENTRY
        return TierEstimate(tier=tier, method="specification-estimate", rationale=rationale)

    best = max(accelerated, key=lambda g: g.vram_total_bytes or 0)
    vram_gib = (best.vram_total_bytes or 0) / GiB
    rationale.append(
        f"Best accelerator: {best.name} with {vram_gib:.1f} GiB VRAM ({best.backend})."
    )
    rationale.append(f"{ram_gib:.0f} GiB RAM, {cores} CPU cores.")

    if vram_gib >= 24 or (len(accelerated) >= 2 and vram_gib >= 16):
        tier = HardwareTier.WORKSTATION
    elif vram_gib >= 16:
        tier = HardwareTier.POWERFUL
    elif vram_gib >= 8:
        tier = HardwareTier.CAPABLE
    elif vram_gib >= 4:
        tier = HardwareTier.BASIC
    else:
        tier = HardwareTier.ENTRY

    if ram_gib and ram_gib < 16 and _ORDER.index(tier) > _ORDER.index(HardwareTier.BASIC):
        rationale.append("System RAM below 16 GiB limits dataset staging; tier reduced one step.")
        tier = _step_down(tier)
    return TierEstimate(tier=tier, method="specification-estimate", rationale=rationale)


_ORDER = list(HardwareTier)


def _step_down(tier: HardwareTier) -> HardwareTier:
    idx = _ORDER.index(tier)
    return _ORDER[max(0, idx - 1)]
