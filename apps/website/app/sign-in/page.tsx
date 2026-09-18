import type { Metadata } from "next";

import { NoAccountServer } from "@/components/Form";
import { OAuthButtons } from "@/components/OAuthButtons";
import { accountsAvailable } from "@/lib/account";

import { SignInForm } from "./SignInForm";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <div className="mx-auto max-w-md space-y-8">
      <div>
        <h1 className="display text-4xl sm:text-5xl">Sign in</h1>
        <p className="mt-3 text-fg-muted">
          An account is how you get installers and add more than one device. It never receives your
          conversations, memories or documents.
        </p>
      </div>
      {accountsAvailable() ? (
        <>
          <OAuthButtons />
          <SignInForm />
        </>
      ) : (
        <NoAccountServer />
      )}
    </div>
  );
}
