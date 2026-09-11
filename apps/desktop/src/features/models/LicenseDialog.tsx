import { formatBytes, type ModelEntry } from "@myai/api-client";
import { ExternalLink } from "lucide-react";

import { Alert, Button } from "../../components/ui";
import { openExternal } from "../../lib/tauri";

/**
 * Licence consent (spec §69). Shown before any network request for a model. The user
 * must actively confirm; there is no default-on checkbox.
 */
export function LicenseDialog({
  entry,
  busy,
  onAccept,
  onClose,
}: {
  entry: ModelEntry;
  busy: boolean;
  onAccept: () => void;
  onClose: () => void;
}) {
  const { catalog } = entry;
  const lic = catalog.license;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="license-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
    >
      <div className="w-full max-w-lg rounded-card border border-border bg-bg-elevated p-6 shadow-card">
        <h2 id="license-title" className="text-lg font-bold">
          Before downloading {catalog.name}
        </h2>
        <dl className="mt-4 space-y-2 text-sm">
          <Row label="Source">
            https://huggingface.co/{catalog.hf_repo}
            <span className="text-fg-muted"> · {catalog.hf_filename}</span>
          </Row>
          <Row label="Size">
            about {formatBytes(catalog.approx_size_bytes, 1)} (exact size is read from the host)
          </Row>
          <Row label="Licence">
            <span className="font-medium">{lic.name}</span>
            {lic.spdx && <span className="text-fg-muted"> ({lic.spdx})</span>}
            <p className="mt-1 text-fg-muted">{lic.summary}</p>
            <p className="text-fg-muted">Commercial use: {lic.commercial_use.replace("-", " ")}</p>
            <button
              type="button"
              className="mt-1 inline-flex items-center gap-1 text-accent underline"
              onClick={() => void openExternal(lic.url)}
            >
              Read the full licence <ExternalLink className="h-3 w-3" aria-hidden />
            </button>
          </Row>
        </dl>
        {!entry.fit.ok && (
          <div className="mt-4">
            <Alert tone="warning" title="This model may not fit your hardware">
              <ul className="list-disc pl-5">
                {entry.fit.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </Alert>
          </div>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={onAccept} disabled={busy}>
            {busy ? "Starting…" : "I accept the licence — download"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[6rem_1fr] gap-2">
      <dt className="text-fg-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}
