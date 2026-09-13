/**
 * Portable AI (spec §23-§27, §77): carry this AI, or keep it as a backup.
 *
 * Writing a package and restoring one are wildly different in consequence, so they do not
 * look alike here. Writing is one button. Restoring is a preview you have to read, a list of
 * what will not work on this machine, and a phrase you have to type — the same shape the
 * Privacy Center uses for erasing, because it has the same finality.
 */
import type { CapabilityRead, ImportPreviewRead, PackageWritten } from "@myai/api-client";
import { Archive, FileDown, FileUp, ShieldCheck, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { Alert, Button, Card, PageHeader, Row, StatusPill } from "../../components/ui";
import {
  describeError,
  usePreviewPackage,
  useRestorePackage,
  useWritePackage,
} from "../../lib/api";

const CONFIRMATION = "REPLACE MY AI";

export function PortablePage() {
  return (
    <>
      <PageHeader
        title="Portable AI"
        subtitle="Carry this AI to another computer, or keep it as a backup you can open again."
      />
      <div className="space-y-5">
        <WriteCard />
        <RestoreCard />
      </div>
    </>
  );
}

function WriteCard() {
  const write = useWritePackage();
  const [destination, setDestination] = useState("");
  const [password, setPassword] = useState("");
  const [written, setWritten] = useState<PackageWritten | null>(null);

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <FileDown className="h-4 w-4" aria-hidden /> Write a package
        </span>
      }
    >
      <p className="text-sm text-fg-muted">
        Identity, memories, conversations, skills and settings. Model files are not copied — they
        are large and their licences usually forbid passing them on, so the package records what to
        download again instead.
      </p>

      <div className="mt-4 space-y-3">
        <label className="block text-sm">
          <span className="text-fg-muted">Where to write it</span>
          <input
            value={destination}
            onChange={(e) => {
              setDestination(e.target.value);
            }}
            placeholder="Leave blank to use this installation's folder"
            className="mt-1 w-full rounded-lg border border-border bg-transparent p-2 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="text-fg-muted">Password (optional, but see below)</span>
          <input
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
            autoComplete="new-password"
            className="mt-1 w-full rounded-lg border border-border bg-transparent p-2 text-sm"
          />
        </label>
        {password === "" && (
          <Alert tone="warning">
            Without a password, anyone who finds the file can read everything in it: your memories,
            your conversations, your AI&apos;s name. Set one if it is going on a drive you carry or
            leave anywhere.
          </Alert>
        )}
        <Button
          onClick={() => {
            write.mutate(
              { destination, password },
              {
                onSuccess: (result) => {
                  setWritten(result);
                },
              },
            );
          }}
          disabled={write.isPending}
        >
          <Archive className="h-4 w-4" /> {write.isPending ? "Writing…" : "Write package"}
        </Button>
      </div>

      {write.isError && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(write.error)}</Alert>
        </div>
      )}
      {written && (
        <div className="mt-4 space-y-2 rounded-lg border border-border p-3 text-sm">
          <Row label="Written to">
            <span className="font-mono text-xs break-all">{written.path}</span>
          </Row>
          <Row label="Size">{(written.size_bytes / 1_000_000).toFixed(1)} MB</Row>
          <Row label="Locked">
            <StatusPill tone={written.encrypted ? "success" : "warning"}>
              {written.encrypted ? "with a password" : "no — readable by anyone"}
            </StatusPill>
          </Row>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-fg-muted">
            {written.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function RestoreCard() {
  const preview = usePreviewPackage();
  const restore = useRestorePackage();
  const [path, setPath] = useState("");
  const [password, setPassword] = useState("");
  const [typed, setTyped] = useState("");
  const [found, setFound] = useState<ImportPreviewRead | null>(null);
  const [done, setDone] = useState(false);

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <FileUp className="h-4 w-4" aria-hidden /> Restore from a package
        </span>
      }
    >
      <Alert tone="warning">
        Restoring <strong>replaces</strong> the AI on this computer. It does not merge the two.
      </Alert>

      <div className="mt-4 space-y-3">
        <label className="block text-sm">
          <span className="text-fg-muted">The .myai file</span>
          <input
            value={path}
            onChange={(e) => {
              setPath(e.target.value);
              setFound(null);
              setDone(false);
            }}
            placeholder="/path/to/nova.myai"
            className="mt-1 w-full rounded-lg border border-border bg-transparent p-2 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="text-fg-muted">Password, if it has one</span>
          <input
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
            autoComplete="off"
            className="mt-1 w-full rounded-lg border border-border bg-transparent p-2 text-sm"
          />
        </label>
        <Button
          variant="secondary"
          onClick={() => {
            preview.mutate(
              { path, password },
              {
                onSuccess: (result) => {
                  setFound(result);
                },
              },
            );
          }}
          disabled={path.trim() === "" || preview.isPending}
        >
          {preview.isPending ? "Reading…" : "See what is in it"}
        </Button>
      </div>

      {preview.isError && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(preview.error)}</Alert>
        </div>
      )}

      {found && !done && (
        <div className="mt-4 space-y-3">
          <dl className="space-y-1 text-sm">
            <Row label="AI in the package">{found.ai_name}</Row>
            <Row label="Written">
              {found.exported_at ? new Date(found.exported_at).toLocaleString() : "unknown"} by
              version {found.exported_by}
            </Row>
            {found.replaces_ai && (
              <Row label="This would replace">
                <strong>{found.replaces_ai}</strong>, on this computer
              </Row>
            )}
          </dl>

          <div className="space-y-2">
            <p className="text-sm font-medium">What will work on this computer</p>
            {found.capabilities.map((capability) => (
              <Capability key={capability.name} capability={capability} />
            ))}
          </div>

          {found.warnings.map((warning) => (
            <Alert key={warning} tone="warning">
              {warning}
            </Alert>
          ))}

          <label className="block text-sm">
            <span className="text-fg-muted">
              Type <code className="font-mono">{CONFIRMATION}</code> to confirm
            </span>
            <input
              value={typed}
              onChange={(e) => {
                setTyped(e.target.value);
              }}
              className="mt-1 w-full rounded-lg border border-border bg-transparent p-2 font-mono text-sm"
            />
          </label>
          <Button
            variant="danger"
            disabled={typed !== CONFIRMATION || restore.isPending}
            onClick={() => {
              restore.mutate(
                { path, password, confirm: typed },
                {
                  onSuccess: () => {
                    setDone(true);
                    setTyped("");
                  },
                },
              );
            }}
          >
            {restore.isPending ? "Restoring…" : `Replace ${found.replaces_ai ?? "this AI"}`}
          </Button>
        </div>
      )}

      {restore.isError && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(restore.error)}</Alert>
        </div>
      )}
      {done && restore.data && (
        <div className="mt-4 space-y-2 text-sm">
          <Alert tone="success">
            Restored{" "}
            {Object.values(restore.data.rows_written as Record<string, number>).reduce(
              (a, b) => a + b,
              0,
            )}{" "}
            records.
          </Alert>
          <ul className="list-disc space-y-1 pl-5 text-xs text-fg-muted">
            {restore.data.notes.map((note: string) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Capability({ capability }: { capability: CapabilityRead }) {
  const supported = capability.verdict === "supported";
  return (
    <div className="flex items-start gap-2 rounded-lg border border-border p-2 text-sm">
      {supported ? (
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
      ) : (
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
      )}
      <div className="min-w-0">
        <p className="font-medium">
          {capability.name}{" "}
          <span className="text-xs font-normal text-fg-muted">
            · {capability.verdict.replace("_", " ")}
          </span>
        </p>
        <p className="text-xs text-fg-muted">{capability.detail}</p>
      </div>
    </div>
  );
}
