# The `.myai` portable package format (draft, Phase 8)

Status: **design draft**. Nothing in Phase 1 reads or writes this format. It is documented
now because the storage layout created in Phase 1 is intentionally the same shape, so
export becomes "copy plus manifest" rather than a migration.

## Goals

- A user can carry their AI (identity, personality, skills, memory, knowledge, adapters,
  checkpoints, projects) to another compatible machine or keep it as a backup (spec §23–§27).
- The format is documented enough for the owner to understand what is inside.
- Integrity is verifiable; encryption is optional and strong.
- The reference implementation is the official app; third-party editing is discouraged.

## Layout

```
<name>.myai/                 (a directory; optionally packed as a single archive)
├── manifest.myai            JSON, UTF-8
├── identity/                ai_id, name, personality, preferences
├── model/                   base model references and any locally permitted weights
├── skills/                  per-skill packages, levels, evaluation records
├── memory/
├── knowledge/
├── training/
├── checkpoints/
├── projects/
└── settings/
```

## `manifest.myai`

```json
{
  "format_version": 1,
  "ai": { "id": "myai_01H…", "name": "Nova", "created_at": "…" },
  "exported_at": "…",
  "exported_by": { "app_version": "0.1.0", "device_id": "dev_…" },
  "models": [{ "id": "…", "license": "…", "included": false, "size_bytes": 0 }],
  "skills": [{ "id": "coding", "level": 12, "last_evaluation": "…" }],
  "requirements": { "min_ram_bytes": 0, "min_vram_bytes": 0, "backends": ["cuda"] },
  "encryption": { "enabled": false },
  "integrity": { "algorithm": "sha256", "files": { "identity/profile.json": "…" } }
}
```

## Integrity

Every file is listed with a SHA-256 digest. The manifest itself is signed with a key
derived from the package password when encryption is enabled; otherwise a detached
digest of the manifest is stored alongside it.

## Encryption (when enabled)

- Key derivation: Argon2id with parameters recorded in the manifest.
- Content encryption: XChaCha20-Poly1305 (or AES-256-GCM where hardware acceleration
  dictates), per-file, with the file path bound as associated data.
- Libraries: audited implementations only (`cryptography` / libsodium). No custom
  cryptography.
- The password is never stored. Hardware-backed key storage is used where available to
  cache an unlocked key for the session.

## Compatibility checks on import (spec §77)

The importer compares `requirements` and each model's backend needs with the local
hardware report and presents a per-capability verdict (Supported / Stored but cannot run
here / Missing). Unsupported models are never executed.

## Licensing

Model files are only included when their licence permits redistribution to the same
user; otherwise the manifest records a reference and the importer re-downloads with the
licence shown.
