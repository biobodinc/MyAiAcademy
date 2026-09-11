from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from myai_core.api.deps import ProfileDep, SkillsDep
from myai_core.skills.service import SkillsSummary, SkillStatus

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=SkillsSummary)
def read_skills(skills: SkillsDep, profile: ProfileDep) -> SkillsSummary:
    row = profile.get()
    return skills.summary(row.ai_id if row else None)


@router.get("/{skill_id}", response_model=SkillStatus)
def read_skill(skill_id: str, skills: SkillsDep, profile: ProfileDep) -> SkillStatus:
    row = profile.get()
    for item in skills.summary(row.ai_id if row else None).skills:
        if item.id == skill_id:
            return item
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown skill '{skill_id}'.")
