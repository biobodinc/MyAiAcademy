from __future__ import annotations

from fastapi import APIRouter

from myai_core.api.deps import AuditDep, PreferencesDep
from myai_core.audit.service import AuditCategory
from myai_core.preferences.schemas import Preferences, PreferencesUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=Preferences)
def read_preferences(prefs: PreferencesDep) -> Preferences:
    return prefs.get()


@router.patch("", response_model=Preferences)
def update_preferences(
    body: PreferencesUpdate, prefs: PreferencesDep, audit: AuditDep
) -> Preferences:
    before = prefs.get()
    after = prefs.update(body)
    if before.contributor_mode != after.contributor_mode:
        # Consent changes are security-relevant and always logged (spec §9, §61).
        audit.record(
            AuditCategory.SECURITY,
            "contributor_mode_changed",
            f"Community contribution turned {'ON' if after.contributor_mode else 'OFF'}",
        )
    return after
