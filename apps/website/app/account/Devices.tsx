"use client";

import { useEffect, useState } from "react";

import { Notice } from "@/components/Form";
import { PairingInvite } from "@/components/PairingInvite";
import { ApiError, type Device, api } from "@/lib/account";

function when(value: string | null): string {
  if (!value) return "never";
  return new Date(value).toLocaleString();
}

export function Devices({ token }: { token: string }) {
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [invite, setInvite] = useState<{ code: string; expiresAt: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    api
      .devices(token)
      .then(setDevices)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "Could not load your devices."),
      );

  useEffect(() => {
    void load();
    // `load` closes over `token` only, which does not change while this is mounted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function act(work: () => Promise<unknown>) {
    setError(null);
    setBusy(true);
    try {
      await work();
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Try again.");
    }
    setBusy(false);
  }

  const addDevice = () =>
    act(async () => {
      const issued = await api.createPairingCode(token);
      setInvite({ code: issued.code, expiresAt: issued.expires_at });
    });

  const rename = (device: Device) => {
    const next = window.prompt("What should this device be called?", device.device_name);
    if (next && next.trim()) void act(() => api.renameDevice(token, device.device_id, next.trim()));
  };

  const revoke = (device: Device) => {
    const sure = window.confirm(
      `Cut off ${device.device_name}? It stops working straight away, and it would have to be paired again.`,
    );
    if (sure) void act(() => api.revokeDevice(token, device.device_id));
  };

  return (
    <div className="mt-6">
      <button
        type="button"
        onClick={addDevice}
        disabled={busy}
        className="rounded-sharp border border-fg px-5 py-2.5 font-medium transition-colors hover:bg-fg hover:text-bg disabled:opacity-50"
      >
        Add a device
      </button>

      {invite ? <PairingInvite code={invite.code} expiresAt={invite.expiresAt} /> : null}

      {error ? (
        <div className="mt-5">
          <Notice kind="error">{error}</Notice>
        </div>
      ) : null}

      {devices === null ? (
        <p className="mt-6 text-fg-muted">Loading…</p>
      ) : devices.length === 0 ? (
        <p className="mt-6 text-fg-muted">
          No devices yet. Add one to use your account from another computer or your phone.
        </p>
      ) : (
        <ul className="mt-6 border-t border-border">
          {devices.map((device) => (
            <li
              key={device.device_id}
              className="flex flex-col gap-2 border-b border-border py-4 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6"
            >
              <div>
                <p className={device.revoked ? "text-fg-muted line-through" : ""}>
                  {device.device_name}
                </p>
                <p className="datum mt-1 text-fg-muted">
                  {device.revoked ? "revoked" : `last seen ${when(device.last_seen)}`}
                </p>
              </div>
              {device.revoked ? null : (
                <div className="flex shrink-0 gap-4 text-sm">
                  <button
                    type="button"
                    onClick={() => rename(device)}
                    disabled={busy}
                    className="underline underline-offset-4 disabled:opacity-50"
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={() => revoke(device)}
                    disabled={busy}
                    className="text-accent underline underline-offset-4 disabled:opacity-50"
                  >
                    Revoke
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
