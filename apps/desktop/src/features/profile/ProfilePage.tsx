import { Alert, Card, PageHeader, Spinner } from "../../components/ui";
import { describeError, useProfile, useUpdateProfile } from "../../lib/api";
import { ProfileForm } from "./ProfileForm";

export function ProfilePage() {
  const profile = useProfile();
  const update = useUpdateProfile();

  if (profile.isPending) return <Spinner />;
  if (profile.isError) return <Alert tone="danger">{describeError(profile.error)}</Alert>;
  const p = profile.data;
  if (!p) return <Alert tone="warning">No AI profile exists yet. Complete onboarding first.</Alert>;

  return (
    <>
      <PageHeader
        title={p.name}
        subtitle={
          <span>
            AI ID <span className="font-mono text-xs">{p.ai_id}</span> · created{" "}
            {new Date(p.created_at).toLocaleDateString()}
          </span>
        }
      />
      <Card title="Identity & personality">
        <ProfileForm
          key={p.version}
          initial={{
            name: p.name,
            owner_name: p.owner_name,
            personality: p.personality,
            communication_style: p.communication_style,
            interests: p.interests,
            goals: p.goals,
          }}
          submitLabel="Save changes"
          busy={update.isPending}
          onSubmit={(v) => {
            update.mutate({
              name: v.name.trim(),
              owner_name: v.owner_name.trim(),
              personality: v.personality.trim(),
              communication_style: v.communication_style.trim(),
              interests: v.interests,
              goals: v.goals,
              expected_version: p.version,
            });
          }}
        />
        {update.isError && (
          <div className="mt-4">
            <Alert tone="danger">{describeError(update.error)}</Alert>
          </div>
        )}
        {update.isSuccess && (
          <div className="mt-4">
            <Alert tone="success">Saved.</Alert>
          </div>
        )}
      </Card>
    </>
  );
}
