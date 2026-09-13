/**
 * Security (spec §47, §51-§53, §60): who may act as this AI, and how secrets are stored.
 *
 * Two things on this page are irreversible — revoking a client and erasing everything — so
 * both state what they will do before they do it, and erasing asks for a typed phrase.
 */
import {
  formatBytes,
  type CapabilityInfo,
  type DeviceRead,
  type NetworkAccess,
  type PairingInvite,
} from "@myai/api-client";
import { KeyRound, ShieldAlert, ShieldCheck, Trash2, Wifi } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";

import {
  Alert,
  Button,
  Card,
  PageHeader,
  Row,
  Spinner,
  Stat,
  StatusPill,
} from "../../components/ui";
import {
  describeError,
  useCapabilityCatalog,
  useCreatePairingCode,
  useCreatePairingInvite,
  useDevices,
  useEraseData,
  useErasePreview,
  useExportData,
  useRevokeDevice,
  useSecurityOverview,
  useSetCapabilities,
  useSetNetworkAccess,
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

        <NetworkCard network={d.network} canManage={d.caller_is_owner} />
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

function NetworkCard({ network, canManage }: { network: NetworkAccess; canManage: boolean }) {
  const setAccess = useSetNetworkAccess();
  const invite = useCreatePairingInvite();

  return (
    <Card
      title="Your phone and other devices"
      action={
        canManage ? (
          <Button
            size="sm"
            variant={network.enabled ? "secondary" : "primary"}
            disabled={setAccess.isPending}
            onClick={() => {
              setAccess.mutate({ enabled: !network.enabled });
            }}
          >
            <Wifi className="h-4 w-4" aria-hidden />
            {network.enabled ? "Turn off" : "Allow devices on this network"}
          </Button>
        ) : undefined
      }
    >
      <p className="text-sm">{network.detail}</p>
      {network.enabled && (
        <dl className="mt-3 space-y-1 text-sm">
          <Row label="Reachable at">
            {network.addresses.map((a) => `${a}:${network.port ?? ""}`).join(", ")}
          </Row>
          <Row label="Certificate">
            <span className="font-mono text-xs break-all">
              {network.certificate_fingerprint_groups}
            </span>
            <span className="block text-xs text-fg-muted">
              A device pins this when it pairs, and then accepts only this computer. Compare it on
              the device if you want to check by eye.
            </span>
          </Row>
        </dl>
      )}
      {setAccess.isError && (
        <div className="mt-2">
          <Alert tone="danger">{describeError(setAccess.error)}</Alert>
        </div>
      )}
      {network.enabled && canManage && (
        <div className="mt-4">
          <Button
            size="sm"
            disabled={invite.isPending}
            onClick={() => {
              invite.mutate("");
            }}
          >
            <KeyRound className="h-4 w-4" aria-hidden /> Show a pairing code
          </Button>
          {invite.isError && (
            <div className="mt-2">
              <Alert tone="danger">{describeError(invite.error)}</Alert>
            </div>
          )}
          {invite.data && <InviteCard invite={invite.data} />}
        </div>
      )}
    </Card>
  );
}

function InviteCard({ invite }: { invite: PairingInvite }) {
  const [qr, setQr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Rendered in the app rather than fetched: the payload is a credential in transit and
    // has no business being sent anywhere to be drawn.
    void QRCode.toDataURL(invite.payload, { margin: 1, width: 240 }).then((url) => {
      if (!cancelled) setQr(url);
    });
    return () => {
      cancelled = true;
    };
  }, [invite.payload]);

  return (
    <div className="mt-4 flex flex-wrap items-start gap-4 rounded-xl border border-border p-4">
      {qr ? (
        <img src={qr} alt="Pairing QR code" className="h-40 w-40 rounded-lg bg-white p-2" />
      ) : (
        <div className="h-40 w-40 animate-pulse rounded-lg bg-bg-muted" />
      )}
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-mono text-2xl tracking-widest">{invite.code}</p>
        <p className="mt-1 text-xs text-fg-muted">
          {invite.host_name} · {invite.addresses.join(", ")}:{invite.port}
        </p>
        <p className="mt-2 text-xs break-all text-fg-muted">
          {invite.certificate_fingerprint_groups}
        </p>
        <p className="mt-2 text-xs">{invite.note}</p>
      </div>
    </div>
  );
}

function ClientsCard({ devices, canManage }: { devices: DeviceRead[]; canManage: boolean }) {
  const createCode = useCreatePairingCode();
  const revoke = useRevokeDevice();
  const catalog = useCapabilityCatalog();
  const [issued, setIssued] = useState<{ code: string; granted: string[] } | null>(null);
  const [wanted, setWanted] = useState<string[]>(["status:read", "skills:read", "models:read"]);
  const [editing, setEditing] = useState<string | null>(null);

  const all = catalog.data ?? [];

  return (
    <Card title="Clients that can act as your AI">
      <p className="text-sm text-fg-muted">
        A pairing code grants exactly what you tick here, and nothing else. The program redeeming it
        cannot ask for more.
      </p>

      {canManage && (
        <div className="mt-4 space-y-3 rounded-xl border border-border p-3">
          <p className="text-sm font-medium">What should the next client be allowed to do?</p>
          {catalog.isPending ? (
            <Spinner />
          ) : (
            <ul className="space-y-1">
              {all.map((info) => (
                <li key={info.capability}>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={wanted.includes(info.capability)}
                      onChange={(e) => {
                        setWanted((current) =>
                          e.target.checked
                            ? [...current, info.capability]
                            : current.filter((c) => c !== info.capability),
                        );
                      }}
                    />
                    <span className="min-w-0">
                      <span className="font-medium">{info.title}</span>
                      {info.sensitive && (
                        <span className="ml-2">
                          <StatusPill tone="warning">your content</StatusPill>
                        </span>
                      )}
                      <span className="block text-xs text-fg-muted">{info.detail}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <Button
            size="sm"
            disabled={createCode.isPending}
            onClick={() => {
              createCode.mutate(
                { label: "", capabilities: wanted },
                {
                  onSuccess: (code) => {
                    setIssued({ code: code.code, granted: code.capabilities });
                  },
                },
              );
            }}
          >
            <KeyRound className="h-4 w-4" aria-hidden /> Make a pairing code
          </Button>
        </div>
      )}

      {issued && (
        <div className="mt-3">
          <Alert tone="info" title="Pairing code">
            <p className="font-mono text-lg tracking-widest">{issued.code}</p>
            <p className="mt-1 text-xs">
              Grants: {issued.granted.length ? issued.granted.join(", ") : "nothing at all"}.
            </p>
            <p className="mt-1 text-xs">
              Single use, and only for the next few minutes. Anyone who has it can obtain a
              credential, so treat it like a password.
            </p>
          </Alert>
        </div>
      )}
      {createCode.isError && <Alert tone="danger">{describeError(createCode.error)}</Alert>}

      {devices.length === 0 ? (
        <p className="mt-3 text-sm text-fg-muted">
          No paired clients. Only this installation&rsquo;s own token can be used, and only from
          this machine.
        </p>
      ) : (
        <ul className="mt-3 space-y-2 text-sm">
          {devices.map((device) => (
            <li key={device.id} className="rounded-xl border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
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
                  <p className="mt-1 text-xs">
                    May:{" "}
                    {device.capabilities.length ? (
                      <span className="font-mono">{device.capabilities.join(", ")}</span>
                    ) : (
                      <span className="text-fg-muted">nothing</span>
                    )}
                  </p>
                </div>
                {canManage && !device.revoked_at && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setEditing(editing === device.id ? null : device.id);
                      }}
                    >
                      {editing === device.id ? "Done" : "Change"}
                    </Button>
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
                  </div>
                )}
              </div>
              {editing === device.id && <GrantEditor device={device} catalog={all} />}
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && <Alert tone="danger">{describeError(revoke.error)}</Alert>}
    </Card>
  );
}

/** Change what one client may do. Unticking is how permission is taken away. */
function GrantEditor({ device, catalog }: { device: DeviceRead; catalog: CapabilityInfo[] }) {
  const setCapabilities = useSetCapabilities();
  const [chosen, setChosen] = useState<string[]>(device.capabilities);

  return (
    <div className="mt-3 space-y-2 border-t border-border pt-3">
      <ul className="space-y-1">
        {catalog.map((info) => (
          <li key={info.capability}>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={chosen.includes(info.capability)}
                onChange={(e) => {
                  setChosen((current) =>
                    e.target.checked
                      ? [...current, info.capability]
                      : current.filter((c) => c !== info.capability),
                  );
                }}
              />
              <span className="min-w-0">
                <span className="font-medium">{info.title}</span>
                {info.sensitive && (
                  <span className="ml-2">
                    <StatusPill tone="warning">your content</StatusPill>
                  </span>
                )}
                <span className="block text-xs text-fg-muted">{info.detail}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <Button
        size="sm"
        disabled={setCapabilities.isPending}
        onClick={() => {
          setCapabilities.mutate({ deviceId: device.id, capabilities: chosen });
        }}
      >
        Save — takes effect on its next request
      </Button>
      {setCapabilities.isError && (
        <Alert tone="danger">{describeError(setCapabilities.error)}</Alert>
      )}
    </div>
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
