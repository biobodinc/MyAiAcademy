"use client";

import { useEffect, useState } from "react";

import { type AuditEvent, api } from "@/lib/account";

/** Event names are stored as identifiers; these are the same facts in plain words. */
const LABELS: Record<string, string> = {
  sign_up: "Account created",
  sign_in: "Signed in",
  sign_in_failed: "Wrong password",
  sign_out: "Signed out",
  password_changed: "Password changed",
  email_verified: "Email confirmed",
  email_verification_expired: "Confirmation link had expired",
  device_added: "Device added",
  device_paired: "Device paired",
  device_renamed: "Device renamed",
  device_revoked: "Device revoked",
  pairing_code_generated: "Pairing code created",
  pairing_code_used: "Pairing code used",
  pairing_code_reused: "Pairing code used again and refused",
  pairing_code_expired: "Pairing code had expired",
  pairing_code_burned: "Pairing code stopped after too many wrong guesses",
};

export function Activity({ token }: { token: string }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);

  useEffect(() => {
    api
      .activity(token)
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [token]);

  if (events === null) return <p className="mt-6 text-fg-muted">Loading…</p>;
  if (events.length === 0) return <p className="mt-6 text-fg-muted">Nothing recorded yet.</p>;

  return (
    <ul className="mt-6 border-t border-border">
      {events.map((event, i) => (
        <li
          key={`${event.created_at}-${i}`}
          className="flex flex-col gap-1 border-b border-border py-3 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6"
        >
          <span>{LABELS[event.event_type] ?? event.event_type}</span>
          <span className="datum shrink-0 text-fg-muted">
            {new Date(event.created_at).toLocaleString()}
            {event.ip_address ? ` · ${event.ip_address}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
