import { Alert, Card, PageHeader, Spinner, Stat } from "../../components/ui";
import { describeError, usePreferences, usePrivacy, useUpdatePreferences } from "../../lib/api";

export function PrivacyPage() {
  const privacy = usePrivacy();
  const prefs = usePreferences();
  const update = useUpdatePreferences();
  if (privacy.isPending || prefs.isPending) return <Spinner />;
  if (privacy.isError) return <Alert tone="danger">{describeError(privacy.error)}</Alert>;
  const d = privacy.data;

  return (
    <>
      <PageHeader
        title="Privacy Center"
        subtitle="Private by default. Local by design. Sharing by choice."
      />
      <div className="space-y-5">
        <Card>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Stat label="Private data" value={d.private_data_location} />
            <Stat label="Cloud AI data uploads" value={d.cloud_ai_data_uploads} />
            <Stat label="Community sharing" value={d.community_sharing ? "ON" : "OFF"} />
            <Stat label="Cloud backup" value={d.cloud_backup ? "ON" : "OFF"} />
            <Stat label="Connected devices" value={d.connected_devices} />
            <Stat label="Connected apps" value={d.connected_apps} />
          </div>
        </Card>
        <Card title="What this build does on the network">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {d.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </Card>
        <Card title="Help improve MyAI Academy">
          <p className="text-sm">
            Would you like to contribute data to help improve future models and skills? This is off
            by default and nothing is sent in this version even when enabled: the contribution
            pipeline arrives in a later phase and will ask for granular consent (training examples,
            evaluation results, error reports) before any upload.
          </p>
          <label className="mt-4 flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 accent-accent"
              checked={prefs.data?.contributor_mode ?? false}
              onChange={(e) => {
                update.mutate({ contributor_mode: e.target.checked });
              }}
            />
            Yes, I want to be asked about contributing
          </label>
          <p className="mt-2 text-xs text-fg-muted">
            You can change this at any time. Anonymisation is never a guarantee of perfect privacy.
          </p>
        </Card>
      </div>
    </>
  );
}
