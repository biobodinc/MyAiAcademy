import { useState } from "react";

import { Button, Field, Input } from "../../components/ui";
import { INTEREST_OPTIONS, type ProfileFormValues } from "./model";

export function ProfileForm({
  initial,
  onSubmit,
  submitLabel,
  busy,
}: {
  initial: ProfileFormValues;
  onSubmit: (values: ProfileFormValues) => void;
  submitLabel: string;
  busy?: boolean;
}) {
  const [values, setValues] = useState(initial);
  const set = <K extends keyof ProfileFormValues>(key: K, value: ProfileFormValues[K]) => {
    setValues((v) => ({ ...v, [key]: value }));
  };
  const toggleInterest = (i: string) => {
    set(
      "interests",
      values.interests.includes(i)
        ? values.interests.filter((x) => x !== i)
        : [...values.interests, i],
    );
  };

  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(values);
      }}
    >
      <Field label="AI name" htmlFor="ai-name" hint="You can rename it later.">
        <Input
          id="ai-name"
          required
          maxLength={64}
          value={values.name}
          onChange={(e) => {
            set("name", e.target.value);
          }}
          placeholder="Nova"
          autoFocus
        />
      </Field>
      <Field label="Your name (optional)" htmlFor="owner-name">
        <Input
          id="owner-name"
          maxLength={128}
          value={values.owner_name}
          onChange={(e) => {
            set("owner_name", e.target.value);
          }}
        />
      </Field>
      <Field
        label="Personality"
        htmlFor="personality"
        hint="A few words. This shapes how your AI talks, it does not retrain the model."
      >
        <Input
          id="personality"
          maxLength={500}
          value={values.personality}
          onChange={(e) => {
            set("personality", e.target.value);
          }}
          placeholder="Helpful, curious, concise"
        />
      </Field>
      <Field label="Communication style" htmlFor="style">
        <Input
          id="style"
          maxLength={500}
          value={values.communication_style}
          onChange={(e) => {
            set("communication_style", e.target.value);
          }}
          placeholder="Friendly and direct"
        />
      </Field>
      <fieldset>
        <legend className="text-sm font-medium">Interests</legend>
        <p className="text-xs text-fg-muted">Suggests which skills to learn first.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {INTEREST_OPTIONS.map((i) => {
            const on = values.interests.includes(i);
            return (
              <button
                key={i}
                type="button"
                aria-pressed={on}
                onClick={() => {
                  toggleInterest(i);
                }}
                className={
                  on
                    ? "rounded-full bg-accent px-3 py-1 text-sm font-medium text-accent-fg"
                    : "rounded-full bg-bg-muted px-3 py-1 text-sm font-medium text-fg-muted hover:text-fg"
                }
              >
                {i}
              </button>
            );
          })}
        </div>
      </fieldset>
      <Button type="submit" disabled={busy || values.name.trim().length === 0}>
        {busy ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
