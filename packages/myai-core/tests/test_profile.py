import pytest
from sqlalchemy.orm import Session

from myai_core.profile.identity import is_valid_ai_id, new_ai_id
from myai_core.profile.schemas import ProfileCreate, ProfileUpdate
from myai_core.profile.service import ProfileConflictError, ProfileError, ProfileService


def test_ai_ids_are_prefixed_ulids() -> None:
    a, b = new_ai_id(), new_ai_id()
    assert a != b
    assert is_valid_ai_id(a)
    assert not is_valid_ai_id("myai_lowercase")
    assert not is_valid_ai_id("01ARZ3NDEKTSV4RRFFQ69G5FAV")


def test_create_and_get(session: Session) -> None:
    svc = ProfileService(session)
    assert svc.get() is None
    p = svc.create(ProfileCreate(name="  Nova ", interests=["Video", "video", " coding "]))
    assert p.name == "Nova"
    assert p.interests == ["Video", "coding"]  # de-duplicated case-insensitively, trimmed
    assert p.version == 1
    assert svc.get() is p


def test_only_one_profile(session: Session) -> None:
    svc = ProfileService(session)
    svc.create(ProfileCreate(name="Nova"))
    with pytest.raises(ProfileError):
        svc.create(ProfileCreate(name="Other"))


def test_update_bumps_version_and_respects_expected_version(session: Session) -> None:
    svc = ProfileService(session)
    svc.create(ProfileCreate(name="Nova"))
    p = svc.update(ProfileUpdate(personality="curious", expected_version=1))
    assert p.version == 2
    assert p.personality == "curious"
    with pytest.raises(ProfileConflictError):
        svc.update(ProfileUpdate(name="Stale", expected_version=1))
    assert svc.update(ProfileUpdate()).version == 2  # no-op does not bump


def test_update_without_profile(session: Session) -> None:
    with pytest.raises(ProfileError):
        ProfileService(session).update(ProfileUpdate(name="x"))


def test_validation_limits() -> None:
    with pytest.raises(ValueError):
        ProfileCreate(name="")
    long_list = [f"i{n}" for n in range(50)]
    assert len(ProfileCreate(name="N", interests=long_list).interests) == 20
