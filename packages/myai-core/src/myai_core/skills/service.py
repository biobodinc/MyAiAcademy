"""Skill progress for the current AI: catalog joined with persisted state."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db.models import SkillState
from myai_core.skills.catalog import SkillAvailability, SkillDefinition, SkillDomain, all_skills
from myai_core.skills.levels import LevelBand, band_for_level, overall_level


class SkillStatus(BaseModel):
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
    locked: bool
    locked_reason: str | None


class SkillsSummary(BaseModel):
    overall_level: int
    skills: list[SkillStatus]


class SkillsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self, ai_id: str | None) -> SkillsSummary:
        states: dict[str, SkillState] = {}
        if ai_id is not None:
            rows = self._session.scalars(select(SkillState).where(SkillState.ai_id == ai_id)).all()
            states = {row.skill_id: row for row in rows}

        statuses = [self._status_for(definition, states) for definition in all_skills()]
        return SkillsSummary(
            overall_level=overall_level([s.level for s in statuses]),
            skills=statuses,
        )

    @staticmethod
    def _status_for(definition: SkillDefinition, states: dict[str, SkillState]) -> SkillStatus:
        state = states.get(definition.id)
        level = state.level if state else 0
        learned = bool(state and state.status == "learned")
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
            locked=locked,
            locked_reason=(
                "Requires: " + ", ".join(m.title() for m in missing) if locked else None
            ),
        )
