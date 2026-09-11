/**
 * First-run flow (spec §87). Progress is persisted in preferences.onboarding_step so a
 * closed app resumes where it left off. Steps that belong to later phases are shown as
 * such and skipped, never faked.
 */
import type { OnboardingStep } from "@myai/api-client";
import { Brain, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router";

import { Alert, Button, Card, PhaseTag, Spinner } from "../../components/ui";
import { cx } from "../../lib/cx";
import {
  describeError,
  useCreateProfile,
  useAcceptLicense,
  useHardware,
  useModels,
  usePreferences,
  useRecommendedModel,
  useStartDownload,
  useProfile,
  useStorage,
  useUpdatePreferences,
  useUpdateProfile,
} from "../../lib/api";
import { GuidePanel } from "../guide/GuidePanel";
import { HardwareSummary } from "../hardware/HardwareSummary";
import { LicenseDialog } from "../models/LicenseDialog";
import { INTEREST_OPTIONS, toCreatePayload } from "../profile/model";
import { ProfileForm } from "../profile/ProfileForm";
import { StoragePicker } from "../storage/StoragePicker";

const ORDER: OnboardingStep[] = [
  "welcome",
  "name_ai",
  "interests",
  "hardware_scan",
  "storage",
  "privacy",
  "account",
  "local_model",
  "done",
];

const TITLES: Record<OnboardingStep, string> = {
  welcome: "Welcome",
  name_ai: "Name your AI",
  interests: "Interests",
  hardware_scan: "Hardware",
  storage: "Storage",
  privacy: "Privacy",
  account: "Account",
  local_model: "Local model",
  done: "Ready",
};

export function OnboardingWizard() {
  const prefs = usePreferences();
  if (!prefs.data) return <Spinner />;
  return (
    <WizardSteps
      initialStep={prefs.data.onboarding_step}
      alreadyCompleted={prefs.data.onboarding_completed}
    />
  );
}

function WizardSteps({
  initialStep,
  alreadyCompleted,
}: {
  initialStep: OnboardingStep;
  alreadyCompleted: boolean;
}) {
  const updatePrefs = useUpdatePreferences();
  const navigate = useNavigate();
  const [step, setStep] = useState<OnboardingStep>(initialStep);
  // Captured once at mount: a user who is already onboarded and opens this screen goes
  // home. Finishing the wizard flips the preference while this component stays mounted,
  // so the value stays false and the wizard itself performs the final navigation.
  const [redirectHome] = useState(alreadyCompleted);
  if (redirectHome) return <Navigate to="/" replace />;

  const index = ORDER.indexOf(step);
  const go = (next: OnboardingStep) => {
    setStep(next);
    updatePrefs.mutate({ onboarding_step: next });
  };
  const advance = () => {
    go(ORDER[Math.min(index + 1, ORDER.length - 1)] ?? "done");
  };
  const back = () => {
    setStep(ORDER[Math.max(index - 1, 0)] ?? "welcome");
  };
  const finish = async () => {
    await updatePrefs.mutateAsync({ onboarding_step: "done", onboarding_completed: true });
    await navigate("/chat", { replace: true });
  };

  return (
    <div className="mx-auto flex min-h-full max-w-2xl flex-col px-6 py-10">
      <ol className="mb-8 flex flex-wrap gap-2" aria-label="Progress">
        {ORDER.map((s, i) => (
          <li
            key={s}
            aria-current={s === step ? "step" : undefined}
            className={cx(
              "rounded-full px-2.5 py-1 text-xs font-medium",
              i < index && "bg-success/20 text-success",
              i === index && "bg-accent text-accent-fg",
              i > index && "bg-bg-muted text-fg-muted",
            )}
          >
            {TITLES[s]}
          </li>
        ))}
      </ol>

      <Card className="flex-1">
        {step === "welcome" && <Welcome onNext={advance} />}
        {step === "name_ai" && <NameStep onNext={advance} onBack={back} />}
        {step === "interests" && <InterestsStep onNext={advance} onBack={back} />}
        {step === "hardware_scan" && <HardwareStep onNext={advance} onBack={back} />}
        {step === "storage" && <StorageStep onNext={advance} onBack={back} />}
        {step === "privacy" && <PrivacyStep onNext={advance} onBack={back} />}
        {step === "account" && (
          <LaterPhaseStep
            title="Sign in (optional)"
            phase={5}
            onNext={advance}
            onBack={back}
            body="Accounts unlock device pairing and optional encrypted sync. Your AI never needs an account to run locally. Sign-in through the MyAI Academy website arrives in Phase 5."
          />
        )}
        {step === "local_model" && <LocalModelStep onNext={advance} onBack={back} />}
        {step === "done" && (
          <DoneStep
            onFinish={() => void finish().catch(() => undefined)}
            busy={updatePrefs.isPending}
          />
        )}
      </Card>
      {updatePrefs.isError && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(updatePrefs.error)}</Alert>
        </div>
      )}
    </div>
  );
}

function StepFooter({
  onBack,
  onNext,
  nextLabel = "Continue",
  nextDisabled,
}: {
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
}) {
  return (
    <div className="mt-6 flex justify-between">
      {onBack ? (
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
      ) : (
        <span />
      )}
      {onNext && (
        <Button onClick={onNext} disabled={nextDisabled}>
          {nextLabel}
        </Button>
      )}
    </div>
  );
}

function Welcome({ onNext }: { onNext: () => void }) {
  return (
    <div className="text-center">
      <Brain className="mx-auto h-14 w-14 text-accent" aria-hidden />
      <h1 className="mt-4 text-3xl font-bold tracking-tight">MyAI Academy</h1>
      <p className="mt-2 text-fg-muted">Build it. Teach it. Make it yours.</p>
      <p className="mx-auto mt-6 max-w-md text-sm">
        You are about to create an AI that lives on your own computer. It will have a name, a
        personality, and a home on your disk. Nothing you make here is uploaded anywhere.
      </p>
      <div className="mt-8">
        <Button size="lg" onClick={onNext}>
          Let's begin
        </Button>
      </div>
      <div className="mt-10 border-t border-border pt-6 text-left">
        <GuidePanel compact />
      </div>
    </div>
  );
}

function NameStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const profile = useProfile();
  const create = useCreateProfile();
  const update = useUpdateProfile();
  if (profile.isPending) return <Spinner />;
  const existing = profile.data;

  return (
    <>
      <h2 className="text-xl font-bold">Name your AI</h2>
      <p className="mb-5 text-sm text-fg-muted">
        Give it a name and a personality. You can change both later.
      </p>
      <ProfileForm
        initial={{
          name: existing?.name ?? "",
          owner_name: existing?.owner_name ?? "",
          personality: existing?.personality ?? "",
          communication_style: existing?.communication_style ?? "",
          interests: existing?.interests ?? [],
          goals: existing?.goals ?? [],
        }}
        submitLabel="Continue"
        busy={create.isPending || update.isPending}
        onSubmit={(v) => {
          const payload = toCreatePayload(v);
          if (existing) {
            update.mutate(
              { ...payload, expected_version: existing.version },
              { onSuccess: onNext },
            );
          } else {
            create.mutate(payload, { onSuccess: onNext });
          }
        }}
      />
      {(create.isError || update.isError) && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(create.error ?? update.error)}</Alert>
        </div>
      )}
      <StepFooter onBack={onBack} />
    </>
  );
}

function InterestsStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const profile = useProfile();
  const update = useUpdateProfile();
  const [selected, setSelected] = useState<string[] | null>(null);
  const current = selected ?? profile.data?.interests ?? [];
  const toggle = (i: string) => {
    setSelected(current.includes(i) ? current.filter((x) => x !== i) : [...current, i]);
  };

  return (
    <>
      <h2 className="text-xl font-bold">
        What should {profile.data?.name ?? "your AI"} be good at?
      </h2>
      <p className="mb-5 text-sm text-fg-muted">
        Pick a few. This only orders suggestions; nothing is downloaded.
      </p>
      <div className="flex flex-wrap gap-2">
        {INTEREST_OPTIONS.map((i) => {
          const on = current.includes(i);
          return (
            <button
              key={i}
              type="button"
              aria-pressed={on}
              onClick={() => {
                toggle(i);
              }}
              className={cx(
                "rounded-full px-4 py-2 text-sm font-medium",
                on ? "bg-accent text-accent-fg" : "bg-bg-muted text-fg-muted hover:text-fg",
              )}
            >
              {i}
            </button>
          );
        })}
      </div>
      {update.isError && <Alert tone="danger">{describeError(update.error)}</Alert>}
      <StepFooter
        onBack={onBack}
        nextDisabled={update.isPending}
        onNext={() => {
          if (!profile.data || selected === null) {
            onNext();
            return;
          }
          update.mutate(
            { interests: selected, expected_version: profile.data.version },
            { onSuccess: onNext },
          );
        }}
      />
    </>
  );
}

function HardwareStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const hardware = useHardware();
  return (
    <>
      <h2 className="text-xl font-bold">Your hardware</h2>
      <p className="mb-5 text-sm text-fg-muted">
        This is what your AI has to work with. The tier is an estimate from specifications, not a
        promise.
      </p>
      {hardware.isPending && <Spinner label="Scanning…" />}
      {hardware.isError && <Alert tone="danger">{describeError(hardware.error)}</Alert>}
      {hardware.data && <HardwareSummary report={hardware.data} />}
      <StepFooter onBack={onBack} onNext={onNext} nextDisabled={hardware.isPending} />
    </>
  );
}

function StorageStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const storage = useStorage();
  return (
    <>
      <h2 className="text-xl font-bold">Where should your AI live?</h2>
      <p className="mb-5 text-sm text-fg-muted">
        Models, training data and checkpoints can be large. Pick a folder on a drive with room to
        grow, or an external SSD.
      </p>
      {storage.data?.configured ? (
        <Alert tone="success" title="Storage configured">
          <span className="font-mono text-xs">{storage.data.root_path}</span>
        </Alert>
      ) : (
        <StoragePicker />
      )}
      <StepFooter onBack={onBack} onNext={onNext} nextDisabled={!storage.data?.configured} />
    </>
  );
}

function PrivacyStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  return (
    <>
      <div className="flex items-center gap-3">
        <ShieldCheck className="h-8 w-8 text-success" aria-hidden />
        <h2 className="text-xl font-bold">Private by default</h2>
      </div>
      <ul className="mt-4 space-y-3 text-sm">
        <li>
          <strong>Local by design.</strong> Conversations, memories, files, training data and model
          weights stay on this computer unless you explicitly export or share them.
        </li>
        <li>
          <strong>Sharing by choice.</strong> Contributing data to improve MyAI Academy is off. If
          you ever turn it on, you choose exactly which categories to share and can stop at any
          time.
        </li>
        <li>
          <strong>Nothing hidden.</strong> The Privacy Center shows what this app does on the
          network and the Activity log records security-relevant events locally.
        </li>
        <li>
          <strong>No lock-in.</strong> You will be able to export everything, including your AI, in
          an open, documented format.
        </li>
      </ul>
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="I understand" />
    </>
  );
}

function LaterPhaseStep({
  title,
  phase,
  body,
  onNext,
  onBack,
}: {
  title: string;
  phase: number;
  body: string;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <>
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-bold">{title}</h2>
        <PhaseTag phase={phase} />
      </div>
      <p className="mt-3 text-sm">{body}</p>
      <StepFooter onBack={onBack} onNext={onNext} nextLabel="Skip for now" />
    </>
  );
}

function LocalModelStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const models = useModels(2000);
  const recommended = useRecommendedModel();
  const accept = useAcceptLicense();
  const start = useStartDownload();
  const [showLicense, setShowLicense] = useState(false);
  const entry = models.data?.models.find((m) => m.id === recommended.data?.id) ?? null;
  const installedAny = models.data?.models.some((m) => m.installed) ?? false;
  const download = entry?.download;
  const running = download && ["queued", "running", "verifying"].includes(download.status);

  return (
    <>
      <h2 className="text-xl font-bold">A model for your AI</h2>
      <p className="mb-4 text-sm text-fg-muted">
        Chat runs on this computer with a small open model. This is the one we suggest for your
        hardware; you can add others later under Models. The licence is shown before anything is
        downloaded.
      </p>
      {models.data && !models.data.runtime_available && (
        <Alert tone="danger" title="Inference runtime missing">
          {models.data.runtime_detail}
        </Alert>
      )}
      {(models.isPending || recommended.isPending) && <Spinner />}
      {entry?.catalog && (
        <div className="rounded-xl border border-border bg-bg p-4">
          <div className="font-semibold">{entry.name}</div>
          <div className="text-xs text-fg-muted">
            {entry.catalog.parameters_billion}B · about{" "}
            {Math.round(entry.catalog.approx_size_bytes / 1024 ** 2)} MB · {entry.license.name}
          </div>
          <p className="mt-2 text-sm">{entry.description}</p>
          {running && download && (
            <div className="mt-3">
              <div className="h-2 w-full overflow-hidden rounded-full bg-bg-muted">
                <div
                  className="h-full bg-accent transition-[width]"
                  style={{
                    width: `${download.bytes_total ? (download.bytes_done / download.bytes_total) * 100 : 0}%`,
                  }}
                />
              </div>
              <div className="mt-1 text-xs text-fg-muted">{download.status}…</div>
            </div>
          )}
          {download?.status === "failed" && (
            <div className="mt-3">
              <Alert tone="danger">{download.error}</Alert>
            </div>
          )}
          {entry.installed ? (
            <div className="mt-3 text-sm text-success">Installed and verified.</div>
          ) : (
            !running && (
              <Button
                className="mt-3"
                onClick={() => {
                  setShowLicense(true);
                }}
              >
                Read licence and download
              </Button>
            )
          )}
        </div>
      )}
      {(accept.isError || start.isError) && (
        <div className="mt-3">
          <Alert tone="danger">{describeError(accept.error ?? start.error)}</Alert>
        </div>
      )}
      {showLicense && entry?.catalog && (
        <LicenseDialog
          entry={entry}
          catalog={entry.catalog}
          busy={accept.isPending || start.isPending}
          onClose={() => {
            setShowLicense(false);
          }}
          onAccept={() => {
            accept.mutate(entry.id, {
              onSuccess: () => {
                start.mutate(entry.id, {
                  onSettled: () => {
                    setShowLicense(false);
                  },
                });
              },
              onError: () => {
                setShowLicense(false);
              },
            });
          }}
        />
      )}
      <StepFooter
        onBack={onBack}
        onNext={onNext}
        nextLabel={installedAny ? "Continue" : "Skip for now"}
      />
    </>
  );
}

function DoneStep({ onFinish, busy }: { onFinish: () => void; busy: boolean }) {
  const profile = useProfile();
  return (
    <div className="text-center">
      <div className="text-5xl" aria-hidden>
        🎓
      </div>
      <h2 className="mt-3 text-2xl font-bold">{profile.data?.name ?? "Your AI"} is ready</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-fg-muted">
        Say hello in Chat, or try <code className="font-mono">/help</code>. When skill packages
        arrive, <code className="font-mono">/learn coding</code> will teach your AI its first skill.
      </p>
      <div className="mt-8">
        <Button size="lg" onClick={onFinish} disabled={busy}>
          Start chatting
        </Button>
      </div>
      <div className="mt-10 border-t border-border pt-6 text-left">
        <GuidePanel compact />
      </div>
    </div>
  );
}
