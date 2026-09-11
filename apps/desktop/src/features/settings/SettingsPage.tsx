import type {
  ComputePreset,
  ExperienceMode,
  Preferences,
  PreferencesUpdate,
  Theme,
} from "@myai/api-client";
import { useState } from "react";

import { Alert, Button, Card, Field, Input, PageHeader, Spinner } from "../../components/ui";
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
        {p.experience_mode === "advanced" && <AdvancedCompute prefs={p} />}
        {p.experience_mode === "advanced" && <ChatGeneration prefs={p} />}
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

type AdvancedKey =
  | "cpu_utilization_percent"
  | "gpu_utilization_percent"
  | "ram_limit_gib"
  | "temperature_limit_c"
  | "time_limit_minutes";

const ADVANCED: Array<{
  key: AdvancedKey;
  label: string;
  unit: string;
  min: number;
  max: number;
  step?: number;
  enforced: string;
}> = [
  {
    key: "cpu_utilization_percent",
    label: "CPU utilisation",
    unit: "%",
    min: 10,
    max: 100,
    enforced: "Enforced now: caps the threads used for chat.",
  },
  {
    key: "ram_limit_gib",
    label: "RAM limit",
    unit: "GB",
    min: 1,
    max: 4096,
    step: 0.5,
    enforced: "Enforced now: a model larger than this is refused instead of loaded.",
  },
  {
    key: "gpu_utilization_percent",
    label: "GPU utilisation",
    unit: "%",
    min: 10,
    max: 100,
    enforced: "Stored now; applied by training jobs (Phase 4).",
  },
  {
    key: "temperature_limit_c",
    label: "Temperature limit",
    unit: "°C",
    min: 50,
    max: 100,
    enforced: "Stored now; training pauses above it once telemetry exists (Phase 4).",
  },
  {
    key: "time_limit_minutes",
    label: "Time limit",
    unit: "min",
    min: 1,
    max: 43200,
    enforced: "Stored now; caps a training job's duration (Phase 4).",
  },
];

function AdvancedCompute({ prefs }: { prefs: Preferences }) {
  const update = useUpdatePreferences();
  const [draft, setDraft] = useState<Record<AdvancedKey, string>>(() => {
    const initial = {} as Record<AdvancedKey, string>;
    for (const f of ADVANCED) initial[f.key] = prefs[f.key] == null ? "" : String(prefs[f.key]);
    return initial;
  });

  const save = () => {
    const body: PreferencesUpdate = {};
    for (const f of ADVANCED) {
      const raw = draft[f.key].trim();
      body[f.key] = raw === "" ? null : Number(raw);
    }
    update.mutate(body);
  };

  return (
    <Card title="Advanced compute limits">
      <p className="text-xs text-warning">
        Changing advanced settings can reduce training quality or cause failures. Leave a field
        empty to let the compute preset decide. Hardware safety controls are never bypassed.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {ADVANCED.map((f) => (
          <Field key={f.key} label={`${f.label} (${f.unit})`} htmlFor={f.key} hint={f.enforced}>
            <Input
              id={f.key}
              type="number"
              inputMode="decimal"
              min={f.min}
              max={f.max}
              step={f.step ?? 1}
              placeholder="preset decides"
              value={draft[f.key]}
              onChange={(e) => {
                setDraft({ ...draft, [f.key]: e.target.value });
              }}
            />
          </Field>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={save} disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save limits"}
        </Button>
        {update.isSuccess && <span className="text-xs text-success">Saved.</span>}
      </div>
    </Card>
  );
}

function ChatGeneration({ prefs }: { prefs: Preferences }) {
  const update = useUpdatePreferences();
  const [maxTokens, setMaxTokens] = useState(String(prefs.chat_max_tokens));
  const [temperature, setTemperature] = useState(String(prefs.chat_temperature));
  return (
    <Card title="Chat generation">
      <p className="text-xs text-fg-muted">
        Defaults for every reply from the local model. Longer replies take longer; higher
        temperature is more varied and less precise.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Field label="Maximum reply length (tokens)" htmlFor="chat_max_tokens">
          <Input
            id="chat_max_tokens"
            type="number"
            min={32}
            max={8192}
            value={maxTokens}
            onChange={(e) => {
              setMaxTokens(e.target.value);
            }}
          />
        </Field>
        <Field label="Temperature (0 = deterministic, 2 = wild)" htmlFor="chat_temperature">
          <Input
            id="chat_temperature"
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            onChange={(e) => {
              setTemperature(e.target.value);
            }}
          />
        </Field>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button
          onClick={() => {
            update.mutate({
              chat_max_tokens: Number(maxTokens),
              chat_temperature: Number(temperature),
            });
          }}
          disabled={update.isPending}
        >
          {update.isPending ? "Saving…" : "Save chat defaults"}
        </Button>
        {update.isSuccess && <span className="text-xs text-success">Saved.</span>}
      </div>
    </Card>
  );
}
