/**
 * Choose and validate a MyAI storage root. Used by onboarding and the Storage page.
 */
import { formatBytes } from "@myai/api-client";
import { FolderOpen } from "lucide-react";
import { useState } from "react";

import { Alert, Button, Input } from "../../components/ui";
import {
  describeError,
  useConfigureStorageRoot,
  useExternalCandidates,
  useStorageCheck,
} from "../../lib/api";
import { pickDirectory } from "../../lib/tauri";

export function StoragePicker({ onConfigured }: { onConfigured?: () => void }) {
  const [path, setPath] = useState("");
  const check = useStorageCheck(path);
  const external = useExternalCandidates();
  const configure = useConfigureStorageRoot();

  const browse = async () => {
    const chosen = await pickDirectory("Choose where MyAI stores models and training data");
    if (chosen) setPath(chosen.endsWith("MyAI") ? chosen : joinPath(chosen, "MyAI"));
  };

  const submit = () => {
    configure.mutate(path, { onSuccess: () => onConfigured?.() });
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          aria-label="Storage folder"
          placeholder="e.g. D:\MyAI or /Volumes/SSD/MyAI"
          value={path}
          onChange={(e) => {
            setPath(e.target.value);
          }}
          className="font-mono"
        />
        <Button variant="secondary" onClick={() => void browse()}>
          <FolderOpen className="h-4 w-4" aria-hidden />
          Browse
        </Button>
      </div>

      {external.data && external.data.length > 0 && (
        <Alert tone="info" title="External drive detected">
          <ul className="mt-1 space-y-1">
            {external.data.map((v) => (
              <li key={v.mountpoint} className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs">{v.mountpoint}</span>
                <span className="text-fg-muted">{formatBytes(v.free_bytes, 0)} free</span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setPath(joinPath(v.mountpoint, "MyAI"));
                  }}
                >
                  Use this drive
                </Button>
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {check.data && (
        <div className="space-y-2 text-sm">
          {check.data.is_existing_myai_storage && (
            <Alert tone="success">
              This folder already contains MyAI storage and will be reused.
            </Alert>
          )}
          {check.data.problems.map((p) => (
            <Alert key={p} tone={p.startsWith("Less than") ? "warning" : "danger"}>
              {p}
            </Alert>
          ))}
          {check.data.free_bytes != null && (
            <p className="text-fg-muted">
              {formatBytes(check.data.free_bytes, 0)} free of{" "}
              {formatBytes(check.data.total_bytes, 0)}
              {check.data.is_removable ? " · removable drive" : ""}
            </p>
          )}
        </div>
      )}
      {check.isError && <Alert tone="danger">{describeError(check.error)}</Alert>}
      {configure.isError && <Alert tone="danger">{describeError(configure.error)}</Alert>}

      <Button onClick={submit} disabled={!check.data?.ok || configure.isPending}>
        {configure.isPending ? "Setting up…" : "Use this folder"}
      </Button>
      <p className="text-xs text-fg-muted">
        MyAI creates a managed folder layout here (Models, Skills, Training, Checkpoints, Memory,
        Knowledge, Projects, Generated). It never repartitions or formats a drive.
      </p>
    </div>
  );
}

function joinPath(base: string, child: string): string {
  const sep = base.includes("\\") && !base.includes("/") ? "\\" : "/";
  return base.endsWith(sep) ? `${base}${child}` : `${base}${sep}${child}`;
}
