// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import type { Metadata } from "next";
import Link from "next/link";

import { LegalDoc, type Clause } from "@/components/LegalDoc";
import { LEGAL } from "@/lib/legal";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "What MyAI Academy collects, which is almost nothing, and what happens to the little it does.",
};

/**
 * Written from the code rather than from a template. Every claim here is checkable: the
 * desktop service binds to loopback, the account server's tables are the list in clause 3,
 * there is no analytics script on this site and no cookie is set by it. A policy that
 * overstates what is collected is merely vague; one that understates it is a deceptive
 * practice, so the specifics matter more than the coverage.
 */
const clauses: Clause[] = [
  {
    heading: "Who this is and what it covers",
    body: (
      <>
        <p>
          {SITE.name} is published by {LEGAL.entity}. This policy covers this website and the
          account service it talks to. It does not cover what you do inside the desktop application
          or the command line, because, as clause 2 explains, that does not reach us.
        </p>
        <p>
          For privacy questions or to exercise any right below, write to{" "}
          <a className="underline" href={`mailto:${LEGAL.privacyEmail}`}>
            {LEGAL.privacyEmail}
          </a>
          .
        </p>
      </>
    ),
  },
  {
    heading: "The software on your computer sends us nothing",
    body: (
      <>
        <p>
          Your conversations, memories, knowledge documents, training data, model weights and
          personality settings are written to disk on your own machine and are never transmitted to
          us. There is no account code path in the desktop build at all, so there is nothing for it
          to transmit them to.
        </p>
        <p>
          The local service listens on 127.0.0.1 and refuses connections from anywhere else unless
          you explicitly turn on access for your own devices. Its only unprompted outbound network
          activity is a TCP connection opened and closed to test whether the internet is reachable,
          so the app can show online or offline. It carries no payload. Model downloads happen when
          you ask for them, from the publisher of that model, after you have been shown its licence.
        </p>
        <p>
          We therefore hold no copy of your AI, and could not produce one in response to a legal
          demand. That is a property of the architecture, not a promise about our conduct.
        </p>
      </>
    ),
  },
  {
    heading: "What the account service stores, if you create an account",
    body: (
      <>
        <p>
          Accounts are optional and exist only to register which of your devices may pair with each
          other. If you create one, the service stores:
        </p>
        <ul className="list-disc space-y-1 pl-6">
          <li>your email address, and whether and when you confirmed it;</li>
          <li>
            a hash of your password — the password itself is never stored, and cannot be recovered
            from the hash;
          </li>
          <li>
            if you sign in with Google, Apple or Facebook instead, the name of that provider and the
            identifier it gives us for you, rather than a password;
          </li>
          <li>
            a name and identifier for each device you add, when it was last seen, and whether you
            have revoked it;
          </li>
          <li>short-lived pairing codes, when they expire, and how many times one was mistyped;</li>
          <li>
            a hash of each active sign-in session, so a session can be ended without us holding the
            token itself;
          </li>
          <li>
            a security log of account events — signing in, adding or revoking a device, changing a
            password — recording the event, the device, the time, and the{" "}
            <strong className="text-fg">IP address and browser user-agent</strong> the request came
            from.
          </li>
        </ul>
        <p>
          That last item is the only thing here you did not type. It is kept because an account
          security log that cannot tell you where a sign-in came from is not much of a security log.
          It is not used for analytics, advertising or profiling.
        </p>
      </>
    ),
  },
  {
    heading: "What we do not do",
    body: (
      <>
        <p>
          This website sets no cookies. It loads no analytics, no tag manager, no advertising pixel
          and no third-party script that could track you. There is nothing to consent to, which is
          why you are not being asked.
        </p>
        <p>
          When you are signed in, your session token is held in your browser&apos;s{" "}
          <code>localStorage</code> on this site&apos;s own origin and sent as an authorisation
          header. It is strictly necessary to keep you signed in, it is removed when you sign out,
          and it is not readable by any other site.
        </p>
        <p>
          We do not sell or share personal information, and we do not profile you or make automated
          decisions about you. Under the CCPA and CPRA we have no sale or sharing to opt out of.
        </p>
      </>
    ),
  },
  {
    heading: "Why we are allowed to hold it",
    body: (
      <>
        <p>
          Where the GDPR or UK GDPR applies, our lawful bases are: performing the contract you
          entered into by creating an account, for your email address, credentials and device
          records; and our legitimate interest in the security of your account, for the security
          log, including the IP address and user-agent. We do not rely on consent for any of it,
          because none of it is optional to the service it provides.
        </p>
      </>
    ),
  },
  {
    heading: "Who else sees it",
    body: (
      <>
        <p>
          No one buys it, and we employ no advertising or analytics processors. The service
          providers involved are limited to those needed to run it:
        </p>
        <ul className="list-disc space-y-1 pl-6">
          <li>
            the hosting provider that serves this website and the account service, and the database
            it runs on;
          </li>
          <li>
            Google, Apple or Facebook — only if you choose to sign in with one of them, in which
            case that provider knows you signed in here;
          </li>
          <li>
            an email provider, when one is configured, to send a confirmation link. At the time of
            writing none is: the server has no mail provider wired up and writes confirmation links
            to its own log instead, which is why sign-up tells you so rather than claiming to have
            sent mail.
          </li>
        </ul>
        <p>
          We will disclose information if legally compelled, and we would rather be in a position
          where the compelled answer is &ldquo;we do not have it&rdquo;, which for everything in
          clause 2 it is.
        </p>
      </>
    ),
  },
  {
    heading: "How long it is kept",
    body: (
      <>
        <p>
          Account records are kept until you delete the account, after which they are removed.
          Pairing codes expire within minutes and are deleted after they expire or are used. Session
          records are deleted when you sign out or when they expire. Security log entries are kept
          while the account exists, because their value is historical.
        </p>
      </>
    ),
  },
  {
    heading: "Your rights",
    body: (
      <>
        <p>
          Whatever jurisdiction you are in, you may ask us for a copy of what we hold about you, ask
          us to correct it, or ask us to delete it and the account with it. Under the GDPR you
          additionally have rights to restrict or object to processing, to portability, and to
          complain to your national data protection authority. Under the CCPA and CPRA you have
          rights to know, delete, correct and to non-discrimination for exercising them.
        </p>
        <p>
          Write to{" "}
          <a className="underline" href={`mailto:${LEGAL.privacyEmail}`}>
            {LEGAL.privacyEmail}
          </a>
          . We will not charge you and will not treat you differently for asking.
        </p>
        <p>
          Separately, and needing no request to us: the desktop application&apos;s Privacy Centre
          exports everything it holds to a file, or erases all of it, on your own machine. Nothing
          about that goes through us.
        </p>
      </>
    ),
  },
  {
    heading: "Children",
    body: (
      <>
        <p>
          Accounts are not for children. You must be at least {LEGAL.minimumAge} years old to create
          one, or at least {LEGAL.minimumAgeEea} in the European Economic Area and the United
          Kingdom. We do not knowingly collect personal information from a child below those ages,
          and if we learn that we have, we will delete the account and its records. If you believe a
          child has created an account, write to{" "}
          <a className="underline" href={`mailto:${LEGAL.privacyEmail}`}>
            {LEGAL.privacyEmail}
          </a>{" "}
          and we will remove it.
        </p>
        <p>
          The desktop application does not require an account, and a parent installing it for a
          child should understand that in that case nothing is collected by us at all.
        </p>
      </>
    ),
  },
  {
    heading: "Where it is processed",
    body: (
      <p>
        The account service and this website are hosted in the United States. If you are outside the
        United States, using an account means your information is transferred there. Where the GDPR
        applies, such transfers rely on the European Commission&apos;s standard contractual clauses
        as implemented by our hosting providers.
      </p>
    ),
  },
  {
    heading: "Security, and its limits",
    body: (
      <>
        <p>
          Passwords are stored only as hashes. Session tokens are stored only as hashes. Connections
          to this site and the account service are encrypted in transit. Device pairing uses a
          certificate your device pins, so a paired device trusts exactly one computer and no
          certificate authority is involved.
        </p>
        <p>
          No system is immune, and promising otherwise would be the least credible sentence in this
          document. If you find a vulnerability, please tell us at{" "}
          <a className="underline" href={`mailto:${LEGAL.securityEmail}`}>
            {LEGAL.securityEmail}
          </a>{" "}
          rather than publishing it first; we will not pursue you for a good-faith report.
        </p>
      </>
    ),
  },
  {
    heading: "Changes",
    body: (
      <p>
        If this policy changes, the date at the top changes with it. If a change means we start
        collecting something we did not collect before, we will say so plainly rather than relying
        on you to re-read the document, and the{" "}
        <Link className="underline" href="/disclosures">
          disclosures
        </Link>{" "}
        will say it too.
      </p>
    ),
  },
];

export default function PrivacyPolicyPage() {
  return (
    <LegalDoc
      title="Privacy Policy"
      summary={
        <>
          The short version: the application on your computer sends us nothing, this website sets no
          cookies and runs no analytics, and the only personal information we ever hold is what you
          type into an optional account. The{" "}
          <Link className="underline" href="/privacy">
            privacy promise
          </Link>{" "}
          says the same thing in fewer words; this is the version that has to hold up.
        </>
      }
      clauses={clauses}
    />
  );
}
