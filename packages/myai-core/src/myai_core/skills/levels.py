"""Level bands (spec §34). Levels are only ever awarded by evaluations."""

from __future__ import annotations

from enum import StrEnum

MAX_LEVEL = 100


class LevelBand(StrEnum):
    UNLEARNED = "unlearned"
    BEGINNER = "beginner"  # 1–5
    DEVELOPING = "developing"  # 6–15
    CAPABLE = "capable"  # 16–30
    ADVANCED = "advanced"  # 31–50
    EXPERT = "expert"  # 51+


_BANDS: tuple[tuple[int, LevelBand], ...] = (
    (51, LevelBand.EXPERT),
    (31, LevelBand.ADVANCED),
    (16, LevelBand.CAPABLE),
    (6, LevelBand.DEVELOPING),
    (1, LevelBand.BEGINNER),
)


def band_for_level(level: int) -> LevelBand:
    if level < 0 or level > MAX_LEVEL:
        raise ValueError(f"level must be within 0..{MAX_LEVEL}, got {level}")
    for floor, band in _BANDS:
        if level >= floor:
            return band
    return LevelBand.UNLEARNED


def overall_level(levels: list[int]) -> int:
    """The AI's headline level: a weighted view of learned skills.

    Deliberately *not* a plain sum (which would reward breadth over depth) nor a plain
    max (which would ignore breadth). Rounded mean of the top three learned skills, so
    a specialist and a generalist with similar competence land near each other.
    """
    learned = sorted((lv for lv in levels if lv > 0), reverse=True)
    if not learned:
        return 0
    top = learned[:3]
    return round(sum(top) / len(top))
