"""The `.myai` portable package: writing one, and reading one back (spec §23-§27, §77).

What this is for
----------------

A person should be able to put their AI on a drive, carry it to another machine, and have it
be the same AI — or keep the file as a backup and know it will still open in a year. That is
the whole promise, and it fails in two boring ways: the file is subtly corrupt and nobody
notices until it is needed, or it opens on the new machine and quietly does less than it did
on the old one without saying so.

So two things are non-negotiable here. **Every entry carries a SHA-256 and the whole package
is verified before a single row is imported** — a half-applied import is worse than a refused
one. And **the manifest records what the AI needed to run**, so the importer can say plainly
which parts will work on this machine rather than discovering it later.

Layout
------

A `.myai` file is a ZIP. Inside::

    myai.json             plain, tiny: format version and how the package is locked
    manifest.myai         the real manifest — encrypted when a password is set
    identity/profile.json
    skills/state.json
    projects/projects.json
    memory/memories.json
    conversations/*.json
    knowledge/documents.json
    settings/preferences.json
    models/models.json

The draft format note put the whole manifest in the clear. That is changed here: a plaintext
manifest would tell anyone who found the drive the AI's name, every skill it has and how good
it is at each. Only the few fields needed to *attempt* opening the file stay outside the
encryption — the format version and the key-derivation parameters, which reveal nothing.

Model weights are referenced, never copied. They are large, they are publicly downloadable,
and their licences frequently do not permit passing them on; the manifest lists what to fetch
and the importer re-downloads with the licence shown.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core import __version__
from myai_core.db import models
from myai_core.portable.crypto import KdfParams, WrongPasswordError, derive_key, new_params, seal
from myai_core.portable.crypto import unseal as unseal_entry

FORMAT = "myai-package"
FORMAT_VERSION = 1
HEADER_NAME = "myai.json"
MANIFEST_NAME = "manifest.myai"
SUFFIX = ".myai"


class PackageError(Exception):
    """The package could not be read, or is not one of ours."""


@dataclass(frozen=True, slots=True)
class Section:
    """One JSON document inside the package, and how it was produced."""

    path: str
    payload: Any


@dataclass(frozen=True, slots=True)
class Requirements:
    """What the AI needed where it came from, so the importer can be honest about here."""

    min_ram_bytes: int = 0
    backends: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {"min_ram_bytes": self.min_ram_bytes, "backends": list(self.backends)}

    @classmethod
    def from_json(cls, raw: dict[str, Any] | None) -> Requirements:
        data = raw or {}
        backends = data.get("backends")
        return cls(
            min_ram_bytes=int(data.get("min_ram_bytes") or 0),
            backends=tuple(str(b) for b in backends) if isinstance(backends, list) else (),
        )


@dataclass(frozen=True, slots=True)
class Manifest:
    """The package's self-description. Encrypted along with everything else when locked."""

    format_version: int
    ai: dict[str, Any]
    exported_at: datetime
    exported_by: dict[str, Any]
    models: list[dict[str, Any]]
    skills: list[dict[str, Any]]
    requirements: Requirements
    counts: dict[str, int]
    integrity: dict[str, str]
    """Entry path → SHA-256 of the bytes stored in the archive."""

    def to_json(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "ai": self.ai,
            "exported_at": self.exported_at.isoformat(),
            "exported_by": self.exported_by,
            "models": self.models,
            "skills": self.skills,
            "requirements": self.requirements.to_json(),
            "counts": self.counts,
            "integrity": {"algorithm": "sha256", "files": self.integrity},
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Manifest:
        try:
            integrity = raw.get("integrity") or {}
            files = integrity.get("files") if isinstance(integrity, dict) else {}
            return cls(
                format_version=int(raw["format_version"]),
                ai=dict(raw.get("ai") or {}),
                exported_at=datetime.fromisoformat(str(raw["exported_at"])),
                exported_by=dict(raw.get("exported_by") or {}),
                models=list(raw.get("models") or []),
                skills=list(raw.get("skills") or []),
                requirements=Requirements.from_json(raw.get("requirements")),
                counts={str(k): int(v) for k, v in (raw.get("counts") or {}).items()},
                integrity={str(k): str(v) for k, v in (files or {}).items()},
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PackageError(f"That package's manifest could not be read: {exc}") from exc


@dataclass(frozen=True, slots=True)
class PackageResult:
    path: Path
    size_bytes: int
    encrypted: bool
    manifest: Manifest
    notes: list[str] = field(default_factory=list)


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _dump(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, default=str, ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------------------
# Gathering what goes in.
# ---------------------------------------------------------------------------------------


def _rows(session: Session, model: type[Any], columns: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {name: getattr(row, name) for name in columns}
        for row in session.scalars(select(model)).all()
    ]


def collect_sections(session: Session) -> list[Section]:
    """Everything that travels in a package, in the order it must be imported."""
    return [
        Section(
            "identity/profile.json",
            _rows(
                session,
                models.AIProfile,
                (
                    "ai_id",
                    "name",
                    "personality",
                    "communication_style",
                    "goals",
                    "interests",
                    "owner_name",
                    "created_at",
                    "updated_at",
                    "version",
                ),
            ),
        ),
        Section(
            "skills/state.json",
            _rows(
                session,
                models.SkillState,
                (
                    "ai_id",
                    "skill_id",
                    "status",
                    "level",
                    "last_evaluation_score",
                    "learned_at",
                    "updated_at",
                    "version",
                    "package_version",
                    "trained_at",
                ),
            ),
        ),
        Section(
            "projects/projects.json",
            _rows(
                session,
                models.Project,
                (
                    "id",
                    "ai_id",
                    "name",
                    "description",
                    "created_at",
                    "updated_at",
                    "version",
                    "archived_at",
                ),
            ),
        ),
        Section(
            "memory/memories.json",
            _rows(
                session,
                models.Memory,
                (
                    "uid",
                    "ai_id",
                    "content",
                    "category",
                    "created_at",
                    "updated_at",
                    "version",
                    "project_id",
                ),
            ),
        ),
        Section(
            "conversations/conversations.json",
            _rows(
                session,
                models.Conversation,
                ("id", "ai_id", "title", "created_at", "updated_at", "version", "project_id"),
            ),
        ),
        Section(
            "conversations/messages.json",
            _rows(
                session,
                models.Message,
                (
                    "uid",
                    "conversation_id",
                    "role",
                    "content",
                    "created_at",
                    "model_id",
                    "finish_reason",
                ),
            ),
        ),
        Section(
            "knowledge/documents.json",
            _rows(
                session,
                models.Document,
                (
                    "id",
                    "ai_id",
                    "title",
                    "source_path",
                    "media_type",
                    "size_bytes",
                    "sha256",
                    "chunk_count",
                    "status",
                    "added_at",
                    "version",
                ),
            ),
        ),
        Section(
            "settings/preferences.json",
            _rows(session, models.Preference, ("key", "value", "updated_at")),
        ),
        Section(
            "models/models.json",
            _rows(
                session,
                models.InstalledModel,
                (
                    "id",
                    "display_name",
                    "family",
                    "size_bytes",
                    "sha256",
                    "verified_against",
                    "license_id",
                    "installed_at",
                ),
            ),
        ),
    ]


def _describe_models(session: Session) -> list[dict[str, Any]]:
    """Model references, with the licence position stated rather than assumed."""
    installed = session.scalars(select(models.InstalledModel)).all()
    return [
        {
            "id": row.id,
            "display_name": row.display_name,
            "license": row.license_id,
            "included": False,
            "size_bytes": row.size_bytes,
            "sha256": row.sha256,
            "reason": "Model files are not copied: they are large, publicly downloadable, and "
            "their licences generally do not permit passing them on. This package records "
            "what to fetch; the importer downloads it with the licence shown.",
        }
        for row in installed
    ]


def _requirements(session: Session) -> Requirements:
    """What this AI needed. Taken from the largest installed model, not guessed at."""
    sizes = [row.size_bytes for row in session.scalars(select(models.InstalledModel)).all()]
    # A model needs roughly its own size in memory to load, plus room to work in.
    return Requirements(min_ram_bytes=max(sizes, default=0), backends=("cpu",))


# ---------------------------------------------------------------------------------------
# Writing.
# ---------------------------------------------------------------------------------------


def write_package(
    session: Session,
    *,
    destination: Path,
    password: str | None = None,
    device_id: str | None = None,
) -> PackageResult:
    """Write a `.myai` package. With a password, everything but the header is encrypted."""
    destination = destination if destination.suffix == SUFFIX else destination.with_suffix(SUFFIX)
    destination.parent.mkdir(parents=True, exist_ok=True)

    params = new_params() if password else None
    key = derive_key(password, params) if password and params else None

    sections = collect_sections(session)
    profile = session.scalar(select(models.AIProfile))
    skills = session.scalars(select(models.SkillState)).all()

    entries: dict[str, bytes] = {}
    integrity: dict[str, str] = {}
    for section in sections:
        body = _dump(section.payload)
        stored = seal(key, section.path, body) if key else body
        entries[section.path] = stored
        # The digest covers what is actually stored, so a corrupted archive is caught before
        # a password is even tried.
        integrity[section.path] = _digest(stored)

    manifest = Manifest(
        format_version=FORMAT_VERSION,
        ai=(
            {"id": profile.ai_id, "name": profile.name, "created_at": profile.created_at}
            if profile
            else {}
        ),
        exported_at=datetime.now(tz=UTC),
        exported_by={"app_version": __version__, "device_id": device_id},
        models=_describe_models(session),
        skills=[{"id": s.skill_id, "level": s.level, "status": s.status} for s in skills],
        requirements=_requirements(session),
        counts={s.path: len(s.payload) for s in sections},
        integrity=integrity,
    )
    manifest_bytes = _dump(manifest.to_json())
    stored_manifest = seal(key, MANIFEST_NAME, manifest_bytes) if key else manifest_bytes

    header = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "encryption": (
            {"enabled": True, "cipher": "aes-256-gcm", "kdf": params.to_json()}
            if params
            else {"enabled": False}
        ),
        # Only useful when unencrypted; when locked, the AEAD tag is the check that matters.
        "manifest_sha256": None if key else _digest(stored_manifest),
    }

    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(HEADER_NAME, _dump(header))
        archive.writestr(MANIFEST_NAME, stored_manifest)
        for path, payload in entries.items():
            archive.writestr(path, payload)

    notes = [
        "Model files are referenced, not copied. Import re-downloads them with the licence shown.",
        "Credentials are never included: an installation token or a paired device's key is "
        "an access grant, not your data.",
    ]
    if not password:
        notes.append(
            "This package is not encrypted. Anyone who finds the file can read everything in "
            "it. Set a password if it is going anywhere you do not control."
        )
    return PackageResult(
        path=destination,
        size_bytes=destination.stat().st_size,
        encrypted=bool(password),
        manifest=manifest,
        notes=notes,
    )


# ---------------------------------------------------------------------------------------
# Reading.
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OpenPackage:
    """A verified package, ready to be read. Nothing is imported by opening one."""

    manifest: Manifest
    encrypted: bool
    _archive: zipfile.ZipFile
    _key: bytes | None

    def section(self, path: str) -> Any:
        raw = self._archive.read(path)
        if self._key is not None:
            raw = unseal_entry(self._key, path, raw)
        return json.loads(raw.decode("utf-8"))

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> OpenPackage:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def read_header(path: Path) -> dict[str, Any]:
    """The plaintext header. Says what the file is and whether a password is needed."""
    if not path.is_file():
        raise PackageError(f"There is no file at {path}.")
    try:
        with zipfile.ZipFile(path) as archive:
            header = json.loads(archive.read(HEADER_NAME).decode("utf-8"))
    except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PackageError(f"{path.name} is not a MyAI package.") from exc
    if header.get("format") != FORMAT:
        raise PackageError(f"{path.name} is not a MyAI package.")
    if int(header.get("format_version") or 0) > FORMAT_VERSION:
        raise PackageError(
            f"{path.name} was made by a newer version of MyAI Academy. Update and try again."
        )
    return dict(header)


def needs_password(path: Path) -> bool:
    return bool((read_header(path).get("encryption") or {}).get("enabled"))


def open_package(path: Path, *, password: str | None = None) -> OpenPackage:
    """Verify a package end to end and return it ready to read.

    Every entry's digest is checked here, before any caller can import anything. A package
    that has rotted on a drive is refused as a whole rather than applied in part.
    """
    header = read_header(path)
    encryption = header.get("encryption") or {}
    encrypted = bool(encryption.get("enabled"))

    key: bytes | None = None
    if encrypted:
        if not password:
            raise WrongPasswordError("This package is locked. It needs its password.")
        key = derive_key(password, KdfParams.from_json(dict(encryption.get("kdf") or {})))

    archive = zipfile.ZipFile(path)
    try:
        stored_manifest = archive.read(MANIFEST_NAME)
        expected = header.get("manifest_sha256")
        if not encrypted and expected and _digest(stored_manifest) != expected:
            raise PackageError(
                f"{path.name} has been changed since it was made: its manifest does not match."
            )
        body = unseal_entry(key, MANIFEST_NAME, stored_manifest) if key else stored_manifest
        manifest = Manifest.from_json(json.loads(body.decode("utf-8")))

        present = set(archive.namelist()) - {HEADER_NAME, MANIFEST_NAME}
        listed = set(manifest.integrity)
        if missing := listed - present:
            raise PackageError(f"{path.name} is incomplete: {', '.join(sorted(missing))} is gone.")
        if extra := present - listed:
            # An entry nobody vouched for is not read, and its presence means the file was
            # assembled by something other than this program.
            raise PackageError(
                f"{path.name} contains files its manifest does not list: "
                f"{', '.join(sorted(extra))}."
            )
        for entry, digest in manifest.integrity.items():
            if _digest(archive.read(entry)) != digest:
                raise PackageError(f"{path.name} is damaged: {entry} does not match its checksum.")
    except Exception:
        archive.close()
        raise

    return OpenPackage(manifest=manifest, encrypted=encrypted, _archive=archive, _key=key)
