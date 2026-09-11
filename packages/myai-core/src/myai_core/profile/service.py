from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db.models import AIProfile
from myai_core.profile.identity import new_ai_id
from myai_core.profile.schemas import ProfileCreate, ProfileUpdate


class ProfileError(ValueError):
    pass


class ProfileConflictError(ProfileError):
    """The caller's ``expected_version`` is stale."""


class ProfileService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> AIProfile | None:
        # Single AI per installation in Phase 1; ordered for determinism if that changes.
        return self._session.scalars(select(AIProfile).order_by(AIProfile.created_at)).first()

    def create(self, data: ProfileCreate) -> AIProfile:
        if self.get() is not None:
            raise ProfileError("An AI profile already exists. Update it instead.")
        profile = AIProfile(ai_id=new_ai_id(), **data.model_dump())
        self._session.add(profile)
        self._session.flush()
        return profile

    def update(self, data: ProfileUpdate) -> AIProfile:
        profile = self.get()
        if profile is None:
            raise ProfileError("No AI profile exists yet.")
        if data.expected_version is not None and data.expected_version != profile.version:
            raise ProfileConflictError(
                f"Profile changed elsewhere (have version {profile.version}, "
                f"you expected {data.expected_version}). Reload and try again."
            )
        changes = data.model_dump(exclude_unset=True, exclude={"expected_version"})
        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            return profile
        for key, value in changes.items():
            setattr(profile, key, value)
        profile.version += 1
        self._session.flush()
        return profile
