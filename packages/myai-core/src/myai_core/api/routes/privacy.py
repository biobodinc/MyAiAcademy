"""Privacy Center (spec §62): a truthful summary computed from local state."""

from __future__ import annotations

from fastapi import APIRouter

from myai_core.api.deps import PreferencesDep
from myai_core.schemas import ApiModel

router = APIRouter(prefix="/privacy", tags=["privacy"])


class PrivacySummary(ApiModel):
    private_data_location: str = "Local only"
    cloud_ai_data_uploads: int = 0
    community_sharing: bool
    cloud_backup: bool = False
    connected_devices: int = 0
    connected_apps: int = 0
    account_linked: bool = False
    notes: list[str]


@router.get("", response_model=PrivacySummary)
def read_privacy(prefs: PreferencesDep) -> PrivacySummary:
    preferences = prefs.get()
    return PrivacySummary(
        community_sharing=preferences.contributor_mode,
        notes=[
            "This build has no cloud account, sync or upload code paths at all.",
            "The only outbound network activity is an internet reachability check "
            "(a TCP connect with no payload) used to show online/offline status.",
            "Device pairing, cloud sync and community contribution arrive in later phases "
            "and will each require explicit opt-in.",
        ],
    )
