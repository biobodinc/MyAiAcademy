# ADR-0012 Only a promised hash may fail a download

## Context

A user's first real model download failed with "Integrity check failed: the downloaded
file does not match the host-declared SHA-256. The partial file was deleted." The file was
almost certainly fine.

`models/download.py` accepted any `ETag` matching `^[0-9a-f]{64}$` as the file's SHA-256.
That holds for Hugging Face's classic LFS CDN. It does not hold for its Xet-backed CDN,
which serves a content-addressed identifier of the same shape that is not the file's hash.
HTTP itself only defines `ETag` as an opaque validator; nothing entitles a client to read
it as a digest. The consequence was the worst kind of dishonesty available to this code: a
correct download declared corrupt, and gigabytes deleted, with no way for the user to tell
which of the two had gone wrong.

## Decision

Distinguish hashes a publisher _promises_ from values that merely look like hashes.

- **May fail a download**: a hash pinned in the catalog (`pinned`), or `X-Linked-Etag`
  (`publisher-hash`), which Hugging Face documents as the LFS object's SHA-256. It is set
  on Hugging Face's own response, so it is read from the redirect history rather than the
  CDN response that finally serves the bytes. `X-Linked-Size` is preferred over the CDN's
  `Content-Length` for the same reason.
- **May never fail a download**: a bare `ETag`. If it happens to equal what we computed we
  record `host-etag` as extra confidence; if it differs we ignore it.
- **Otherwise** the result is `none`: the transfer is checked for completeness only.

What was verified is stored on the installed model (migration 0005) and shown as such.
Previously the UI displayed a SHA-256 for every installed model, which read as "verified"
when it only meant "this is what we computed".

An integrity failure now names both hashes and which promise was broken, and
`GET /api/models/{id}/source` (`myai models check <id>`) reports what a host declares
without downloading anything, so this class of problem is diagnosable from the outside.

## Consequences

- Catalog models whose publisher exposes no content hash install as **unverified**. That
  is a real reduction in assurance and is stated in the README, the website disclosures
  and the app, rather than papered over.
- Pinning SHA-256 values in the catalog restores strict verification per model. The
  authors could not reach Hugging Face from the development environment to obtain them;
  `myai models check` prints the hash to pin when a publisher does expose one.
- Deleting the file on a genuine mismatch is kept: a model that fails a promised hash must
  not linger on disk.
