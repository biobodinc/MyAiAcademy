import pytest
from sqlalchemy.orm import Session

from myai_core.db.models import SkillState
from myai_core.profile.schemas import ProfileCreate
from myai_core.profile.service import ProfileService
from myai_core.skills.catalog import all_skills, get_skill, resolve_skill_id
from myai_core.skills.levels import LevelBand, band_for_level, overall_level
from myai_core.skills.service import SkillsService


@pytest.mark.parametrize(
    ("level", "band"),
    [
        (0, LevelBand.UNLEARNED),
        (1, LevelBand.BEGINNER),
        (5, LevelBand.BEGINNER),
        (6, LevelBand.DEVELOPING),
        (15, LevelBand.DEVELOPING),
        (16, LevelBand.CAPABLE),
        (30, LevelBand.CAPABLE),
        (31, LevelBand.ADVANCED),
        (50, LevelBand.ADVANCED),
        (51, LevelBand.EXPERT),
        (100, LevelBand.EXPERT),
    ],
)
def test_bands(level: int, band: LevelBand) -> None:
    assert band_for_level(level) is band


def test_band_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        band_for_level(101)
    with pytest.raises(ValueError):
        band_for_level(-1)


def test_overall_level() -> None:
    assert overall_level([]) == 0
    assert overall_level([0, 0]) == 0
    assert overall_level([18, 12, 27, 9]) == 19  # mean of top three: (27+18+12)/3
    assert overall_level([40]) == 40


def test_catalog_integrity() -> None:
    ids = [s.id for s in all_skills()]
    assert len(ids) == len(set(ids))
    for s in all_skills():
        for req in s.requires:
            assert get_skill(req) is not None, f"{s.id} requires unknown {req}"
        assert s.requires != [s.id]


def test_resolve_aliases() -> None:
    assert resolve_skill_id("Video") == "video"
    assert resolve_skill_id("code") == "coding"
    assert resolve_skill_id("nonsense") is None


def test_summary_without_profile(session: Session) -> None:
    summary = SkillsService(session).summary(None)
    assert summary.overall_level == 0
    assert all(not s.learned and s.level == 0 for s in summary.skills)
    video = next(s for s in summary.skills if s.id == "video")
    assert video.locked and "Images" in (video.locked_reason or "")


def test_summary_with_learned_skill(session: Session) -> None:
    profile = ProfileService(session).create(ProfileCreate(name="Nova"))
    session.add(SkillState(ai_id=profile.ai_id, skill_id="conversation", status="learned", level=7))
    session.add(SkillState(ai_id=profile.ai_id, skill_id="images", status="learned", level=3))
    session.flush()
    summary = SkillsService(session).summary(profile.ai_id)
    by_id = {s.id: s for s in summary.skills}
    assert by_id["conversation"].learned and by_id["conversation"].band is LevelBand.DEVELOPING
    assert by_id["coding"].locked is False  # requirement (conversation) satisfied
    assert by_id["video"].locked is False  # images learned
    assert summary.overall_level == 5
