"""Resumable, integrity-verified HTTP download for large model files.

* Resumes an interrupted ``.part`` file with a ``Range`` request (restarts cleanly if the
  server ignores it).
* Verifies SHA-256 against a pinned hash or the hash the host declares (Hugging Face
  exposes the LFS object hash as the ``ETag``/``X-Linked-ETag`` of the resolved file).
* Renames into place only after verification, so a half-written or corrupt file never
  masquerades as a model.
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
    verified_against: str  # 'pinned', 'host-declared' or 'none'


def declared_sha256(headers: httpx.Headers) -> str | None:
    """Extract a SHA-256 from ETag-style headers when the host publishes one."""
    for name in ("x-linked-etag", "etag"):
        value = headers.get(name)
        if not value:
            continue
        candidate = str(value).strip().strip('"').removeprefix("W/").strip('"').lower()
        if _SHA256_RE.match(candidate):
            return candidate
    return None


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
            total = _content_length(head.headers)
            host_hash = declared_sha256(head.headers)
            expected = expected_sha256 or host_hash
            verified_against = (
                "pinned" if expected_sha256 else ("host-declared" if host_hash else "none")
            )

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
                "Integrity check failed: the downloaded file does not match the "
                f"{verified_against} SHA-256. The partial file was deleted."
            )
        part.replace(dest)
        return DownloadResult(
            path=dest, size_bytes=done, sha256=actual, verified_against=verified_against
        )


def _content_length(headers: httpx.Headers) -> int | None:
    value = headers.get("content-length")
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
