import { formatBytes, titleCase } from "@myai/api-client";
import { Lock } from "lucide-react";
import { useState } from "react";

import { Alert, Button, Card, PageHeader, ProgressBar, Spinner } from "../../components/ui";
import { describeError, useSetCategoryOverride, useStorage } from "../../lib/api";
import { pickDirectory } from "../../lib/tauri";
import { StoragePicker } from "./StoragePicker";

export function StoragePage() {
  const storage = useStorage();
  const override = useSetCategoryOverride();
  const [relocating, setRelocating] = useState(false);

  if (storage.isPending) return <Spinner label="Measuring storage…" />;
  if (storage.isError) return <Alert tone="danger">{describeError(storage.error)}</Alert>;
  const data = storage.data;

  if (!data.configured || relocating) {
    return (
      <>
        <PageHeader
          title="MyAI Storage"
          subtitle="Choose where your AI keeps models, training data and checkpoints."
        />
        <Card>
          <StoragePicker
            onConfigured={() => {
              setRelocating(false);
            }}
          />
          {relocating && (
            <Button
              variant="ghost"
              className="mt-3"
              onClick={() => {
                setRelocating(false);
              }}
            >
              Cancel
            </Button>
          )}
        </Card>
      </>
    );
  }

  const volumeUsed = (data.volume_total_bytes ?? 0) - (data.volume_free_bytes ?? 0);

  return (
    <>
      <PageHeader
        title="MyAI Storage"
        subtitle={<span className="font-mono text-xs">{data.root_path}</span>}
        action={
          <Button
            variant="secondary"
            onClick={() => {
              setRelocating(true);
            }}
          >
            Change location
          </Button>
        }
      />
      <div className="space-y-5">
        <Card title="Usage">
          <div className="mb-2 flex items-baseline justify-between text-sm">
            <span>
              MyAI uses <strong>{formatBytes(data.total_bytes_used)}</strong>
            </span>
            {data.volume_total_bytes != null && (
              <span className="text-fg-muted">
                Drive: {formatBytes(volumeUsed, 0)} / {formatBytes(data.volume_total_bytes, 0)}
              </span>
            )}
          </div>
          {data.volume_total_bytes != null && (
            <ProgressBar
              value={volumeUsed}
              max={data.volume_total_bytes}
              label="Drive usage"
              tone={volumeUsed / data.volume_total_bytes > 0.9 ? "danger" : "accent"}
            />
          )}
        </Card>
        <Card title="Categories">
          <ul className="divide-y divide-border">
            {data.categories.map((c) => (
              <li key={c.category} className="flex items-center gap-4 py-3 text-sm">
                <div className="w-32 font-medium">
                  {titleCase(c.category)}
                  {c.protected && (
                    <Lock
                      className="ml-1 inline h-3 w-3 text-fg-muted"
                      aria-label="Protected: warns before deletion"
                    />
                  )}
                </div>
                <div className="w-24 tabular-nums">{formatBytes(c.bytes_used)}</div>
                <div className="w-20 text-fg-muted tabular-nums">{c.file_count} files</div>
                <div className="min-w-0 flex-1 truncate font-mono text-xs text-fg-muted">
                  {c.path}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    void pickDirectory(`Store ${titleCase(c.category)} in…`).then((p) => {
                      if (p) override.mutate({ category: c.category, path: p });
                    })
                  }
                >
                  Move…
                </Button>
                {data.category_overrides[c.category] && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      override.mutate({ category: c.category, path: null });
                    }}
                  >
                    Reset
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {override.isError && <Alert tone="danger">{describeError(override.error)}</Alert>}
          <p className="mt-3 text-xs text-fg-muted">
            "Move" changes where new files for that category are stored. Existing files are not
            moved automatically in this version.
          </p>
        </Card>
      </div>
    </>
  );
}
