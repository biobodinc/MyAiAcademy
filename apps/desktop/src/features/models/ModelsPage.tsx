import { formatBytes, type ModelEntry } from "@myai/api-client";
import { CheckCircle2, Download, Trash2, XCircle } from "lucide-react";
import { useState } from "react";

import {
  Alert,
  Button,
  Card,
  PageHeader,
  ProgressBar,
  Spinner,
  StatusPill,
} from "../../components/ui";
import {
  describeError,
  useAcceptLicense,
  useCancelDownload,
  useLoadActiveModel,
  useModels,
  useRemoveModel,
  useSetActiveModel,
  useStartDownload,
  useUnloadModel,
} from "../../lib/api";
import { LicenseDialog } from "./LicenseDialog";

export function ModelsPage() {
  const models = useModels(2000);
  const [licenseFor, setLicenseFor] = useState<ModelEntry | null>(null);
  const accept = useAcceptLicense();
  const start = useStartDownload();
  const cancel = useCancelDownload();
  const activate = useSetActiveModel();
  const remove = useRemoveModel();
  const load = useLoadActiveModel();
  const unload = useUnloadModel();

  if (models.isPending) return <Spinner label="Loading models…" />;
  if (models.isError) return <Alert tone="danger">{describeError(models.error)}</Alert>;
  const data = models.data;
  const anyError = [accept, start, cancel, activate, remove, load, unload].find((m) => m.isError);

  const beginDownload = (entry: ModelEntry) => {
    accept.mutate(entry.catalog.id, {
      onSuccess: () => {
        start.mutate(entry.catalog.id, {
          onSettled: () => {
            setLicenseFor(null);
          },
        });
      },
      onError: () => {
        setLicenseFor(null);
      },
    });
  };

  return (
    <>
      <PageHeader
        title="Models"
        subtitle="Local models run on this computer. Nothing is downloaded until you read and accept its licence."
        action={
          <div className="flex items-center gap-2">
            <StatusPill tone={data.runtime_available ? "success" : "danger"}>
              {data.runtime_available ? "Runtime ready" : "Runtime missing"}
            </StatusPill>
            {data.active_model_id && (
              <StatusPill tone={data.loaded_model_id ? "success" : "muted"}>
                {data.loaded_model_id ? `Loaded on ${data.backend ?? "cpu"}` : "Not loaded"}
              </StatusPill>
            )}
            {data.loaded_model_id && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  unload.mutate();
                }}
                disabled={unload.isPending}
                title="Free the memory the model is using; the next message loads it again."
              >
                {unload.isPending ? "Unloading…" : "Unload"}
              </Button>
            )}
          </div>
        }
      />
      {!data.runtime_available && (
        <Alert tone="danger" title="The local inference runtime is not available">
          {data.runtime_detail}
        </Alert>
      )}
      {anyError && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(anyError.error)}</Alert>
        </div>
      )}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {data.models.map((entry) => (
          <ModelCard
            key={entry.catalog.id}
            entry={entry}
            onDownload={() => {
              setLicenseFor(entry);
            }}
            onCancel={(jobId) => {
              cancel.mutate(jobId);
            }}
            onActivate={() => {
              activate.mutate(entry.catalog.id);
            }}
            onRemove={() => {
              if (window.confirm(`Delete ${entry.catalog.name} from disk?`))
                remove.mutate(entry.catalog.id);
            }}
            onLoad={() => {
              load.mutate();
            }}
            loading={load.isPending}
          />
        ))}
      </div>
      {licenseFor && (
        <LicenseDialog
          entry={licenseFor}
          busy={accept.isPending || start.isPending}
          onAccept={() => {
            beginDownload(licenseFor);
          }}
          onClose={() => {
            setLicenseFor(null);
          }}
        />
      )}
    </>
  );
}

function ModelCard({
  entry,
  onDownload,
  onCancel,
  onActivate,
  onRemove,
  onLoad,
  loading,
}: {
  entry: ModelEntry;
  onDownload: () => void;
  onCancel: (jobId: string) => void;
  onActivate: () => void;
  onRemove: () => void;
  onLoad: () => void;
  loading: boolean;
}) {
  const { catalog: c, download } = entry;
  const running = download && ["queued", "running", "verifying"].includes(download.status);
  const fitTone = entry.fit.recommended ? "success" : entry.fit.ok ? "info" : "warning";
  const fitLabel = entry.fit.recommended ? "Recommended" : entry.fit.ok ? "Fits" : "May not fit";

  return (
    <Card className={entry.active ? "border-accent" : undefined}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold">{c.name}</h3>
          <p className="text-xs text-fg-muted">
            {c.parameters_billion}B · {c.quantization} · {formatBytes(c.approx_size_bytes, 1)} ·{" "}
            {c.license.name}
          </p>
        </div>
        <StatusPill tone={fitTone}>{fitLabel}</StatusPill>
      </div>
      <p className="mt-2 text-sm text-fg-muted">{c.description}</p>
      {entry.fit.reasons.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-fg-muted">
          {entry.fit.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}

      {running && download && (
        <div className="mt-3 space-y-1">
          <ProgressBar
            value={download.bytes_done}
            max={download.bytes_total ?? Math.max(download.bytes_done, 1)}
            label={`Downloading ${c.name}`}
          />
          <div className="flex items-center justify-between text-xs text-fg-muted">
            <span>
              {download.status} · {formatBytes(download.bytes_done)} /{" "}
              {formatBytes(download.bytes_total, 1)}
            </span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                onCancel(download.id);
              }}
            >
              <XCircle className="h-3.5 w-3.5" aria-hidden /> Cancel
            </Button>
          </div>
        </div>
      )}
      {download?.status === "failed" && (
        <div className="mt-3">
          <Alert tone="danger" title="Download failed">
            {download.error} You can retry; a partial file resumes where it stopped.
          </Alert>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {entry.installed ? (
          <>
            {entry.active ? (
              <span className="inline-flex items-center gap-1 text-sm text-success">
                <CheckCircle2 className="h-4 w-4" aria-hidden /> Active
              </span>
            ) : (
              <Button size="sm" onClick={onActivate}>
                Make active
              </Button>
            )}
            {entry.active && (
              <Button size="sm" variant="secondary" onClick={onLoad} disabled={loading}>
                {loading ? "Loading…" : "Load now"}
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={onRemove}>
              <Trash2 className="h-3.5 w-3.5" aria-hidden /> Remove
            </Button>
            {entry.verified_sha256 && (
              <span
                className="ml-auto font-mono text-[10px] text-fg-muted"
                title="SHA-256 verified"
              >
                sha256 {entry.verified_sha256.slice(0, 12)}…
              </span>
            )}
          </>
        ) : (
          !running && (
            <Button size="sm" onClick={onDownload}>
              <Download className="h-4 w-4" aria-hidden />
              {download?.status === "failed" ? "Retry download" : "Download"}
            </Button>
          )
        )}
      </div>
    </Card>
  );
}
