"""Degrees and achievements (spec §82-§83): game concepts backed only by measured levels
and benchmark area scores. Nothing here is awarded for time spent or clicks."""

from __future__ import annotations

from dataclasses import dataclass

from myai_core.schemas import ApiModel


@dataclass(frozen=True, slots=True)
class DegreeDefinition:
    id: str
    name: str
    icon: str
    skills: tuple[str, ...]


DEGREES: tuple[DegreeDefinition, ...] = (
    DegreeDefinition("software", "Software Development", "💻", ("conversation", "coding")),
    DegreeDefinition("research", "Research", "🔎", ("research", "science")),
    DegreeDefinition("writing", "Creative Writing", "✍️", ("conversation", "writing")),
    DegreeDefinition("media", "Creative Media", "🎬", ("images", "video", "music")),
)


class DegreeStatus(ApiModel):
    id: str
    name: str
    icon: str
    skills: list[str]
    level: int
    earned: bool
    missing: list[str]
    note: str


class AchievementStatus(ApiModel):
    id: str
    name: str
    icon: str
    requirement: str
    earned: bool
    progress: str


def degrees_for(levels: dict[str, int], learnable: set[str]) -> list[DegreeStatus]:
    out: list[DegreeStatus] = []
    for d in DEGREES:
        missing = [s for s in d.skills if levels.get(s, 0) <= 0]
        earned = not missing
        level = min(levels[s] for s in d.skills) if earned else 0
        unavailable = [s for s in d.skills if s not in learnable]
        if unavailable:
            note = (
                "Not yet possible: " + ", ".join(unavailable) + " cannot be learned in this build."
            )
        elif earned:
            note = "The degree level is the lowest level among its skills."
        else:
            note = "Requires: " + ", ".join(m.title() for m in missing)
        out.append(
            DegreeStatus(
                id=d.id,
                name=d.name,
                icon=d.icon,
                skills=list(d.skills),
                level=level,
                earned=earned,
                missing=missing,
                note=note,
            )
        )
    return out


def achievements_for(
    levels: dict[str, int], area_scores: dict[str, dict[str, float]]
) -> list[AchievementStatus]:
    """``area_scores`` maps skill id -> latest benchmark area scores (0..1)."""
    learned = [s for s, lv in levels.items() if lv > 0]
    coding = levels.get("coding", 0)
    debugging = area_scores.get("coding", {}).get("debugging", 0.0)
    research, science, writing = (
        levels.get("research", 0),
        levels.get("science", 0),
        levels.get("writing", 0),
    )
    return [
        AchievementStatus(
            id="first_lesson",
            name="First Lesson",
            icon="🎓",
            requirement="Learn any skill (its benchmark completes at least once).",
            earned=bool(learned),
            progress=f"{len(learned)} skill(s) learned",
        ),
        AchievementStatus(
            id="coding_specialist",
            name="Coding Specialist",
            icon="💻",
            requirement="Coding level 30 or higher.",
            earned=coding >= 30,
            progress=f"Coding level {coding}/30",
        ),
        AchievementStatus(
            id="debugger",
            name="Debugger",
            icon="🐞",
            requirement="Score 75% or more on the coding benchmark's debugging area.",
            earned=debugging >= 0.75,
            progress=f"Debugging area {round(debugging * 100)}%/75%",
        ),
        AchievementStatus(
            id="scholar",
            name="Scholar",
            icon="📚",
            requirement="Research and Science both at level 30 or higher.",
            earned=research >= 30 and science >= 30,
            progress=f"Research {research}/30, Science {science}/30",
        ),
        AchievementStatus(
            id="wordsmith",
            name="Wordsmith",
            icon="✍️",
            requirement="Writing level 30 or higher.",
            earned=writing >= 30,
            progress=f"Writing level {writing}/30",
        ),
        AchievementStatus(
            id="well_rounded",
            name="Well Rounded",
            icon="🌐",
            requirement="Four or more skills learned.",
            earned=len(learned) >= 4,
            progress=f"{len(learned)}/4 skills",
        ),
    ]
