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
    title: "Training is not implemented (Phase 4).",
    body: "Skills are learned from bundled packages (instructions plus a 12-task benchmark) and a skill's level is the score its benchmark produced with your local model. /train shows its information and states that training jobs arrive in Phase 4. Creative skills (images, video, music, games) have no benchmark yet and cannot be learned.",
  },
  {
    title: "Not every model download can be hash-verified.",
    body: "A download is only failed when it disagrees with a hash the publisher actually promises (a hash pinned in our catalog, or Hugging Face's X-Linked-Etag header). A plain ETag is an opaque validator rather than a content hash, so it is never used to reject a file. Where no published hash exists the download is checked for completeness only, and the app labels that model \u201cunverified\u201d rather than implying it was checked.",
  },
  {
    title: "The coding benchmark executes code written by your local model.",
    body: "It runs in a separate interpreter with an import allow-list, a scratch directory, a timeout and resource limits. That contains accidents; it is not a security boundary against a hostile model, so treat imported models with the same care as any software you run.",
  },
  {
    title: "Network activity is limited.",
    body: "An internet reachability check (a TCP connect with no payload) and model downloads you start after accepting a licence. Nothing you write, remember or add to knowledge leaves your machine.",
  },
] as const;

export const DISCLOSURES_UPDATED = "2026-09-11";
