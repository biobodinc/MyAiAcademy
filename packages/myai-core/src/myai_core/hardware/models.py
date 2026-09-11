"""Pydantic schemas describing detected hardware."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from myai_core.schemas import ApiModel


class GpuVendor(StrEnum):
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    APPLE = "apple"
    UNKNOWN = "unknown"


class AcceleratorBackend(StrEnum):
    """Compute backend a GPU could be driven with. Detected, not assumed."""

    CUDA = "cuda"
    ROCM = "rocm"
    METAL = "metal"
    NONE = "none"


class CpuInfo(ApiModel):
    model_name: str | None = None
    architecture: str | None = None
    physical_cores: int | None = None
    logical_threads: int | None = None
    max_frequency_mhz: float | None = None


class MemoryInfo(ApiModel):
    total_bytes: int | None = None
    available_bytes: int | None = None


class GpuInfo(ApiModel):
    index: int
    name: str
    vendor: GpuVendor = GpuVendor.UNKNOWN
    vram_total_bytes: int | None = None
    vram_used_bytes: int | None = None
    driver_version: str | None = None
    temperature_c: float | None = None
    utilization_percent: float | None = None
    backend: AcceleratorBackend = AcceleratorBackend.NONE
    source: str = Field(description="Which probe produced this entry, e.g. 'nvidia-smi'.")


class StorageVolume(ApiModel):
    mountpoint: str
    device: str | None = None
    filesystem: str | None = None
    total_bytes: int | None = None
    free_bytes: int | None = None
    is_removable: bool | None = Field(
        default=None, description="True/False when the OS reports it; None when unknown."
    )
    label: str | None = None


class OsInfo(ApiModel):
    system: str
    release: str | None = None
    version: str | None = None
    machine: str | None = None
    python_version: str | None = None


class HardwareTier(StrEnum):
    ENTRY = "entry"
    BASIC = "basic"
    CAPABLE = "capable"
    POWERFUL = "powerful"
    WORKSTATION = "workstation"


class TierEstimate(ApiModel):
    tier: HardwareTier
    method: str = Field(description="How the tier was derived. Phase 1: 'specification-estimate'.")
    rationale: list[str] = Field(default_factory=list)
    benchmark_ran: bool = False


class HardwareReport(ApiModel):
    detected_at: datetime
    os: OsInfo
    cpu: CpuInfo
    memory: MemoryInfo
    gpus: list[GpuInfo] = Field(default_factory=list)
    volumes: list[StorageVolume] = Field(default_factory=list)
    tier: TierEstimate
    warnings: list[str] = Field(
        default_factory=list,
        description="Probes that failed or were unavailable. Shown to the user, not hidden.",
    )

    @property
    def primary_gpu(self) -> GpuInfo | None:
        if not self.gpus:
            return None
        return max(self.gpus, key=lambda g: g.vram_total_bytes or 0)
