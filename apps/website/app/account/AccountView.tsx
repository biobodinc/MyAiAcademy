"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Notice } from "@/components/Form";
import { type Account, ApiError, api, clearToken, storedToken } from "@/lib/account";

import { Activity } from "./Activity";
import { ChangePassword } from "./ChangePassword";
import { Devices } from "./Devices";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border pt-8">
      <h2 className="display text-2xl sm:text-3xl">{title}</h2>
      {children}
    </section>
  );
}

export function AccountView() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [resent, setResent] = useState<string | null>(null);

  useEffect(() => {
    const stored = storedToken();
    if (!stored) {
      router.replace("/sign-in");
      return;
    }
    api
      .me(stored)
      .then((loaded) => {
        setToken(stored);
        setAccount(loaded);
      })
      .catch((caught) => {
        // A session that the server no longer honours is worth clearing here, or every
        // page load retries a token that cannot work.
        if (caught instanceof ApiError && caught.status === 401) clearToken();
        router.replace("/sign-in");
      });
  }, [router]);

  if (!token || !account) return <p className="text-fg-muted">Loading…</p>;

  async function signOut() {
    if (token) await api.signOut(token).catch(() => undefined);
    clearToken();
    router.push("/");
  }

  return (
    <div className="space-y-12">
      <section>
        <dl className="border-t border-border">
          <div className="flex justify-between gap-6 border-b border-border py-3">
            <dt className="text-fg-muted">Email</dt>
            <dd className="text-right">{account.email ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-6 border-b border-border py-3">
            <dt className="text-fg-muted">Account number</dt>
            <dd className="datum text-right">{account.account_id}</dd>
          </div>
          <div className="flex justify-between gap-6 border-b border-border py-3">
            <dt className="text-fg-muted">Member since</dt>
            <dd className="datum text-right">
              {new Date(account.created_at).toLocaleDateString()}
            </dd>
          </div>
        </dl>

        {account.email_verified ? null : (
          <div className="mt-6 border-l-2 border-accent py-1 pl-5">
            <p className="datum text-accent uppercase">Email not confirmed</p>
            <p className="mt-2 max-w-md text-sm text-fg-muted">
              We sent a link to {account.email}. Follow it to confirm the address is yours.
            </p>
            <button
              type="button"
              onClick={() =>
                api
                  .resendVerification(token!)
                  .then((r) => setResent(r.detail))
                  .catch(() => setResent("Could not send it. Try again in a moment."))
              }
              className="mt-3 text-sm text-accent underline underline-offset-4"
            >
              Send it again
            </button>
            {resent ? (
              <div className="mt-3">
                <Notice kind="info">{resent}</Notice>
              </div>
            ) : null}
          </div>
        )}
      </section>

      <Section title="Devices">
        <p className="mt-3 max-w-xl text-fg-muted">
          Each device you add holds its own session. Revoking one stops it immediately rather than
          whenever its session would have run out.
        </p>
        <Devices token={token} />
      </Section>

      <Section title="Password">
        <p className="mt-3 max-w-xl text-fg-muted">
          Changing it signs out every other session, which is the point of changing it.
        </p>
        <ChangePassword token={token} />
      </Section>

      <Section title="Activity">
        <p className="mt-3 max-w-xl text-fg-muted">
          Everything done to this account, newest first — including attempts that failed.
        </p>
        <Activity token={token} />
      </Section>

      <section className="border-t border-border pt-8">
        <button
          type="button"
          onClick={signOut}
          className="rounded-sharp border border-fg px-5 py-2.5 font-medium transition-colors hover:bg-fg hover:text-bg"
        >
          Sign out
        </button>
      </section>
    </div>
  );
}
