"""Background jobs (spec §40): one at a time, pausable, cancellable, persisted."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from ulid import ULID

from myai_core.db.models import Job
from myai_core.schemas import ApiModel
from myai_core.skills.evaluate import JobCancelledError, JobControl

log = logging.getLogger(__name__)

JobKind = Literal["learn", "evaluate", "train"]
JobStatus = Literal["queued", "running", "paused", "completed", "failed", "cancelled"]
ACTIVE_STATUSES: frozenset[str] = frozenset({"queued", "running", "paused"})

Work = Callable[[JobControl, Callable[[int, int], None]], dict[str, object]]


class JobRead(ApiModel):
    id: str
    kind: str
    skill_id: str
    model_id: str | None
    status: str
    progress_done: int
    progress_total: int
    compute_preset: str | None
    error: str | None
    result: dict[str, object]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

    @property
    def progress_percent(self) -> int:
        if self.progress_total <= 0:
            return 0
        return int(self.progress_done * 100 / self.progress_total)


class JobSummary(ApiModel):
    """The compact view shown in status bars."""

    id: str
    kind: str
    skill_id: str
    status: str
    progress_percent: int = Field(ge=0, le=100)


class JobBusyError(RuntimeError):
    """Another job is already running; the spec forbids accidental overload (§40)."""


def summarise(job: Job | JobRead) -> JobSummary:
    total = job.progress_total
    percent = int(job.progress_done * 100 / total) if total > 0 else 0
    return JobSummary(
        id=job.id, kind=job.kind, skill_id=job.skill_id, status=job.status, progress_percent=percent
    )


class JobManager:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory
        self._lock = threading.Lock()
        self._controls: dict[str, JobControl] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._current: str | None = None

    # --- queries --------------------------------------------------------------------------

    def current_id(self) -> str | None:
        with self._lock:
            return self._current

    def current(self, session: Session) -> Job | None:
        job_id = self.current_id()
        return session.get(Job, job_id) if job_id else None

    @staticmethod
    def recent(session: Session, limit: int = 50) -> list[Job]:
        return list(session.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit)).all())

    @staticmethod
    def recover(session: Session) -> int:
        """Mark jobs left active by a crash or restart as failed (spec §74). Returns count."""
        stale = list(session.scalars(select(Job).where(Job.status.in_(ACTIVE_STATUSES))).all())
        for job in stale:
            job.status = "failed"
            job.error = "Interrupted: the service stopped before this job finished. Start it again."
            job.finished_at = datetime.now(tz=UTC)
        session.flush()
        return len(stale)

    # --- lifecycle ------------------------------------------------------------------------

    def create(
        self,
        session: Session,
        *,
        kind: JobKind,
        ai_id: str,
        skill_id: str,
        model_id: str | None,
        compute_preset: str | None,
        total: int,
    ) -> Job:
        active = session.scalar(
            select(Job).where(Job.status.in_(ACTIVE_STATUSES)).order_by(Job.created_at.desc())
        )
        if self.current_id() is not None or active is not None:
            raise JobBusyError("Another job is already running. Wait for it or stop it first.")
        job = Job(
            id=f"job_{ULID()}",
            kind=kind,
            ai_id=ai_id,
            skill_id=skill_id,
            model_id=model_id,
            compute_preset=compute_preset,
            status="queued",
            progress_total=total,
        )
        session.add(job)
        session.flush()
        return job

    def start(self, job_id: str, work: Work) -> None:
        control = JobControl()
        thread = threading.Thread(
            target=self._run, args=(job_id, work, control), name=f"job-{job_id}", daemon=True
        )
        with self._lock:
            if self._current is not None:
                raise JobBusyError("Another job is already running.")
            self._current = job_id
            self._controls[job_id] = control
            self._threads[job_id] = thread
        thread.start()

    def pause(self, job_id: str) -> bool:
        control = self._controls.get(job_id)
        if control is None or control.cancel.is_set():
            return False
        control.paused.set()
        self._update(job_id, status="paused")
        return True

    def resume(self, job_id: str) -> bool:
        control = self._controls.get(job_id)
        if control is None or not control.paused.is_set():
            return False
        control.paused.clear()
        self._update(job_id, status="running")
        return True

    def cancel(self, job_id: str) -> bool:
        control = self._controls.get(job_id)
        if control is None:
            return False
        control.cancel.set()
        control.paused.clear()
        return True

    def wait(self, job_id: str, timeout: float | None = None) -> None:
        thread = self._threads.get(job_id)
        if thread is not None:
            thread.join(timeout)

    def shutdown(self) -> None:
        with self._lock:
            controls = list(self._controls.values())
            threads = list(self._threads.values())
        for control in controls:
            control.cancel.set()
            control.paused.clear()
        for thread in threads:
            thread.join(timeout=10)

    # --- worker ---------------------------------------------------------------------------

    def _run(self, job_id: str, work: Work, control: JobControl) -> None:
        self._update(job_id, status="running", started=True)

        def progress(done: int, total: int) -> None:
            self._update(job_id, progress=(done, total))

        try:
            result = work(control, progress)
        except JobCancelledError:
            self._update(job_id, status="cancelled", finished=True)
        except Exception as exc:
            log.exception("job %s failed", job_id)
            self._update(job_id, status="failed", error=str(exc), finished=True)
        else:
            self._update(job_id, status="completed", result=result, finished=True)
        finally:
            with self._lock:
                self._controls.pop(job_id, None)
                if self._current == job_id:
                    self._current = None

    def _update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: tuple[int, int] | None = None,
        error: str | None = None,
        result: dict[str, object] | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> None:
        with self._sessions() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress_done, job.progress_total = progress
            if error is not None:
                job.error = error[:2000]
            if result is not None:
                job.result = result
            now = datetime.now(tz=UTC)
            if started:
                job.started_at = now
            if finished:
                job.finished_at = now
            session.commit()
