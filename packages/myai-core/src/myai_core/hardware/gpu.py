"""GPU probes.

Order of preference:

1. ``nvidia-smi`` – authoritative for NVIDIA (VRAM, driver, temperature, utilisation).
2. ``rocm-smi`` – AMD on Linux with ROCm installed.
3. ``torch`` – if a user-installed PyTorch can see a device, report it (Phase 2+ ships
   PyTorch as part of the local AI runtime; Phase 1 only treats it as optional).
4. OS inventory – Windows CIM / macOS ``system_profiler`` / Linux ``lspci``; these tell
   us a GPU exists but usually not usable VRAM. Entries are marked ``backend=none`` so
   the UI never claims acceleration that was not verified.
"""

from __future__ import annotations

import json
import platform
import re
from collections.abc import Callable

from myai_core.hardware._subprocess import ProbeUnavailableError, run_tool
from myai_core.hardware.models import AcceleratorBackend, GpuInfo, GpuVendor

MiB = 1024 * 1024
_WIN_ADAPTER_RAM_CAP = 0xFFF00000


def probe_gpus() -> tuple[list[GpuInfo], list[str]]:
    """Return ``(gpus, warnings)``. Vendor-specific tools win over OS inventory."""
    warnings: list[str] = []
    gpus: list[GpuInfo] = []

    for probe in (_probe_nvidia_smi, _probe_rocm_smi):
        try:
            found = probe()
        except ProbeUnavailableError:
            continue
        except Exception as exc:
            warnings.append(f"{probe.__name__}: {exc}")
            continue
        gpus.extend(found)

    if not gpus:
        try:
            gpus.extend(_probe_torch())
        except ProbeUnavailableError:
            pass
        except Exception as exc:
            warnings.append(f"torch probe: {exc}")

    if not gpus:
        inventory = _os_inventory_probe()
        if inventory is not None:
            try:
                gpus.extend(inventory())
            except ProbeUnavailableError as exc:
                warnings.append(str(exc))
            except Exception as exc:
                warnings.append(f"OS GPU inventory: {exc}")

    return gpus, warnings


# --- NVIDIA -----------------------------------------------------------------------------

_NVSMI_FIELDS = "index,name,memory.total,memory.used,driver_version,temperature.gpu,utilization.gpu"


def _probe_nvidia_smi() -> list[GpuInfo]:
    out = run_tool(["nvidia-smi", f"--query-gpu={_NVSMI_FIELDS}", "--format=csv,noheader,nounits"])
    gpus: list[GpuInfo] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        gpus.append(
            GpuInfo(
                index=_int(parts[0]) or 0,
                name=parts[1],
                vendor=GpuVendor.NVIDIA,
                vram_total_bytes=_mib_to_bytes(parts[2]),
                vram_used_bytes=_mib_to_bytes(parts[3]),
                driver_version=parts[4] or None,
                temperature_c=_float(parts[5]),
                utilization_percent=_float(parts[6]),
                backend=AcceleratorBackend.CUDA,
                source="nvidia-smi",
            )
        )
    return gpus


# --- AMD --------------------------------------------------------------------------------


def _probe_rocm_smi() -> list[GpuInfo]:
    out = run_tool(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"])
    data = json.loads(out)
    gpus: list[GpuInfo] = []
    for idx, (card, fields) in enumerate(sorted(data.items())):
        if not isinstance(fields, dict):
            continue
        name = fields.get("Card series") or fields.get("Card model") or card
        total = _int(fields.get("VRAM Total Memory (B)"))
        used = _int(fields.get("VRAM Total Used Memory (B)"))
        gpus.append(
            GpuInfo(
                index=idx,
                name=str(name),
                vendor=GpuVendor.AMD,
                vram_total_bytes=total,
                vram_used_bytes=used,
                backend=AcceleratorBackend.ROCM,
                source="rocm-smi",
            )
        )
    return gpus


# --- PyTorch (optional) -----------------------------------------------------------------


def _probe_torch() -> list[GpuInfo]:
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ProbeUnavailableError("torch not installed") from exc

    gpus: list[GpuInfo] = []
    if torch.cuda.is_available():
        backend = (
            AcceleratorBackend.ROCM
            if getattr(torch.version, "hip", None)
            else (AcceleratorBackend.CUDA)
        )
        vendor = GpuVendor.AMD if backend is AcceleratorBackend.ROCM else GpuVendor.NVIDIA
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            gpus.append(
                GpuInfo(
                    index=i,
                    name=str(props.name),
                    vendor=vendor,
                    vram_total_bytes=int(props.total_memory),
                    backend=backend,
                    source="torch",
                )
            )
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        gpus.append(
            GpuInfo(
                index=0,
                name="Apple GPU (Metal)",
                vendor=GpuVendor.APPLE,
                backend=AcceleratorBackend.METAL,
                source="torch",
            )
        )
    return gpus


# --- OS inventory fallbacks -------------------------------------------------------------


def _os_inventory_probe() -> Callable[[], list[GpuInfo]] | None:
    system = platform.system()
    if system == "Windows":
        return _probe_windows_cim
    if system == "Darwin":
        return _probe_macos_system_profiler
    if system == "Linux":
        return _probe_lspci
    return None


def _probe_windows_cim() -> list[GpuInfo]:
    script = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json -Compress"
    )
    out = run_tool(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])
    data = json.loads(out or "[]")
    entries = data if isinstance(data, list) else [data]
    gpus: list[GpuInfo] = []
    for idx, entry in enumerate(entries):
        name = str(entry.get("Name", "Unknown GPU"))
        # AdapterRAM is a 32-bit field; cards with >= 4 GiB report the capped value
        # 0xFFF00000, so anything at or above that is unknown rather than wrong.
        ram = _int(entry.get("AdapterRAM"))
        vram = ram if ram and ram < _WIN_ADAPTER_RAM_CAP else None
        gpus.append(
            GpuInfo(
                index=idx,
                name=name,
                vendor=_vendor_from_name(name),
                vram_total_bytes=vram,
                driver_version=str(entry.get("DriverVersion") or "") or None,
                source="win32-cim",
            )
        )
    return gpus


def _probe_macos_system_profiler() -> list[GpuInfo]:
    out = run_tool(["system_profiler", "SPDisplaysDataType", "-json"])
    data = json.loads(out)
    gpus: list[GpuInfo] = []
    for idx, entry in enumerate(data.get("SPDisplaysDataType", [])):
        name = str(entry.get("sppci_model") or entry.get("_name") or "Unknown GPU")
        vram = _parse_size_string(str(entry.get("spdisplays_vram") or ""))
        gpus.append(
            GpuInfo(
                index=idx,
                name=name,
                vendor=_vendor_from_name(name),
                vram_total_bytes=vram,
                source="system_profiler",
            )
        )
    return gpus


def _probe_lspci() -> list[GpuInfo]:
    out = run_tool(["lspci"])
    gpus: list[GpuInfo] = []
    for line in out.splitlines():
        if re.search(r"\b(VGA compatible controller|3D controller|Display controller)\b", line):
            name = line.split(":", 2)[-1].strip()
            gpus.append(
                GpuInfo(index=len(gpus), name=name, vendor=_vendor_from_name(name), source="lspci")
            )
    return gpus


# --- helpers ----------------------------------------------------------------------------


def _vendor_from_name(name: str) -> GpuVendor:
    lowered = name.lower()
    if "nvidia" in lowered or "geforce" in lowered or "quadro" in lowered or "rtx" in lowered:
        return GpuVendor.NVIDIA
    if "amd" in lowered or "radeon" in lowered:
        return GpuVendor.AMD
    if "intel" in lowered or "arc" in lowered.split():
        return GpuVendor.INTEL
    if "apple" in lowered:
        return GpuVendor.APPLE
    return GpuVendor.UNKNOWN


def _int(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _mib_to_bytes(value: str) -> int | None:
    mib = _int(value)
    return mib * MiB if mib is not None else None


_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|MB|KB)", re.IGNORECASE)


def _parse_size_string(text: str) -> int | None:
    m = _SIZE_RE.search(text)
    if not m:
        return None
    amount = float(m.group(1))
    unit = m.group(2).upper()
    factor = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[unit]
    return int(amount * factor)
