from __future__ import annotations

from fastapi import APIRouter

from myai_core.api.deps import PreferencesDep, ProfileDep, SessionDep, StateDep, StorageDep
from myai_core.skills.jobs import summarise
from myai_core.skills.service import count_trainable_skills
from myai_core.status.service import ServiceStatus

router = APIRouter(tags=["status"])


@router.get("/status", response_model=ServiceStatus)
def read_status(
    state: StateDep,
    session: SessionDep,
    profile: ProfileDep,
    prefs: PreferencesDep,
    storage: StorageDep,
) -> ServiceStatus:
    preferences = prefs.get()
    row = profile.get()
    return state.status.build(
        profile_exists=row is not None,
        storage_configured=storage.get_config() is not None,
        onboarding_completed=preferences.onboarding_completed,
        privacy_mode=preferences.privacy_mode.value,
        ai_state=state.ai_state(session),
        job=summarise(current) if (current := state.jobs.current(session)) else None,
        trainable_skills=count_trainable_skills(session, row.ai_id if row else None),
    )
