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
    title: "Training does not change your model's weights.",
    body: "/train searches for better instructions for one skill \u2014 short rules from its package, rules your AI writes for itself after a mistake, and worked examples \u2014 and keeps a change only when it scores higher on practice tasks that the benchmark never uses. When the search ends, the skill's benchmark runs with the old and the new instructions, and the result is kept only if the score went up; if it did not, the run says so and nothing changes. Fine-tuning a quantised local model is not something this program can honestly do on the hardware it targets, so it does not claim to.",
  },
  {
    title: "Creative skills cannot be learned or trained yet.",
    body: "Images, video, music and games have no measurable benchmark in this build, so they cannot be learned or trained, and every surface says so rather than showing a level.",
  },
  {
    title: "Your AI is reachable from your network only if you turn that on.",
    body: "By default the service listens on 127.0.0.1 and nothing on your network can reach it. If you allow devices, it starts a second listener that is HTTPS only, with a certificate your device pins when it pairs \u2014 so the device accepts that one computer and no other, with no certificate authority involved. This installation's own token is refused over the network: a device uses its own credential, which you can revoke on its own. Turning access on and off is recorded in the audit log.",
  },
  {
    title: "The phone app cannot connect to your computer yet.",
    body: "The computer side is built and tested: the listener, the certificate, the pairing code and the QR that carries the fingerprint to pin. The phone side is not finished, because pinning a self-signed certificate in React Native needs a native module and a device build, and we will not ship a connection that has never been made on real hardware. The app reports itself unpaired, which is the truth.",
  },
  {
    title: "The account server exists in the repository, but is not running anywhere.",
    body: "An account server is now written and tested \u2014 sign-up with email confirmation, sign-in with a password or with Google, Apple or Facebook, device pairing and revocation \u2014 and this site has pages for it. Nothing is deployed: the published site is built without an account server configured, so those pages say there is none rather than showing a form that posts into the void. The desktop app and the command line still have no account code path at all. When it does run, it will hold an email address, a hashed password, which devices you have added, and a log of account activity \u2014 never your conversations, memories, files or model weights.",
  },
  {
    title: "Pairing grants access to programs on your machine, not to other machines.",
    body: "The local service listens on 127.0.0.1 only, so nothing on your network can reach it. Each paired client holds its own credential that you can revoke on its own, and only the installation itself can grant access, revoke it, export your data or erase it. Credentials are stored as SHA-256 hashes and shown once.",
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
