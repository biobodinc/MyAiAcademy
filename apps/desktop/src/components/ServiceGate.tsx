/**
 * Blocks the UI until the local service is reachable, and explains failures instead of
 * showing a broken dashboard (spec §67: never hide failures).
 */
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { describeError, useStatus } from "../lib/api";
import { getServiceState, inTauri, restartService } from "../lib/tauri";
import { Alert, Button, Spinner } from "./ui";

export function ServiceGate({ children }: { children: ReactNode }) {
  const shell = useQuery({
    queryKey: ["shell", "service-state"],
    queryFn: getServiceState,
    refetchInterval: (q) => (q.state.data?.kind === "running" ? false : 1000),
  });
  const status = useStatus(shell.data?.kind === "running" ? 10_000 : 0);

  if (shell.data?.kind === "failed") {
    return (
      <Centered>
        <Alert tone="danger" title="The local AI service could not start">
          <pre className="mt-2 overflow-auto rounded-lg bg-bg p-3 font-mono text-xs whitespace-pre-wrap">
            {shell.data.error}
          </pre>
          <div className="mt-3 flex gap-2">
            <Button onClick={() => void restartService().then(() => shell.refetch())}>
              Try again
            </Button>
          </div>
        </Alert>
      </Centered>
    );
  }

  if (shell.isPending || shell.data?.kind === "starting") {
    return (
      <Centered>
        <Spinner label="Starting your local AI service…" />
      </Centered>
    );
  }

  if (status.isPending) {
    return (
      <Centered>
        <Spinner label="Connecting to your AI…" />
      </Centered>
    );
  }

  if (status.isError) {
    return (
      <Centered>
        <Alert tone="danger" title="Cannot reach the local AI service">
          <p>{describeError(status.error)}</p>
          {!inTauri && (
            <p className="mt-2 text-fg-muted">
              You are running the UI in a browser. Start the service with <code>myai serve</code>{" "}
              and set <code>VITE_MYAI_DEV_TOKEN</code> in <code>apps/desktop/.env.local</code>.
            </p>
          )}
          <div className="mt-3">
            <Button onClick={() => void status.refetch()}>Retry</Button>
          </div>
        </Alert>
      </Centered>
    );
  }

  return <>{children}</>;
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="flex h-full items-center justify-center p-8">{children}</div>;
}
