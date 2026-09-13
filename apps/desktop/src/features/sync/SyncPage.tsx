/**
 * Sync (spec §16, §18, §72): keeping your own devices in step.
 *
 * The page is built around the two questions a person actually has, in that order: what
 * leaves this machine, and what happened when two of my devices disagreed. The list of
 * things that never leave is shown in full rather than summarised — "we only sync what we
 * need to" is the kind of sentence that means nothing, and a table of every record with the
 * reason beside it means something.
 */
import { RefreshCw, Laptop, ShieldCheck, GitMerge } from "lucide-react";

import { Alert, Button, Card, PageHeader, Row, Spinner, Stat } from "../../components/ui";
import {
  describeError,
  useDismissConflict,
  useSyncConflicts,
  useSyncOverview,
} from "../../lib/api";

function whenever(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : "never";
}

export function SyncPage() {
  const overview = useSyncOverview();
  const conflicts = useSyncConflicts();

  if (overview.isPending) return <Spinner />;
  if (overview.isError) return <Alert tone="danger">{describeError(overview.error)}</Alert>;
  const d = overview.data;

  return (
    <>
      <PageHeader
        title="Sync"
        subtitle="Your own devices, kept in step. No server in the middle."
      />
      <div className="space-y-5">
        <Card>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Devices in sync" value={d.peers.length} />
            <Stat label="Kinds that travel" value={d.syncs.length} />
            <Stat label="Stays on this machine" value={Object.keys(d.stays_local).length} />
            <Stat label="Unresolved clashes" value={d.unresolved_conflicts} />
          </div>
          <p className="mt-3 text-sm text-fg-muted">{d.detail}</p>
        </Card>

        <Card
          title={
            <span className="flex items-center gap-2">
              <Laptop className="h-4 w-4" aria-hidden /> Your devices
            </span>
          }
        >
          {d.peers.length === 0 ? (
            <p className="text-sm text-fg-muted">
              Nothing has synced with this computer yet. Pair a device under Security first —
              syncing uses the same pinned connection, so a device that cannot verify this machine
              cannot sync with it either.
            </p>
          ) : (
            <dl className="space-y-1 text-sm">
              {d.peers.map((peer) => (
                <Row key={peer.peer_install_id} label={peer.name}>
                  last synced {whenever(peer.last_synced_at)}
                  <span className="block font-mono text-xs break-all text-fg-muted">
                    {peer.peer_install_id}
                  </span>
                </Row>
              ))}
            </dl>
          )}
        </Card>

        <Card
          title={
            <span className="flex items-center gap-2">
              <GitMerge className="h-4 w-4" aria-hidden /> When two devices disagree
            </span>
          }
        >
          <p className="mb-3 text-sm text-fg-muted">
            One version has to be chosen. The other is kept here, not deleted.
          </p>
          {conflicts.isPending ? (
            <Spinner />
          ) : conflicts.isError ? (
            <Alert tone="danger">{describeError(conflicts.error)}</Alert>
          ) : conflicts.data.length === 0 ? (
            <p className="text-sm text-fg-muted">
              Nothing has clashed. Your devices agree about everything they share.
            </p>
          ) : (
            <ul className="space-y-3">
              {conflicts.data.map((conflict) => (
                <ConflictRow key={conflict.id} conflict={conflict} />
              ))}
            </ul>
          )}
        </Card>

        <Card
          title={
            <span className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" aria-hidden /> What never leaves this machine
            </span>
          }
        >
          <p className="mb-3 text-sm text-fg-muted">
            Every kind of record that stays here, and the reason it does.
          </p>
          <dl className="space-y-2 text-sm">
            {Object.entries(d.stays_local)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([name, reason]) => (
                <Row key={name} label={name}>
                  <span className="text-fg-muted">{reason}</span>
                </Row>
              ))}
          </dl>
        </Card>

        <Card title="What travels">
          <p className="mb-3 text-sm text-fg-muted">
            The columns that are sent to your own devices. Nothing else is.
          </p>
          <dl className="space-y-1 text-sm">
            {d.syncs.map((kind) => (
              <Row key={kind.name} label={kind.name}>
                <span className="font-mono text-xs text-fg-muted">{kind.travels.join(", ")}</span>
              </Row>
            ))}
          </dl>
        </Card>
      </div>
    </>
  );
}

function ConflictRow({
  conflict,
}: {
  conflict: ReturnType<typeof useSyncConflicts>["data"] extends (infer T)[] | undefined ? T : never;
}) {
  const dismiss = useDismissConflict();
  const payload = conflict.losing_payload as Record<string, unknown>;
  const replaced =
    (typeof payload.title === "string" && payload.title) ||
    (typeof payload.content === "string" && payload.content) ||
    "(no text)";

  return (
    <li className="rounded-lg border border-border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {conflict.entity} · kept the {conflict.kept === "remote" ? "other device's" : "local"}{" "}
            version
          </p>
          <p className="mt-1 text-xs text-fg-muted">
            Replaced on {whenever(conflict.detected_at)}. What it replaced:
          </p>
          <p className="mt-1 rounded bg-bg-muted p-2 text-sm break-words">{replaced}</p>
        </div>
        <Button
          variant="ghost"
          onClick={() => {
            dismiss.mutate(conflict.id);
          }}
          disabled={dismiss.isPending}
        >
          <RefreshCw className="h-4 w-4" /> Mark as seen
        </Button>
      </div>
    </li>
  );
}
