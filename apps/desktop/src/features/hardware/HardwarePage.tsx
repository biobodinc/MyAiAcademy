import { formatBytes } from "@myai/api-client";
import { RefreshCw } from "lucide-react";

import { Alert, Button, Card, PageHeader, Spinner } from "../../components/ui";
import { describeError, useHardware, useRefreshHardware } from "../../lib/api";
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
