"use client";

import { useState } from "react";

import { Field, Notice, SubmitButton } from "@/components/Form";
import { ApiError, api, storeToken } from "@/lib/account";

const MIN_PASSWORD = 10;

export function ChangePassword({ token }: { token: string }) {
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    setMessage(null);
    setBusy(true);
    try {
      // The server ends every session on a password change, including this one, and hands
      // back a replacement — so store it or the next request signs us out.
      const result = await api.changePassword(
        token,
        String(form.get("current_password") ?? ""),
        String(form.get("new_password") ?? ""),
      );
      storeToken(result.token);
      element.reset();
      setMessage({
        kind: "info",
        text: "Password changed. Every other signed-in session has been signed out.",
      });
    } catch (caught) {
      setMessage({
        kind: "error",
        text: caught instanceof ApiError ? caught.message : "Something went wrong. Try again.",
      });
    }
    setBusy(false);
  }

  return (
    <form onSubmit={onSubmit} className="mt-6 max-w-md space-y-5">
      <Field
        label="Current password"
        name="current_password"
        type="password"
        autoComplete="current-password"
        required
      />
      <Field
        label="New password"
        name="new_password"
        type="password"
        autoComplete="new-password"
        minLength={MIN_PASSWORD}
        required
        hint={`At least ${MIN_PASSWORD} characters.`}
      />
      {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}
      <SubmitButton busy={busy}>Change password</SubmitButton>
    </form>
  );
}
