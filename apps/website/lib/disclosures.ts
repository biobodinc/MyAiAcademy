/** Single source for the disclosures shown on the website. Mirror README.md. */
export const DISCLOSURES = [
  {
    title:
      "Catalog models have not yet been downloaded and run by the authors on consumer hardware.",
    body: "The real llama.cpp runtime is exercised end to end in the test suite (loading, chat templating, streaming, benchmarking and unloading) with a small synthetic model, and downloads are verified against a local server. What remains unconfirmed is the full path with a catalog model from Hugging Face on an ordinary PC: the environment the code was written in could not reach Hugging Face. Any failure is reported in the app rather than hidden.",
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
