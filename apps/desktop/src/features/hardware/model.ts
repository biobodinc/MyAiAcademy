import type { GpuInfo, HardwareReport } from "@myai/api-client";

/** The GPU with the most VRAM, or null. Mirrors HardwareReport.primary_gpu on the service. */
export function primaryGpu(report: HardwareReport): GpuInfo | null {
  if (report.gpus.length === 0) return null;
  return (
    [...report.gpus].sort((a, b) => (b.vram_total_bytes ?? 0) - (a.vram_total_bytes ?? 0))[0] ??
    null
  );
}
