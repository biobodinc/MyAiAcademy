/**
 * Security (spec §47, §51-§53, §60): who may act as this AI, and how secrets are stored.
 *
 * Two things on this page are irreversible — revoking a client and erasing everything — so
 * both state what they will do before they do it, and erasing asks for a typed phrase.
 */
import { formatBytes, type DeviceRead } from "@myai/api-client";
import { KeyRound, ShieldAlert, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";

import { Alert, Button, Card, PageHeader, Spinner, Stat, StatusPill } from "../../components/ui";
import {
  describeError,
  useCreatePairingCode,
  useDevices,
  useEraseData,
  useErasePreview,
  useExportData,
  useRevokeDevice,
  useSecurityOverview,
} from "../../lib/api";

export function SecurityPage() {
  const overview = useSecurityOverview();
  const devices = useDevices();

  if (overview.isPending) return <Spinner />;
  if (overview.isError) return <Alert tone="danger">{describeError(overview.error)}</Alert>;
  const d = overview.data;
  const storage = d.secret_storage;

  return (
    <>
      <PageHeader
        title="Security"
        subtitle="Who may act as your AI, where your secrets live, and how to take your data out."
      />
      <div className="space-y-5">
        <Card>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Listening on" value={d.bound_to_loopback ? "127.0.0.1 only" : "network"} />
            <Stat label="You are" value={d.caller_is_owner ? "this installation" : d.caller_name} />
            <Stat label="Paired clients" value={d.active_clients} />
            <Stat label="Revoked" value={d.revoked_clients} />
          </div>
        </Card>

        <Card title="Where this installation's secrets live">
          {storage.checked ? (
            <div className="flex items-start gap-2 text-sm">
              {storage.problems.length === 0 ? (
                <ShieldCheck className="mt-0.5 h-4 w-4 text-success" aria-hidden />
              ) : (
                <ShieldAlert className="mt-0.5 h-4 w-4 text-warning" aria-hidden />
              )}
              <div>
                <p>{storage.detail}</p>
                {storage.mode && (
                  <p className="mt-1 text-xs text-fg-muted">
                    Token file permissions: {storage.mode}
                  </p>
                )}
                {storage.problems.map((p) => (
                  <p key={p} className="mt-1 text-xs text-warning">
                    {p}
                  </p>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-fg-muted">{storage.detail}</p>
          )}
        </Card>

        <Card title="Account">
          <div className="flex items-center gap-2">
            <StatusPill tone={d.account.linked ? "success" : "muted"}>
              {d.account.linked ? "linked" : "none"}
            </StatusPill>
            <p className="text-sm text-fg-muted">{d.account.detail}</p>
          </div>
        </Card>

        <ClientsCard devices={devices.data ?? []} canManage={d.caller_is_owner} />
        <DataCard canManage={d.caller_is_owner} />

        <Card title="How this works">
          <ul className="list-disc space-y-1 pl-5 text-sm text-fg-muted">
            {d.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}

function ClientsCard({ devices, canManage }: { devices: DeviceRead[]; canManage: boolean }) {
  const createCode = useCreatePairingCode();
  const revoke = useRevokeDevice();
  const [issued, setIssued] = useState<string | null>(null);

  return (
    <Card
      title="Clients that can act as your AI"
      action={
        canManage ? (
          <Button
            size="sm"
            disabled={createCode.isPending}
            onClick={() => {
              createCode.mutate("", {
                onSuccess: (code) => {
                  setIssued(code.code);
                },
              });
            }}
          >
            <KeyRound className="h-4 w-4" aria-hidden /> Pairing code
          </Button>
        ) : undefined
      }
    >
      {issued && (
        <Alert tone="info" title="Pairing code">
          <p className="font-mono text-lg tracking-widest">{issued}</p>
          <p className="mt-1 text-xs">
            Single use, and only for the next few minutes. Type it into the client you are pairing;
            anyone who has it can obtain a credential, so treat it like a password.
          </p>
        </Alert>
      )}
      {createCode.isError && <Alert tone="danger">{describeError(createCode.error)}</Alert>}
      {devices.length === 0 ? (
        <p className="text-sm text-fg-muted">
          No paired clients. Only this installation&rsquo;s own token can be used, and only from
          this machine.
        </p>
      ) : (
        <ul className="mt-3 space-y-2 text-sm">
          {devices.map((device) => (
            <li
              key={device.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border p-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{device.name}</span>
                  <StatusPill tone={device.revoked_at ? "muted" : "success"}>
                    {device.revoked_at ? "revoked" : device.kind}
                  </StatusPill>
                </div>
                <p className="text-xs text-fg-muted">
                  Added {new Date(device.created_at).toLocaleDateString()} ·{" "}
                  {device.last_seen_at
                    ? `last used ${new Date(device.last_seen_at).toLocaleString()}`
                    : "never used"}
                  {device.revoked_reason ? ` · ${device.revoked_reason}` : ""}
                </p>
              </div>
              {canManage && !device.revoked_at && (
                <Button
                  size="sm"
                  variant="danger"
                  disabled={revoke.isPending}
                  onClick={() => {
                    revoke.mutate({ device_id: device.id, reason: "Revoked from the app" });
                  }}
                >
                  Revoke
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && <Alert tone="danger">{describeError(revoke.error)}</Alert>}
    </Card>
  );
}

function DataCard({ canManage }: { canManage: boolean }) {
  const preview = useErasePreview();
  const exporting = useExportData();
  const erasing = useEraseData();
  const [confirm, setConfirm] = useState("");
  const [removeFiles, setRemoveFiles] = useState(false);
  const plan = preview.data;
  const phrase = plan?.confirmation_phrase ?? "ERASE MY DATA";
  const rows = plan ? Object.values(plan.row_counts).reduce((a, b) => a + b, 0) : 0;

  if (!canManage) {
    return (
      <Card title="Your data">
        <p className="text-sm text-fg-muted">
          Exporting and erasing are done in the app on the machine that holds this installation.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Your data">
      <p className="text-sm">
        An export contains everything this installation holds about you. It deliberately leaves out
        credentials, which are access grants rather than your data, and lists your model files
        instead of copying gigabytes of publicly downloadable weights.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={exporting.isPending}
          onClick={() => {
            exporting.mutate({ include_model_files: false });
          }}
        >
          {exporting.isPending ? "Exporting…" : "Export my data"}
        </Button>
        {exporting.data && (
          <span className="text-xs text-fg-muted">
            Written to {exporting.data.path} ({formatBytes(exporting.data.size_bytes)})
          </span>
        )}
      </div>
      {exporting.isError && (
        <div className="mt-2">
          <Alert tone="danger">{describeError(exporting.error)}</Alert>
        </div>
      )}

      <div className="mt-6 rounded-xl border border-danger/40 p-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-danger">
          <Trash2 className="h-4 w-4" aria-hidden /> Erase everything
        </h3>
        {plan && (
          <>
            <p className="mt-1 text-sm">
              {rows} rows of your data would be deleted, and {plan.storage_file_count} files
              totalling {formatBytes(plan.storage_bytes)} are in your storage root.
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-fg-muted">
              {plan.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </>
        )}
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 accent-accent"
            checked={removeFiles}
            onChange={(e) => {
              setRemoveFiles(e.target.checked);
            }}
          />
          Also delete the files under my storage root, including downloaded models
        </label>
        <label className="mt-3 block text-sm">
          <span className="text-fg-muted">
            Type <span className="font-mono">{phrase}</span> to confirm
          </span>
          <input
            value={confirm}
            onChange={(e) => {
              setConfirm(e.target.value);
            }}
            className="mt-1 w-full rounded-md border border-border bg-bg px-2 py-1"
            aria-label="Confirmation phrase"
          />
        </label>
        <Button
          size="sm"
          variant="danger"
          className="mt-3"
          disabled={confirm !== phrase || erasing.isPending}
          onClick={() => {
            erasing.mutate({ confirm, remove_files: removeFiles });
          }}
        >
          {erasing.isPending ? "Erasing…" : "Erase everything"}
        </Button>
        {erasing.isError && (
          <div className="mt-2">
            <Alert tone="danger">{describeError(erasing.error)}</Alert>
          </div>
        )}
        {erasing.data && (
          <Alert tone="success" title="Erased">
            <ul className="list-disc pl-5">
              {erasing.data.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </Alert>
        )}
      </div>
    </Card>
  );
}
