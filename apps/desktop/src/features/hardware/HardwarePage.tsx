import { formatBytes, type BenchmarkResult } from "@myai/api-client";
import { Gauge, RefreshCw } from "lucide-react";

import { Alert, Button, Card, PageHeader, Spinner, Stat } from "../../components/ui";
import {
  describeError,
  useBenchmark,
  useHardware,
  useRefreshHardware,
  useRunBenchmark,
} from "../../lib/api";
import { HardwareSummary } from "./HardwareSummary";

export function HardwarePage() {
  const hardware = useHardware();
  const refresh = useRefreshHardware();

  return (
    <>
      <PageHeader
        title="Hardware"
        subtitle="What your computer can offer your AI. Tiers are recommendations, not guarantees."
        action={
          <Button
            variant="secondary"
            onClick={() => {
              refresh.mutate();
            }}
            disabled={refresh.isPending}
          >
            <RefreshCw
              className={refresh.isPending ? "h-4 w-4 animate-spin" : "h-4 w-4"}
              aria-hidden
            />
            Rescan
          </Button>
        }
      />
      {hardware.isPending && <Spinner label="Scanning hardware…" />}
      {hardware.isError && <Alert tone="danger">{describeError(hardware.error)}</Alert>}
      {hardware.data && (
        <div className="space-y-5">
          <Card title="Overview">
            <HardwareSummary report={hardware.data} />
          </Card>
          <BenchmarkCard />
          <Card title="Graphics">
            {hardware.data.gpus.length === 0 ? (
              <p className="text-sm text-fg-muted">
                No GPU was detected. Chat with small models will work on the CPU; training will be
                slow.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-fg-muted uppercase">
                  <tr>
                    <th className="py-1">Name</th>
                    <th>VRAM</th>
                    <th>Backend</th>
                    <th>Driver</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {hardware.data.gpus.map((g) => (
                    <tr key={`${g.source}-${g.index}`} className="border-t border-border">
                      <td className="py-2">{g.name}</td>
                      <td>{formatBytes(g.vram_total_bytes, 0)}</td>
                      <td>{g.backend === "none" ? "not verified" : g.backend.toUpperCase()}</td>
                      <td>{g.driver_version ?? "—"}</td>
                      <td className="text-fg-muted">{g.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <Card title="Volumes">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-fg-muted uppercase">
                <tr>
                  <th className="py-1">Mount</th>
                  <th>Free</th>
                  <th>Total</th>
                  <th>Removable</th>
                </tr>
              </thead>
              <tbody>
                {hardware.data.volumes.map((v) => (
                  <tr key={v.mountpoint} className="border-t border-border">
                    <td className="py-2 font-mono text-xs">{v.mountpoint}</td>
                    <td>{formatBytes(v.free_bytes, 0)}</td>
                    <td>{formatBytes(v.total_bytes, 0)}</td>
                    <td>{v.is_removable == null ? "unknown" : v.is_removable ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <p className="text-xs text-fg-muted">
            OS: {hardware.data.os.system} {hardware.data.os.release ?? ""} · Python{" "}
            {hardware.data.os.python_version ?? "?"} · scanned{" "}
            {new Date(hardware.data.detected_at).toLocaleString()}
          </p>
        </div>
      )}
    </>
  );
}

function BenchmarkCard() {
  const benchmark = useBenchmark();
  const run = useRunBenchmark();
  const result: BenchmarkResult | null | undefined = run.data ?? benchmark.data;
  return (
    <Card
      title="Benchmark"
      action={
        <Button
          variant="secondary"
          onClick={() => {
            run.mutate();
          }}
          disabled={run.isPending}
        >
          <Gauge className={run.isPending ? "h-4 w-4 animate-pulse" : "h-4 w-4"} aria-hidden />
          {run.isPending ? "Measuring…" : result ? "Run again" : "Run benchmark"}
        </Button>
      }
    >
      <p className="text-sm text-fg-muted">
        A few seconds of measurement: single-thread memory bandwidth, memory pressure and, once a
        model is installed, real tokens per second. Measurements sit next to the tier; they do not
        change it.
      </p>
      {run.isError && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(run.error)}</Alert>
        </div>
      )}
      {result && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat
              label="Memory copy"
              value={result.memory_copy_gbps != null ? `${result.memory_copy_gbps} GB/s` : "—"}
              hint="single thread"
            />
            <Stat
              label="RAM in use"
              value={
                result.memory_pressure_percent != null ? `${result.memory_pressure_percent}%` : "—"
              }
              hint={`${formatBytes(result.memory_available_bytes, 0)} free`}
            />
            <Stat
              label="Generation"
              value={
                result.inference ? `${result.inference.generation_tokens_per_second} tok/s` : "—"
              }
              hint={result.inference ? result.inference.model_id : "not measured"}
            />
            <Stat
              label="First token"
              value={result.inference ? `${result.inference.prompt_seconds}s` : "—"}
              hint={result.inference?.backend ?? ""}
            />
          </div>
          <p className="text-xs text-fg-muted">{result.inference_note}</p>
          <ul className="list-disc pl-5 text-xs text-fg-muted">
            {result.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
          <p className="text-[10px] text-fg-muted">
            Measured {new Date(result.ran_at).toLocaleString()} in {result.duration_seconds}s.
          </p>
        </div>
      )}
    </Card>
  );
}
