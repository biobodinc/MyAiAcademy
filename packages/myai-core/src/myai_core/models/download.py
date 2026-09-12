"""Resumable, integrity-verified HTTP download for large model files.

* Resumes an interrupted ``.part`` file with a ``Range`` request (restarts cleanly if the
  server ignores it).
* Renames into place only after verification, so a half-written or corrupt file never
  masquerades as a model.

Which hashes may fail a download
--------------------------------

Only a hash the publisher *promises* is the content hash can fail a download:

* a hash pinned in our catalog, or
* ``X-Linked-Etag``, which Hugging Face documents as the LFS object's SHA-256 and sets on
  its own response (before the redirect to whichever CDN serves the bytes).

A bare ``ETag`` is deliberately **not** treated as a promise. HTTP defines it as an opaque
validator, and Hugging Face's Xet-backed CDN returns a 64-character hexadecimal id that
looks exactly like a SHA-256 but is not the file's hash. Treating it as one failed every
download of an otherwise perfect file and deleted it. We still use it opportunistically:
if it happens to match what we computed, that is extra confidence; if it does not, it
tells us nothing and is ignored.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ProgressCallback = Callable[[int, int | None], None]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CHUNK_BYTES = 1024 * 1024
PROGRESS_EVERY_BYTES = 4 * 1024 * 1024

PINNED = "pinned"
PUBLISHER = "publisher-hash"
HOST_ETAG = "host-etag"
IMPORTED = "imported"
UNVERIFIED = "none"

VERIFICATION_LABELS: dict[str, str] = {
    PINNED: "Verified against the hash pinned in MyAI Academy's catalog.",
    PUBLISHER: "Verified against the SHA-256 the publisher declares for this file.",
    HOST_ETAG: "The host's ETag matched the hash we computed while downloading.",
    IMPORTED: (
        "Recorded from the file you imported. MyAI Academy did not verify it against any "
        "publisher, because you supplied the file."
    ),
    UNVERIFIED: (
        "Not hash-verified: the host published no content hash for this file. The "
        "download was checked for completeness only."
    ),
}


class DownloadError(RuntimeError):
    pass


class IntegrityError(DownloadError):
    pass


class DownloadCancelled(DownloadError):  # noqa: N818 - reads naturally as a signal
    pass


@dataclass(frozen=True, slots=True)
class DownloadResult:
    path: Path
    size_bytes: int
    sha256: str
    verified_against: str  # PINNED, PUBLISHER, HOST_ETAG or UNVERIFIED

    @property
    def verified(self) -> bool:
        """True only when the hash was checked against something the publisher promised."""
        return self.verified_against in (PINNED, PUBLISHER)


@dataclass(frozen=True, slots=True)
class HostFileInfo:
    """What the host says about the file, before we download a byte."""

    size_bytes: int | None
    publisher_sha256: str | None
    """A hash the host promises is the content hash. May fail a download."""
    etag_sha256: str | None
    """A bare ETag that looks like a SHA-256. Never fails a download on its own."""
    final_url: str
    status_code: int


def _sha256_or_none(value: str | None) -> str | None:
    if not value:
        return None
    candidate = str(value).strip().removeprefix("W/").strip().strip('"').lower()
    return candidate if _SHA256_RE.match(candidate) else None


def read_host_info(response: httpx.Response) -> HostFileInfo:
    """Collect file metadata from a response and any redirects that led to it.

    Hugging Face sets ``X-Linked-Etag``/``X-Linked-Size`` on its own response and then
    redirects to a CDN, so the useful metadata lives in the redirect history rather than
    the final response.
    """
    chain = [*response.history, response]
    publisher = next(
        (h for h in (_sha256_or_none(r.headers.get("x-linked-etag")) for r in chain) if h), None
    )
    etag = next((h for h in (_sha256_or_none(r.headers.get("etag")) for r in chain) if h), None)
    size = next(
        (s for s in (_int_or_none(r.headers.get("x-linked-size")) for r in chain) if s), None
    )
    return HostFileInfo(
        size_bytes=size if size is not None else _content_length(response.headers),
        publisher_sha256=publisher,
        etag_sha256=etag,
        final_url=str(response.url),
        status_code=response.status_code,
    )


def _hash_existing(path: Path) -> tuple[Any, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK_BYTES), b""):
            digest.update(block)
            size += len(block)
    return digest, size


class ModelDownloader:
    def __init__(self, client_factory: Callable[[], httpx.Client] | None = None) -> None:
        self._client_factory = client_factory or (
            lambda: httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0, connect=15.0))
        )

    def inspect(self, url: str) -> HostFileInfo:
        """What the host declares about the file. Downloads nothing."""
        with self._client_factory() as client:
            response = client.head(url)
        if response.status_code >= 400:
            raise DownloadError(f"The file host answered {response.status_code} for {url}")
        return read_host_info(response)

    def download(
        self,
        url: str,
        dest: Path,
        *,
        expected_sha256: str | None = None,
        on_progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> DownloadResult:
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        cancel = cancel or threading.Event()

        with self._client_factory() as client:
            head = client.head(url)
            if head.status_code >= 400:
                raise DownloadError(f"The file host answered {head.status_code} for {url}")
            info = read_host_info(head)
            total = info.size_bytes
            # Only a promised content hash may fail the download; see the module docstring.
            expected = expected_sha256 or info.publisher_sha256
            source = PINNED if expected_sha256 else (PUBLISHER if expected else UNVERIFIED)

            digest = hashlib.sha256()
            done = 0
            headers: dict[str, str] = {}
            mode = "wb"
            if part.exists():
                digest, done = _hash_existing(part)
                if total is not None and done >= total:
                    done = 0
                    digest = hashlib.sha256()
                elif done > 0:
                    headers["Range"] = f"bytes={done}-"
                    mode = "ab"

            with client.stream("GET", url, headers=headers) as response:
                if response.status_code == 200 and done > 0:
                    # Server ignored the Range header: start over.
                    done = 0
                    digest = hashlib.sha256()
                    mode = "wb"
                elif response.status_code not in (200, 206):
                    raise DownloadError(f"The file host answered {response.status_code} for {url}")
                if total is None:
                    total = _content_length(response.headers)
                    if total is not None and response.status_code == 206:
                        total += done

                last_report = done
                with part.open(mode) as fh:
                    for block in response.iter_bytes(CHUNK_BYTES):
                        if cancel.is_set():
                            raise DownloadCancelled("Download cancelled.")
                        fh.write(block)
                        digest.update(block)
                        done += len(block)
                        if on_progress and done - last_report >= PROGRESS_EVERY_BYTES:
                            on_progress(done, total)
                            last_report = done
                if on_progress:
                    on_progress(done, total)

        if total is not None and done != total:
            raise DownloadError(f"Download ended early: {done} of {total} bytes.")
        actual = digest.hexdigest()
        if expected and actual != expected:
            part.unlink(missing_ok=True)
            raise IntegrityError(
                f"Integrity check failed for {dest.name}. The {_source_phrase(source)} says the "
                f"file should hash to {expected}, but the {done} bytes we received hash to "
                f"{actual}. The download was deleted rather than kept. This usually means the "
                "transfer was corrupted or interrupted; downloading again starts from scratch."
            )
        if not expected and info.etag_sha256 == actual:
            source = HOST_ETAG
        part.replace(dest)
        return DownloadResult(path=dest, size_bytes=done, sha256=actual, verified_against=source)


def _source_phrase(source: str) -> str:
    return "pinned catalog hash" if source == PINNED else "publisher's declared hash"


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _content_length(headers: httpx.Headers) -> int | None:
    return _int_or_none(headers.get("content-length"))
