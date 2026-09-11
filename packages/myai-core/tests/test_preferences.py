from sqlalchemy.orm import Session

from myai_core.db.models import Preference
from myai_core.preferences.schemas import (
    ComputePreset,
    ExperienceMode,
    Preferences,
    PreferencesUpdate,
)
from myai_core.preferences.service import PreferencesService


def test_defaults_are_private_and_beginner(session: Session) -> None:
    prefs = PreferencesService(session).get()
    assert prefs == Preferences()
    assert prefs.contributor_mode is False
    assert prefs.privacy_mode.value == "private"
    assert prefs.experience_mode is ExperienceMode.BEGINNER


def test_update_persists_only_provided_fields(session: Session) -> None:
    svc = PreferencesService(session)
    out = svc.update(PreferencesUpdate(compute_preset=ComputePreset.HIGH))
    assert out.compute_preset is ComputePreset.HIGH
    assert out.experience_mode is ExperienceMode.BEGINNER
    session.commit()
    assert svc.get().compute_preset is ComputePreset.HIGH
    stored = session.get(Preference, "compute_preset")
    assert stored is not None and stored.value == "high"


def test_corrupt_or_unknown_values_fall_back_to_defaults(session: Session) -> None:
    session.add(Preference(key="compute_preset", value="turbo"))
    session.add(Preference(key="future_setting", value={"x": 1}))
    session.flush()
    assert PreferencesService(session).get() == Preferences()
