/** Single source for the disclosures shown on the website. Mirror README.md. */
export const DISCLOSURES = [
  {
    title: "Local chat has not yet been exercised end to end with a real model by the authors.",
    body: "The environment the code was written in could not reach Hugging Face, so model downloads and generation were verified against a local test server and an injected fake inference backend. The real path is expected to work and reports any failure in the app, but treat it as unconfirmed until this line is removed.",
  },
  {
    title: "No signed installers are published yet.",
    body: "The release workflow builds Windows, macOS and Linux packages and CLI archives, but nothing has been signed, notarised or uploaded to GitHub Releases, Google Play or the App Store. Downloads say “Not available yet” until that happens.",
  },
  {
    title: "The mobile app is a skeleton.",
    body: "It shows its connection state truthfully (“not paired”) and nothing else. Pairing, chat and controls arrive in Phase 6.",
  },
  {
    title: "Knowledge retrieval is keyword-based, not semantic.",
    body: "It uses BM25 over SQLite full-text search and finds passages that share words with your question. Embedding-based retrieval is planned and will be labelled when it ships.",
  },
  {
    title: "Skills, levels and training are not implemented.",
    body: "The catalog and skill tree show what will be learnable; /learn and /train say so instead of doing anything.",
  },
  {
    title: "Network activity is limited.",
    body: "An internet reachability check (a TCP connect with no payload) and model downloads you start after accepting a licence. Nothing you write, remember or add to knowledge leaves your machine.",
  },
] as const;

export const DISCLOSURES_UPDATED = "2026-09-11";
