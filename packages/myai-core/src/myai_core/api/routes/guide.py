from __future__ import annotations

from fastapi import APIRouter
from pydantic import Field

from myai_core.guide import GuideAnswer, GuideTopicRead, ask, topics
from myai_core.schemas import ApiModel

router = APIRouter(prefix="/guide", tags=["guide"])


class GuideQuestion(ApiModel):
    question: str = Field(min_length=1, max_length=500)


@router.get("/topics", response_model=list[GuideTopicRead])
def list_topics() -> list[GuideTopicRead]:
    return topics()


@router.post("/ask", response_model=GuideAnswer)
def ask_guide(body: GuideQuestion) -> GuideAnswer:
    """Answer a question about MyAI Academy from the curated guide. Questions are not
    logged anywhere."""
    return ask(body.question)
