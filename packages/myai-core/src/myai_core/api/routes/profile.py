from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from myai_core.api.deps import AuditDep, ProfileDep
from myai_core.audit.service import AuditCategory
from myai_core.profile.schemas import ProfileCreate, ProfileRead, ProfileUpdate
from myai_core.profile.service import ProfileConflictError, ProfileError

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileRead | None)
def read_profile(profile: ProfileDep) -> ProfileRead | None:
    row = profile.get()
    return ProfileRead.model_validate(row) if row else None


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileCreate, profile: ProfileDep, audit: AuditDep) -> ProfileRead:
    try:
        row = profile.create(body)
    except ProfileError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    audit.record(
        AuditCategory.PROFILE, "created", f"AI '{row.name}' was created", {"ai_id": row.ai_id}
    )
    return ProfileRead.model_validate(row)


@router.patch("", response_model=ProfileRead)
def update_profile(body: ProfileUpdate, profile: ProfileDep, audit: AuditDep) -> ProfileRead:
    try:
        row = profile.update(body)
    except ProfileConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ProfileError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    changed = sorted(k for k, v in body.model_dump(exclude_unset=True).items() if v is not None)
    changed = [c for c in changed if c != "expected_version"]
    if changed:
        audit.record(
            AuditCategory.PROFILE,
            "updated",
            "AI profile updated",
            {"fields": changed, "version": row.version},
        )
    return ProfileRead.model_validate(row)
