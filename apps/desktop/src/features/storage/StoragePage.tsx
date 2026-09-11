import { formatBytes, titleCase, type CleanupCandidate } from "@myai/api-client";
import { Lock, Trash2 } from "lucide-react";
import { useState } from "react";

import { Alert, Button, Card, PageHeader, ProgressBar, Spinner } from "../../components/ui";
import {
  describeError,
  useCleanupPlan,
  useRunCleanup,
  useSetCategoryOverride,
  useStorage,
} from "../../lib/api";
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
        <CleanupCard />
      </div>
    </>
  );
}

function CleanupCard() {
  const plan = useCleanupPlan();
  const cleanup = useRunCleanup();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);

  if (plan.isPending) return <Card title="Clean up">{<Spinner label="Scanning…" />}</Card>;
  if (plan.isError) {
    return (
      <Card title="Clean up">
        <Alert tone="danger">{describeError(plan.error)}</Alert>
      </Card>
    );
  }
  const candidates = plan.data.candidates;
  const chosen = candidates.filter((c) => selected.has(c.path));
  const chosenProtected = chosen.filter((c) => c.protected);
  const chosenBytes = chosen.reduce((sum, c) => sum + c.size_bytes, 0);

  const toggle = (c: CleanupCandidate) => {
    const next = new Set(selected);
    if (next.has(c.path)) next.delete(c.path);
    else next.add(c.path);
    setSelected(next);
  };

  const run = (acknowledge: boolean) => {
    cleanup.mutate(
      { paths: chosen.map((c) => c.path), acknowledge_protected: acknowledge },
      {
        onSuccess: () => {
          setSelected(new Set());
          setConfirming(false);
        },
      },
    );
  };

  return (
    <Card title="Clean up">
      {candidates.length === 0 ? (
        <p className="text-sm text-fg-muted">
          Nothing to clean up. Interrupted downloads and untracked model files show up here.
        </p>
      ) : (
        <>
          <p className="text-sm text-fg-muted">
            {formatBytes(plan.data.reclaimable_bytes)} could be reclaimed. Items marked with a lock
            are training resources; deleting them cannot be undone.
          </p>
          <ul className="mt-3 divide-y divide-border">
            {candidates.map((c) => (
              <li key={c.path} className="flex items-start gap-3 py-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-accent"
                  aria-label={`Select ${c.path}`}
                  checked={selected.has(c.path)}
                  onChange={() => {
                    toggle(c);
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{titleCase(c.kind)}</span>
                    {c.protected && (
                      <Lock className="h-3 w-3 text-warning" aria-label="Protected" />
                    )}
                    <span className="text-fg-muted tabular-nums">{formatBytes(c.size_bytes)}</span>
                  </div>
                  <div className="truncate font-mono text-xs text-fg-muted">{c.path}</div>
                  <div className="text-xs text-fg-muted">{c.reason}</div>
                </div>
              </li>
            ))}
          </ul>
          {cleanup.isError && (
            <div className="mt-3">
              <Alert tone="danger">{describeError(cleanup.error)}</Alert>
            </div>
          )}
          {cleanup.data && cleanup.data.refused.length > 0 && (
            <div className="mt-3">
              <Alert tone="warning" title="Some files were not deleted">
                <ul className="list-disc pl-5">
                  {cleanup.data.refused.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </Alert>
            </div>
          )}
          {confirming ? (
            <Alert tone="warning" title="Delete training resources?">
              <p>
                {chosenProtected.length} of the selected files belong to protected categories
                (checkpoints, training data or memory). They cannot be recovered.
              </p>
              <div className="mt-3 flex gap-2">
                <Button
                  variant="danger"
                  onClick={() => {
                    run(true);
                  }}
                  disabled={cleanup.isPending}
                >
                  Delete anyway
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setConfirming(false);
                  }}
                >
                  Keep them
                </Button>
              </div>
            </Alert>
          ) : (
            <div className="mt-3 flex items-center gap-3">
              <Button
                variant="danger"
                disabled={chosen.length === 0 || cleanup.isPending}
                onClick={() => {
                  if (chosenProtected.length > 0) setConfirming(true);
                  else run(false);
                }}
              >
                <Trash2 className="h-4 w-4" aria-hidden />
                Delete {chosen.length > 0 ? `${chosen.length} (${formatBytes(chosenBytes)})` : ""}
              </Button>
              {cleanup.data && cleanup.data.deleted.length > 0 && (
                <span className="text-xs text-success">
                  Freed {formatBytes(cleanup.data.freed_bytes)}.
                </span>
              )}
            </div>
          )}
        </>
      )}
    </Card>
  );
}
