/**
 * The app's one piece of state: which host this device is paired with, and what it is doing.
 *
 * Everything the screens render comes from here, including the failures. A failure is not a
 * toast that disappears — being revoked, or being unable to verify the host, changes what
 * the app *is*, so each is a state the UI has to have a face for.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { HostClient, Revoked, pair as pairWithHost } from "./client";
import { reduceConnection, type ConnectionState } from "./connection";
import { credentialStore } from "./secureStore";
import type { DeviceCredential } from "./credential";
import { parseStatus, type HostStatus } from "./hostStatus";
import type { PairingInvite } from "./pairing";
import { CannotPin, pinnedTransport } from "./transport";

export interface HostView {
  loading: boolean;
  connection: ConnectionState;
  credential: DeviceCredential | null;
  status: HostStatus | null;
  /** Set when the last action failed, in words meant for the person holding the phone. */
  problem: string | null;
  pair(invite: PairingInvite, deviceName: string): Promise<void>;
  refresh(): Promise<void>;
  forget(): Promise<void>;
}

export function useHost(): HostView {
  const store = useMemo(() => credentialStore(), []);
  const [loading, setLoading] = useState(true);
  const [credential, setCredential] = useState<DeviceCredential | null>(null);
  const [connection, setConnection] = useState<ConnectionState>({ kind: "unpaired" });
  const [status, setStatus] = useState<HostStatus | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const load = useCallback(
    async (held: DeviceCredential) => {
      setConnection((state) =>
        reduceConnection(state, { type: "paired", hostName: held.hostName }),
      );
      try {
        const body = await new HostClient(held, pinnedTransport()).status();
        if (!alive.current) return;
        setStatus(parseStatus(body));
        setProblem(null);
        setConnection((state) => reduceConnection(state, { type: "local_link_up" }));
      } catch (error) {
        if (!alive.current) return;
        if (error instanceof Revoked) {
          // The credential is dead. Holding on to it would only produce the same failure
          // on every screen, so the device goes back to being unpaired.
          await store.clear();
          setCredential(null);
          setStatus(null);
          setConnection({ kind: "unpaired" });
          setProblem(error.message);
          return;
        }
        setProblem(error instanceof Error ? error.message : String(error));
        setConnection((state) =>
          reduceConnection(state, { type: "link_down", at: new Date().toISOString() }),
        );
      }
    },
    [store],
  );

  useEffect(() => {
    void (async () => {
      const held = await store.read();
      if (!alive.current) return;
      setCredential(held);
      if (held) await load(held);
      if (alive.current) setLoading(false);
    })();
  }, [store, load]);

  const pair = useCallback(
    async (invite: PairingInvite, deviceName: string) => {
      setProblem(null);
      setConnection({ kind: "connecting", hostName: invite.hostName });
      try {
        const issued = await pairWithHost(invite, deviceName, pinnedTransport());
        await store.write(issued);
        if (!alive.current) return;
        setCredential(issued);
        await load(issued);
      } catch (error) {
        if (!alive.current) return;
        setConnection({ kind: "unpaired" });
        setProblem(
          error instanceof CannotPin || error instanceof Error ? error.message : String(error),
        );
        throw error;
      }
    },
    [store, load],
  );

  const refresh = useCallback(async () => {
    if (credential) await load(credential);
  }, [credential, load]);

  const forget = useCallback(async () => {
    await store.clear();
    if (!alive.current) return;
    setCredential(null);
    setStatus(null);
    setProblem(null);
    setConnection({ kind: "unpaired" });
  }, [store]);

  return { loading, connection, credential, status, problem, pair, refresh, forget };
}
