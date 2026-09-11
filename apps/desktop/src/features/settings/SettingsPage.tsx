import type { ComputePreset, ExperienceMode, Theme } from "@myai/api-client";

import { Alert, Card, PageHeader, Spinner } from "../../components/ui";
import { describeError, usePreferences, useUpdatePreferences } from "../../lib/api";

const COMPUTE: Array<{ value: ComputePreset; label: string; percent: number }> = [
  { value: "low", label: "Low", percent: 25 },
  { value: "balanced", label: "Balanced", percent: 50 },
  { value: "high", label: "High", percent: 75 },
  { value: "maximum", label: "Maximum", percent: 100 },
];

export function SettingsPage() {
  const prefs = usePreferences();
  const update = useUpdatePreferences();
  if (prefs.isPending) return <Spinner />;
  if (prefs.isError) return <Alert tone="danger">{describeError(prefs.error)}</Alert>;
  const p = prefs.data;

  return (
    <>
      <PageHeader title="Settings" />
      <div className="space-y-5">
        <Card title="Experience">
          <Segmented<ExperienceMode>
            name="experience_mode"
            value={p.experience_mode}
            options={[
              { value: "beginner", label: "Beginner", hint: "Plain language. No hyperparameters." },
              {
                value: "advanced",
                label: "Advanced",
                hint: "Expose model, dataset and training settings.",
              },
            ]}
            onChange={(v) => {
              update.mutate({ experience_mode: v });
            }}
          />
          {p.experience_mode === "advanced" && (
            <p className="mt-3 text-xs text-warning">
              Changing advanced settings can reduce training quality or cause failures.
            </p>
          )}
        </Card>
        <Card title="Compute">
          <Segmented<ComputePreset>
            name="compute_preset"
            value={p.compute_preset}
            options={COMPUTE.map((c) => ({ value: c.value, label: `${c.label} · ${c.percent}%` }))}
            onChange={(v) => {
              update.mutate({ compute_preset: v });
            }}
          />
          <p className="mt-3 text-xs text-fg-muted">
            Higher settings may make your computer slower and hotter. Hardware safety limits are
            never bypassed.
          </p>
        </Card>
        <Card title="Appearance">
          <Segmented<Theme>
            name="theme"
            value={p.theme}
            options={[
              { value: "system", label: "System" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ]}
            onChange={(v) => {
              update.mutate({ theme: v });
            }}
          />
        </Card>
        {update.isError && <Alert tone="danger">{describeError(update.error)}</Alert>}
      </div>
    </>
  );
}

function Segmented<T extends string>({
  name,
  value,
  options,
  onChange,
}: {
  name: string;
  value: T;
  options: Array<{ value: T; label: string; hint?: string }>;
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={name} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => {
              onChange(o.value);
            }}
            className={
              active
                ? "rounded-xl border-2 border-accent bg-accent-soft px-4 py-3 text-left"
                : "rounded-xl border-2 border-border bg-bg px-4 py-3 text-left hover:border-fg-muted"
            }
          >
            <div className="text-sm font-semibold">{o.label}</div>
            {o.hint && <div className="text-xs text-fg-muted">{o.hint}</div>}
          </button>
        );
      })}
    </div>
  );
}
