import type { Metadata } from "next";

import { NoAccountServer } from "@/components/Form";
import { OAuthButtons } from "@/components/OAuthButtons";
import { accountsAvailable } from "@/lib/account";

import { SignUpForm } from "./SignUpForm";

export const metadata: Metadata = { title: "Create an account" };

export default function SignUpPage() {
  return (
    <div className="mx-auto max-w-md space-y-8">
      <div>
        <h1 className="display text-4xl sm:text-5xl">Create an account</h1>
        <p className="mt-3 text-fg-muted">
          We store an email address, a hashed password, and which devices you have added. Nothing
          else — your AI stays on your own computer.
        </p>
      </div>
      {accountsAvailable() ? (
        <>
          <OAuthButtons />
          <SignUpForm />
        </>
      ) : (
        <NoAccountServer />
      )}
    </div>
  );
}
