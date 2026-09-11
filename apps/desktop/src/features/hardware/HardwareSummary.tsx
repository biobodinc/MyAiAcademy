import { formatBytes, TIER_LABELS, type HardwareReport } from "@myai/api-client";

import { Alert, Stat } from "../../components/ui";
import { primaryGpu } from "./model";

export function HardwareSummary({ report }: { report: HardwareReport }) {
  const gpu = primaryGpu(report);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="CPU"
          value={`${report.cpu.physical_cores ?? "?"} cores`}
          hint={report.cpu.model_name ?? "Unknown model"}
        />
        <Stat label="Memory" value={formatBytes(report.memory.total_bytes, 0)} hint="System RAM" />
        <Stat
          label="GPU"
          value={gpu ? formatBytes(gpu.vram_total_bytes, 0) : "None"}
          hint={
            gpu
              ? `${gpu.name} · ${gpu.backend === "none" ? "no compute backend verified" : gpu.backend.toUpperCase()}`
              : "No GPU detected"
          }
        />
        <Stat
          label="Tier"
          value={TIER_LABELS[report.tier.tier] ?? report.tier.tier}
          hint="Estimate from specifications"
        />
      </div>
      <ul className="list-disc space-y-1 pl-5 text-sm text-fg-muted">
        {report.tier.rationale.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {report.warnings.length > 0 && (
        <Alert tone="warning" title="Some probes were unavailable">
          <ul className="list-disc pl-5">
            {report.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Alert>
      )}
    </div>
  );
}
