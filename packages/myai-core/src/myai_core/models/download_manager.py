"""Runs model downloads on background threads and persists their progress."""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from myai_core.audit.service import AuditCategory, AuditService
from myai_core.db.models import ModelDownload
from myai_core.hardware.volumes import probe_volumes
from myai_core.models.catalog import CatalogModel
from myai_core.models.download import DownloadCancelled, DownloadError, ModelDownloader
from myai_core.models.service import ModelService
from myai_core.storage import StorageManager

log = logging.getLogger(__name__)


class DownloadManager:
    def __init__(
        self, session_factory: sessionmaker[Session], downloader: ModelDownloader | None = None
    ) -> None:
        self._sessions = session_factory
        self._downloader = downloader or ModelDownloader()
        self._cancels: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self, job_id: str, model: CatalogModel, dest: Path) -> None:
        cancel = threading.Event()
        thread = threading.Thread(
            target=self._run,
            args=(job_id, model, dest, cancel),
            name=f"download-{model.id}",
            daemon=True,
        )
        with self._lock:
            self._cancels[job_id] = cancel
            self._threads[job_id] = thread
        thread.start()

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            event = self._cancels.get(job_id)
        if event is None:
            return False
        event.set()
        return True

    def wait(self, job_id: str, timeout: float | None = None) -> None:
        """Test helper: block until the job's thread finishes."""
        with self._lock:
            thread = self._threads.get(job_id)
        if thread is not None:
            thread.join(timeout)

    def shutdown(self) -> None:
        with self._lock:
            for event in self._cancels.values():
                event.set()
            threads = list(self._threads.values())
        for thread in threads:
            thread.join(timeout=5)

    # --- worker -------------------------------------------------------------------------

    def _run(self, job_id: str, model: CatalogModel, dest: Path, cancel: threading.Event) -> None:
        last_flush = 0.0

        def progress(done: int, total: int | None) -> None:
            nonlocal last_flush
            now = time.monotonic()
            if now - last_flush < 0.5:
                return
            last_flush = now
            self._update(job_id, status="running", bytes_done=done, bytes_total=total)

        self._update(job_id, status="running")
        try:
            result = self._downloader.download(
                model.download_url,
                dest,
                expected_sha256=model.sha256,
                on_progress=progress,
                cancel=cancel,
            )
        except DownloadCancelled:
            self._update(job_id, status="cancelled", finished=True)
            return
        except DownloadError as exc:
            log.warning("download of %s failed: %s", model.id, exc)
            self._update(job_id, status="failed", error=str(exc), finished=True)
            return
        except Exception as exc:
            log.exception("download of %s crashed", model.id)
            self._update(job_id, status="failed", error=f"Unexpected error: {exc}", finished=True)
            return

        with self._sessions() as session:
            storage = StorageManager(session, probe_volumes)
            ModelService(session, storage).record_installed(
                model, result.path, result.size_bytes, result.sha256
            )
            AuditService(session).record(
                AuditCategory.SYSTEM,
                "model_installed",
                f"Model '{model.name}' downloaded and verified",
                {
                    "model_id": model.id,
                    "size_bytes": result.size_bytes,
                    "verified_against": result.verified_against,
                },
            )
            job = session.get(ModelDownload, job_id)
            if job is not None:
                job.status = "completed"
                job.bytes_done = result.size_bytes
                job.bytes_total = result.size_bytes
                job.finished_at = datetime.now(tz=UTC)
            session.commit()
        with self._lock:
            self._cancels.pop(job_id, None)

    def _update(
        self,
        job_id: str,
        *,
        status: str,
        bytes_done: int | None = None,
        bytes_total: int | None = None,
        error: str | None = None,
        finished: bool = False,
    ) -> None:
        with self._sessions() as session:
            job = session.get(ModelDownload, job_id)
            if job is None:
                return
            job.status = status
            if bytes_done is not None:
                job.bytes_done = bytes_done
            if bytes_total is not None:
                job.bytes_total = bytes_total
            if error is not None:
                job.error = error
            if finished:
                job.finished_at = datetime.now(tz=UTC)
            session.commit()
        if finished:
            with self._lock:
                self._cancels.pop(job_id, None)
