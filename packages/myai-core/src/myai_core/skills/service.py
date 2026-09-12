"""Skill progress for the current AI: catalog joined with persisted state."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db.models import SkillEvaluation, SkillState
from myai_core.schemas import ApiModel
from myai_core.skills.academy import AchievementStatus, DegreeStatus, achievements_for, degrees_for
from myai_core.skills.catalog import SkillAvailability, SkillDefinition, SkillDomain, all_skills
from myai_core.skills.levels import LevelBand, band_for_level, overall_level
from myai_core.skills.packages import bundled_package


class SkillStatus(ApiModel):
    """What the UI shows per skill. ``level`` 0 + ``learned=False`` means "not yet"."""

    id: str
    name: str
    icon: str
    domain: SkillDomain
    description: str
    specializations: list[str]
    requires: list[str]
    availability: SkillAvailability
    planned_phase: int
    learned: bool
    level: int
    band: LevelBand
    last_evaluation_score: float | None
    learned_at: datetime | None
    trained_at: datetime | None = Field(
        default=None, description="When training last replaced this skill's instructions."
    )
    trainable: bool = Field(
        default=False, description="A practice set exists, so this skill can be trained."
    )
    locked: bool
    locked_reason: str | None
    learnable: bool = Field(description="A package with a measurable benchmark exists.")
    package_version: str | None = None
    package: SkillPackageInfo | None = None
    area_scores: dict[str, float] = Field(default_factory=dict)


class SkillPackageInfo(ApiModel):
    version: str
    task_count: int
    areas: list[str]
    size_bytes: int
    license: str


class SkillsSummary(ApiModel):
    overall_level: int
    skills: list[SkillStatus]
    degrees: list[DegreeStatus] = Field(default_factory=list)
    achievements: list[AchievementStatus] = Field(default_factory=list)


class SkillsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self, ai_id: str | None) -> SkillsSummary:
        states: dict[str, SkillState] = {}
        if ai_id is not None:
            rows = self._session.scalars(select(SkillState).where(SkillState.ai_id == ai_id)).all()
            states = {row.skill_id: row for row in rows}

        area_scores: dict[str, dict[str, float]] = {}
        if ai_id is not None:
            latest: dict[str, SkillEvaluation] = {}
            for row in self._session.scalars(
                select(SkillEvaluation)
                .where(SkillEvaluation.ai_id == ai_id)
                .order_by(SkillEvaluation.evaluated_at.desc(), SkillEvaluation.id.desc())
            ):
                latest.setdefault(row.skill_id, row)
            area_scores = {
                k: {a: float(v) for a, v in r.area_scores.items()}  # type: ignore[arg-type]
                for k, r in latest.items()
            }
        statuses = [
            self._status_for(definition, states, area_scores.get(definition.id, {}))
            for definition in all_skills()
        ]
        levels = {s.id: s.level for s in statuses if s.learned}
        learnable = {s.id for s in statuses if s.learnable}
        return SkillsSummary(
            overall_level=overall_level([s.level for s in statuses]),
            skills=statuses,
            degrees=degrees_for(levels, learnable),
            achievements=achievements_for(levels, area_scores),
        )

    @staticmethod
    def _status_for(
        definition: SkillDefinition,
        states: dict[str, SkillState],
        area_scores: dict[str, float],
    ) -> SkillStatus:
        state = states.get(definition.id)
        level = state.level if state else 0
        learned = bool(state and state.status == "learned")
        package = bundled_package(definition.id)
        missing = [
            req for req in definition.requires if not (states.get(req) and states[req].level > 0)
        ]
        locked = bool(missing) and not learned
        return SkillStatus(
            id=definition.id,
            name=definition.name,
            icon=definition.icon,
            domain=definition.domain,
            description=definition.description,
            specializations=definition.specializations,
            requires=definition.requires,
            availability=definition.availability,
            planned_phase=definition.planned_phase,
            learned=learned,
            level=level,
            band=band_for_level(level),
            last_evaluation_score=state.last_evaluation_score if state else None,
            learned_at=state.learned_at if state else None,
            trained_at=state.trained_at if state else None,
            trainable=package is not None and package.practice is not None,
            locked=locked,
            locked_reason=(
                "Requires: " + ", ".join(m.title() for m in missing) if locked else None
            ),
            learnable=package is not None,
            package_version=state.package_version if state else None,
            package=(
                SkillPackageInfo(
                    version=package.manifest.version,
                    task_count=len(package.benchmark.tasks),
                    areas=package.benchmark.areas,
                    size_bytes=package.size_bytes,
                    license=package.manifest.license,
                )
                if package
                else None
            ),
            area_scores=area_scores,
        )


def count_trainable_skills(session: Session, ai_id: str | None) -> int:
    """Learned skills that have a practice set, so ``/train`` has something to work on."""
    if ai_id is None:
        return 0
    rows = session.scalars(
        select(SkillState).where(SkillState.ai_id == ai_id, SkillState.status == "learned")
    ).all()
    total = 0
    for row in rows:
        package = bundled_package(row.skill_id)
        if package is not None and package.practice is not None:
            total += 1
    return total
