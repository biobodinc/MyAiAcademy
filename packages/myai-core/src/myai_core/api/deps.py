from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from myai_core.api.state import AppState
from myai_core.audit.service import AuditService
from myai_core.hardware.volumes import probe_volumes
from myai_core.preferences.service import PreferencesService
from myai_core.profile.service import ProfileService
from myai_core.skills.service import SkillsService
from myai_core.storage.manager import StorageManager


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.core
    return state


StateDep = Annotated[AppState, Depends(get_state)]


def get_session(state: StateDep) -> Iterator[Session]:
    session = state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def get_profile_service(session: SessionDep) -> ProfileService:
    return ProfileService(session)


def get_preferences_service(session: SessionDep) -> PreferencesService:
    return PreferencesService(session)


def get_storage_manager(session: SessionDep) -> StorageManager:
    return StorageManager(session, probe_volumes)


def get_skills_service(session: SessionDep) -> SkillsService:
    return SkillsService(session)


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(session)


ProfileDep = Annotated[ProfileService, Depends(get_profile_service)]
PreferencesDep = Annotated[PreferencesService, Depends(get_preferences_service)]
StorageDep = Annotated[StorageManager, Depends(get_storage_manager)]
SkillsDep = Annotated[SkillsService, Depends(get_skills_service)]
AuditDep = Annotated[AuditService, Depends(get_audit_service)]
