import { Alert, Card, EmptyState, PageHeader, Spinner } from "../../components/ui";
import { describeError, useAudit } from "../../lib/api";

export function AuditPage() {
  const audit = useAudit(200);
  if (audit.isPending) return <Spinner />;
  if (audit.isError) return <Alert tone="danger">{describeError(audit.error)}</Alert>;

  return (
    <>
      <PageHeader
        title="Security activity"
        subtitle="A local record of what happened. Never contains private content."
      />
      <Card>
        {audit.data.length === 0 ? (
          <EmptyState icon="🛡️" title="Nothing yet">
            Actions like storage changes or consent toggles appear here.
          </EmptyState>
        ) : (
          <ol className="divide-y divide-border">
            {audit.data.map((e) => (
              <li key={e.id} className="flex items-baseline gap-4 py-2 text-sm">
                <time
                  className="w-40 shrink-0 text-xs text-fg-muted tabular-nums"
                  dateTime={e.occurred_at}
                >
                  {new Date(e.occurred_at).toLocaleString()}
                </time>
                <span className="w-24 shrink-0 rounded-md bg-bg-muted px-2 py-0.5 text-center text-xs">
                  {e.category}
                </span>
                <span className="flex-1">{e.summary}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </>
  );
}
