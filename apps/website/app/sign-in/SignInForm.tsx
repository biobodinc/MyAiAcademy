"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field, Notice, SubmitButton } from "@/components/Form";
import { ApiError, api, storeToken } from "@/lib/account";

export function SignInForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setBusy(true);
    try {
      const result = await api.signIn(
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
        autoComplete="current-password"
        required
      />
      {error ? <Notice kind="error">{error}</Notice> : null}
      <SubmitButton busy={busy}>Sign in</SubmitButton>
      <p className="text-sm text-fg-muted">
        No account yet?{" "}
        <Link href="/sign-up" className="text-accent underline underline-offset-4">
          Create one
        </Link>
      </p>
    </form>
  );
}
