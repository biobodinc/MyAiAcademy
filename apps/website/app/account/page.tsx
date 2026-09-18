import type { Metadata } from "next";

import { NoAccountServer } from "@/components/Form";
import { accountsAvailable } from "@/lib/account";

import { AccountView } from "./AccountView";

export const metadata: Metadata = { title: "Your account" };

export default function AccountPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="display text-4xl sm:text-5xl">Your account</h1>
      {accountsAvailable() ? <AccountView /> : <NoAccountServer />}
    </div>
  );
}
