# The `.myai` portable package format

Status: **implemented** (Phase 8). `myai_core.portable` writes and reads this; the tests in
`packages/myai-core/tests/test_portable.py` are the specification in executable form.

## Goals

- A user can carry their AI (identity, personality, skills, memory, conversations,
  knowledge) to another machine, or keep it as a backup (spec §23–§27).
- The format is documented enough for the owner to understand what is inside.
- Integrity is verifiable; encryption is optional and strong.
- A package that has been damaged is refused, not partly applied.

## Layout

A `.myai` file is a ZIP archive:

```
<name>.myai
├── myai.json                        plain: format version and how the package is locked
├── manifest.myai                    the manifest (encrypted when a password is set)
├── identity/profile.json
├── skills/state.json
├── memory/memories.json
├── conversations/conversations.json
├── conversations/messages.json
├── knowledge/documents.json         metadata; the files themselves are not carried yet
├── settings/preferences.json
└── models/models.json               references, never weights
```

### `myai.json` — the only plaintext

```json
{
  "format": "myai-package",
  "format_version": 1,
  "encryption": {
    "enabled": true,
    "cipher": "aes-256-gcm",
    "kdf": {
      "algorithm": "argon2id",
      "salt": "…",
      "memory_kib": 262144,
      "iterations": 3,
      "lanes": 4
    }
  },
  "manifest_sha256": null
}
```

**This differs from the Phase 1 draft, deliberately.** The draft kept the whole manifest in
the clear and signed it. That would tell anyone who found the drive the AI's name, every
skill it has and how good it is at each — which is most of what a person would want to keep
private about it. Only what is needed to _attempt_ opening the file stays outside the
encryption, and none of it says anything about the owner.

`manifest_sha256` is present only for an unencrypted package; when locked, the AEAD tag is
the stronger check and a separate digest would add nothing.

### `manifest.myai`

```json
{
  "format_version": 1,
  "ai": { "id": "myai_01H…", "name": "Nova", "created_at": "…" },
  "exported_at": "…",
  "exported_by": { "app_version": "0.1.0", "device_id": "dev_…" },
  "models": [{ "id": "…", "license": "…", "included": false, "size_bytes": 0, "reason": "…" }],
  "skills": [{ "id": "coding", "level": 12, "status": "learned" }],
  "requirements": { "min_ram_bytes": 0, "backends": ["cpu"] },
  "counts": { "memory/memories.json": 14 },
  "integrity": { "algorithm": "sha256", "files": { "identity/profile.json": "…" } }
}
```

## Integrity

Every entry is listed with the SHA-256 of **the bytes stored in the archive** — after
encryption, not before. That ordering matters: a package corrupted on a drive is detected
without needing the password, so "this file has rotted" and "you typed the wrong password"
are different messages.

`open_package` verifies the whole archive before returning, and refuses:

- an entry whose digest does not match;
- an entry listed in the manifest but missing from the archive;
- an entry present in the archive that the manifest does not list — an archive assembled by
  something other than this program is not opened.

## Encryption (when a password is set)

- **Key derivation: Argon2id**, parameters recorded in the header so a package written today
  still opens when the defaults are raised. A password is short and human, so the defence
  against offline guessing has to be memory-hard; PBKDF2 and scrypt at ordinary settings are
  far cheaper to attack with a GPU.
- **Content: AES-256-GCM**, one nonce per entry, prepended. GCM authenticates as well as
  encrypts, so an altered package fails to open rather than opening subtly wrong.
- **The entry's path is bound in as associated data.** A file cannot be swapped for another
  from the same package: `memory/memories.json` will not decrypt in the place of
  `identity/profile.json` even though both were sealed with the same key.
- The password is never stored, and the derived key is never written anywhere.

## What is deliberately not in a package

- **Credentials.** The installation token and every paired device's key are access grants,
  not data. A package containing them would be a key left under the mat.
- **Model weights.** Large, publicly downloadable, and their licences generally do not permit
  passing them on. The manifest records what to fetch and the importer re-downloads with the
  licence shown.
- **Knowledge file contents.** Only document metadata travels today. Carrying the files needs
  a size budget and a story for large archives, and is not done.
- **Sync state.** A restored installation gets a _new_ sync identity — see below.

## Import

`preview_import` reports a verdict per capability against the local hardware report, and
says it before anything is changed:

| Verdict       | Meaning                                                                           |
| ------------- | --------------------------------------------------------------------------------- |
| `supported`   | Works here. Records — memories, conversations, levels — always do.                |
| `stored_only` | Comes across, but will not run on this machine (e.g. a model larger than memory). |
| `missing`     | Referenced but not present; it is downloaded again, with its licence shown.       |

Importing **replaces** the AI on this machine. Restoring a backup and merging two machines
are different operations with different right answers, and quietly doing the second when the
user asked for the first would lose the thing they were restoring. The API requires the
phrase `REPLACE MY AI` typed exactly, as the Privacy Center's erase does.

### A restored installation is a new device

This closes the gap ADR-0016 recorded. A sync identity is a counter plus an id, and peers
remember how far through that counter they have read. A database restored from a backup has
a _lower_ counter than its peers remember, so every change it went on to make would be
silently skipped — exactly the class of failure sync is built to avoid.

So an import clears the sync identity, the peer cursors, the tombstones and the conflict
records, and a fresh identity is generated. The restored copy looks like a new device to the
others, because that is what it is, and it has to be paired with them again.
