from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from myai_core.api.deps import SessionDep, StateDep
from myai_core.db.models import Job
from myai_core.skills.jobs import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    state: StateDep, session: SessionDep, limit: int = Query(default=50, ge=1, le=500)
) -> list[JobRead]:
    return [JobRead.model_validate(j) for j in state.jobs.recent(session, limit)]


@router.get("/current", response_model=JobRead | None)
def current_job(state: StateDep, session: SessionDep) -> JobRead | None:
    job = state.jobs.current(session)
    return JobRead.model_validate(job) if job else None


@router.get("/{job_id}", response_model=JobRead)
def read_job(job_id: str, session: SessionDep) -> JobRead:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown job.")
    return JobRead.model_validate(job)


def _act(state: StateDep, session: SessionDep, job_id: str, action: str) -> JobRead:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown job.")
    ok = {"pause": state.jobs.pause, "resume": state.jobs.resume, "cancel": state.jobs.cancel}[
        action
    ](job_id)
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, f"That job cannot be {action}d now.")
    session.expire(job)
    return JobRead.model_validate(session.get(Job, job_id))


@router.post("/{job_id}/pause", response_model=JobRead)
def pause_job(job_id: str, state: StateDep, session: SessionDep) -> JobRead:
    return _act(state, session, job_id, "pause")


@router.post("/{job_id}/resume", response_model=JobRead)
def resume_job(job_id: str, state: StateDep, session: SessionDep) -> JobRead:
    return _act(state, session, job_id, "resume")


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: str, state: StateDep, session: SessionDep) -> JobRead:
    return _act(state, session, job_id, "cancel")
