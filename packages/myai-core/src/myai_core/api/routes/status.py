from __future__ import annotations

from fastapi import APIRouter

from myai_core.api.deps import PreferencesDep, ProfileDep, StateDep, StorageDep
from myai_core.status.service import ServiceStatus

router = APIRouter(tags=["status"])


@router.get("/status", response_model=ServiceStatus)
def read_status(
    state: StateDep, profile: ProfileDep, prefs: PreferencesDep, storage: StorageDep
) -> ServiceStatus:
    preferences = prefs.get()
    return state.status.build(
        profile_exists=profile.get() is not None,
        storage_configured=storage.get_config() is not None,
        onboarding_completed=preferences.onboarding_completed,
        privacy_mode=preferences.privacy_mode.value,
    )
