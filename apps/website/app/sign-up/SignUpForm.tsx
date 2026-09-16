"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field, Notice, SubmitButton } from "@/components/Form";
import { ApiError, api, storeToken } from "@/lib/account";

const MIN_PASSWORD = 10;

export function SignUpForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setBusy(true);
    try {
      const result = await api.signUp(
        String(form.get("email") ?? ""),
        String(form.get("password") ?? ""),
      );
      storeToken(result.token);
      router.push("/account");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Field label="Email" name="email" type="email" autoComplete="email" required />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={MIN_PASSWORD}
        required
        hint={`At least ${MIN_PASSWORD} characters. Length is the only rule — a phrase you can remember beats a short tangle you cannot.`}
      />
      {error ? <Notice kind="error">{error}</Notice> : null}
      <SubmitButton busy={busy}>Create account</SubmitButton>
      <p className="text-sm text-fg-muted">
        Already have one?{" "}
        <Link href="/sign-in" className="text-accent underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </form>
  );
}
