// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import type { Metadata } from "next";
import Link from "next/link";

import { LegalDoc, Unset, type Clause } from "@/components/LegalDoc";
import { LEGAL } from "@/lib/legal";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The agreement for using MyAI Academy, and the limits of what it promises.",
};

/**
 * The clauses that carry real weight for this product are 5, 6 and 8: a local model's output
 * is unreviewed text that people will be tempted to act on, the models themselves arrive under
 * other people's licences, and the software is given away free. Boilerplate about account
 * suspension matters much less here than any of those.
 */
const clauses: Clause[] = [
  {
    heading: "Agreeing to this",
    body: (
      <>
        <p>
          These terms are an agreement between you and {LEGAL.entity}, the publisher of {SITE.name}.
          By installing or using the software, or by creating an account on this site, you accept
          them. If you do not accept them, do not use it.
        </p>
        <p>
          You must be at least {LEGAL.minimumAge} years old, or {LEGAL.minimumAgeEea} in the
          European Economic Area and the United Kingdom. If you are using this on behalf of an
          organisation, you are confirming you may bind it.
        </p>
      </>
    ),
  },
  {
    heading: "What you are given",
    body: (
      <>
        <p>
          The source code of {SITE.name} is licensed under the Apache License, Version 2.0. That
          licence governs the code and grants you its rights directly; nothing in these terms
          reduces them. Where these terms and that licence disagree about the code, the licence
          wins.
        </p>
        <p>
          These terms cover the things the licence does not: the account service, this website, and
          the published builds as a service we operate rather than as source you compile.
        </p>
        <p>
          The name {SITE.name} and its branding are not granted to you. The Apache licence is
          explicit that it does not grant trademark rights, and this is a reminder, not an
          additional restriction.
        </p>
      </>
    ),
  },
  {
    heading: "Your AI and your data are yours",
    body: (
      <>
        <p>
          We claim no ownership of anything you create with this software — your conversations, your
          memories, your documents, your trained skill configurations, your exported{" "}
          <code>.myai</code> package. We do not hold copies of them and we do not want them. You are
          responsible for backing them up; the software can export them, and the{" "}
          <Link className="underline" href="/legal/privacy">
            privacy policy
          </Link>{" "}
          explains why we could not restore them for you.
        </p>
      </>
    ),
  },
  {
    heading: "How you may use it",
    body: (
      <>
        <p>You agree not to use {SITE.name}:</p>
        <ul className="list-disc space-y-1 pl-6">
          <li>to break the law, or to help anyone else break it;</li>
          <li>
            to generate material that sexually exploits children, incites violence, or harasses or
            defames a person;
          </li>
          <li>
            to attack the account service — probing it, overwhelming it, or trying to reach another
            person&apos;s account or devices;
          </li>
          <li>to pair with, or attempt to pair with, a computer you are not authorised to use;</li>
          <li>
            to present its output as a professional&apos;s advice, or as the output of a human,
            where that would mislead someone who is relying on it.
          </li>
        </ul>
        <p>
          The software runs on your own hardware, so in practice we cannot stop you doing any of
          this. That does not make it permitted, and it does not make it our responsibility.
        </p>
      </>
    ),
  },
  {
    heading: "What the AI says is not advice, and may be wrong",
    body: (
      <>
        <p>
          A language model produces text that reads like an answer whether or not it is one. The
          models this software runs are small enough to run on a personal computer, which makes them
          more likely to be wrong than the large hosted ones, not less.
        </p>
        <p>
          Nothing it produces is medical, legal, financial, psychological, safety or professional
          advice, and it is not a substitute for a qualified person. Do not rely on it for a
          decision that matters without checking it against a source that is accountable for being
          right. If you are in crisis or facing an emergency, contact a professional or emergency
          service, not this program.
        </p>
        <p>
          Skill levels and benchmark scores describe how a model performed on this software&apos;s
          own practice tasks. They are a measurement of that, and nothing more: they are not a
          qualification, a certification, an accreditation or a credential, and the word
          &quot;Academy&quot; in the name does not make them one.
        </p>
        <p>
          You are responsible for what you do with the output, and for anything you publish or act
          on that came from it.
        </p>
      </>
    ),
  },
  {
    heading: "Models and other people's licences",
    body: (
      <>
        <p>
          The AI models this software can download are not ours. Each is published by a third party
          under its own licence, which the application shows you before it downloads anything, and
          which you are agreeing to with that publisher rather than with us. Some restrict
          commercial use. Some restrict particular fields of use. Reading the licence is your
          responsibility and the application&apos;s job is to put it in front of you.
        </p>
        <p>
          We do not warrant any model, its output, its licence terms, or its continued availability.
          A model you import yourself is software you chose to run, and the same care applies as to
          any other program you install.
        </p>
      </>
    ),
  },
  {
    heading: "The account service, while it exists",
    body: (
      <>
        <p>
          Accounts are optional, free, and offered as they are. We may change, suspend or
          discontinue the account service, and we may suspend or close an account that is being used
          to attack the service or in breach of clause 4. The software keeps working without an
          account; losing one costs you device pairing, not your AI.
        </p>
        <p>
          Keep your password to yourself. You are responsible for what is done through your account,
          and the security log in the application will show you what that was.
        </p>
      </>
    ),
  },
  {
    heading: "No warranty",
    body: (
      <>
        <p>
          The software and the account service are provided &quot;as is&quot; and &quot;as
          available&quot;, without warranty of any kind, express or implied, including any implied
          warranty of merchantability, fitness for a particular purpose, title or non-infringement.
          We do not warrant that it will be uninterrupted, error-free, secure, or that it will
          produce any particular result.
        </p>
        <p>
          Builds are not signed by a certificate authority, which means your operating system will
          warn you about them and you are choosing to proceed. The{" "}
          <Link className="underline" href="/download">
            download page
          </Link>{" "}
          publishes a SHA-256 for every file so you can verify you received what we published, and
          checking it is the protection available to you.
        </p>
        <p>
          Some jurisdictions do not allow the exclusion of implied warranties, so parts of this
          clause may not apply to you.
        </p>
      </>
    ),
  },
  {
    heading: "Limitation of liability",
    body: (
      <>
        <p>
          To the fullest extent the law allows, {LEGAL.entity} is not liable for any indirect,
          incidental, special, consequential or punitive damages, nor for lost profits, lost data,
          lost model weights, or business interruption, arising from your use of or inability to use{" "}
          {SITE.name} — including anything done in reliance on its output.
        </p>
        <p>
          Our total liability for all claims relating to {SITE.name} is limited to the greater of
          the amount you paid us in the twelve months before the claim, or twenty United States
          dollars. {SITE.name} is free, so in most cases that figure is twenty dollars, and saying
          so plainly is fairer than implying there is more.
        </p>
        <p>
          Nothing here excludes liability that cannot lawfully be excluded, including for death or
          personal injury caused by negligence, or for fraud. Some jurisdictions do not allow these
          limits, so parts of this clause may not apply to you.
        </p>
      </>
    ),
  },
  {
    heading: "Indemnity",
    body: (
      <p>
        You agree to indemnify {LEGAL.entity} against claims, damages and reasonable legal costs
        arising from your use of {SITE.name} in breach of these terms, or from content you generated
        with it and then published or acted upon.
      </p>
    ),
  },
  {
    heading: "Export and sanctions",
    body: (
      <p>
        You may not use or export {SITE.name} in breach of applicable export-control or sanctions
        law, and you confirm you are not located in, or acting for anyone in, a territory subject to
        comprehensive sanctions.
      </p>
    ),
  },
  {
    heading: "Governing law and disputes",
    body: (
      <>
        <p>
          These terms are governed by the laws of{" "}
          {LEGAL.jurisdiction || <Unset>publisher&apos;s state or country of residence</Unset>},
          without regard to its conflict-of-laws rules. Any dispute will be heard in{" "}
          {LEGAL.courts || <Unset>the courts of that place</Unset>}, and you and we each consent to
          that.
        </p>
        <p>
          If you are a consumer in the European Economic Area or the United Kingdom, nothing here
          deprives you of the protection of the mandatory law of your country of residence, or of
          your right to bring proceedings there.
        </p>
      </>
    ),
  },
  {
    heading: "Changes, and the rest",
    body: (
      <>
        <p>
          We may change these terms; the date at the top will change with them, and continuing to
          use the software after that means accepting the new version. If a change materially
          reduces your rights, we will say so rather than hoping you do not notice.
        </p>
        <p>
          If a clause is unenforceable, the rest stands. Not enforcing something once does not waive
          it. These terms, with the Apache licence and the{" "}
          <Link className="underline" href="/legal/privacy">
            privacy policy
          </Link>
          , are the whole agreement between us about {SITE.name}.
        </p>
        <p>
          Questions:{" "}
          <a className="underline" href={`mailto:${LEGAL.contactEmail}`}>
            {LEGAL.contactEmail}
          </a>
          .
        </p>
      </>
    ),
  },
];

export default function TermsPage() {
  return (
    <LegalDoc
      title="Terms of Service"
      summary={
        <>
          The code is Apache-2.0 and these terms do not take that away. What they do say is that the
          software is free and given as it is, that a small local model is often wrong and its
          output is not advice, that the models you download belong to other people and carry their
          licences, and that what you make with it is yours.
        </>
      }
      clauses={clauses}
    />
  );
}
