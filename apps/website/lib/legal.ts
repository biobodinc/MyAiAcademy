// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
/**
 * The facts the legal pages need that live outside the code.
 *
 * These are gathered here rather than written into the prose because every one of them is a
 * decision only the publisher can make, and because getting one wrong should be a one-line
 * change rather than a hunt through two documents. `reviewed` gates a banner on both pages:
 * while it is false they say they are a draft that no lawyer has read, which is the truthful
 * state of any document generated rather than advised.
 */
export const LEGAL = {
  /**
   * The party the contract is with. A registered company limits personal liability in a way
   * no wording in a terms document can; an individual trading under a name does not.
   */
  entity: "Biobodinc",
  entityKind: "individual" as "individual" | "company",

  /**
   * Governing law and the courts that hear a dispute. Deliberately blank rather than filled
   * with a plausible guess: for an individual publisher the defensible choice is the state you
   * actually live in, because a forum with no real connection to either party is the kind of
   * clause a court disregards. Naming the wrong state makes this weaker than naming none, so
   * it renders as a visible placeholder until the real one is known.
   */
  jurisdiction: "",
  courts: "",

  /** Where legal, privacy and security notices are received. */
  contactEmail: "MyAIcontact@biobod.net",
  privacyEmail: "MyAIcontact@biobod.net",
  securityEmail: "MyAIcontact@biobod.net",

  /**
   * 13 is the floor set by COPPA in the United States; the EU's GDPR lets member states set
   * the digital-consent age anywhere from 13 to 16, so 16 is the safe number there.
   */
  minimumAge: 13,
  minimumAgeEea: 16,

  effectiveDate: "2026-10-01",
  lastUpdated: "2026-10-01",

  /** Flip to true only once a lawyer has actually read these. */
  reviewed: false,
} as const;
