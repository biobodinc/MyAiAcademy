"""Keyword matching over the curated topics. Deterministic and fully offline."""

from __future__ import annotations

import re

from pydantic import Field

from myai_core.guide.topics import BY_ID, TOPICS, GuideTopic
from myai_core.schemas import ApiModel

SOURCE_LABEL = "Built-in guide (not your AI model)"

_WORD_RE = re.compile(r"[a-z0-9/\-]+")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "do",
        "does",
        "did",
        "i",
        "my",
        "me",
        "you",
        "your",
        "it",
        "its",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "and",
        "or",
        "what",
        "which",
        "how",
        "why",
        "when",
        "where",
        "can",
        "could",
        "should",
        "would",
        "will",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "about",
        "any",
        "some",
        "there's",
        "what's",
        "how's",
    ]
)


class GuideTopicRead(ApiModel):
    id: str
    title: str
    question: str


class GuideAnswer(ApiModel):
    matched: bool = Field(description="False when no topic fit; ``answer`` then says so.")
    topic_id: str | None
    title: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = SOURCE_LABEL
    related: list[GuideTopicRead] = Field(default_factory=list)


def topics() -> list[GuideTopicRead]:
    return [GuideTopicRead(id=t.id, title=t.title, question=t.question) for t in TOPICS]


def ask(question: str) -> GuideAnswer:
    words = _words(question)
    if not words:
        return _no_match()
    scored = sorted(((_score(t, words, question), t) for t in TOPICS), key=lambda s: -s[0])
    best_score, best = scored[0]
    if best_score <= 0:
        return _no_match()
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    # Confidence: how decisively the best topic won, capped so a single shared word
    # never reads as certainty.
    confidence = min(1.0, 0.4 + 0.2 * best_score - 0.15 * runner_up)
    return GuideAnswer(
        matched=True,
        topic_id=best.id,
        title=best.title,
        answer=best.answer,
        confidence=round(max(0.0, confidence), 2),
        related=[
            GuideTopicRead(id=r.id, title=r.title, question=r.question)
            for r in (BY_ID[i] for i in best.related)
        ],
    )


def _no_match() -> GuideAnswer:
    return GuideAnswer(
        matched=False,
        topic_id=None,
        title="No built-in answer",
        answer=(
            "The guide only knows about MyAI Academy itself. Once a local model is installed, "
            "ask your AI in Chat; until then, try one of the suggested questions."
        ),
        confidence=0.0,
        related=[GuideTopicRead(id=t.id, title=t.title, question=t.question) for t in TOPICS[:4]],
    )


def _words(text: str) -> set[str]:
    return {_stem(w) for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def _stem(word: str) -> str:
    for suffix in ("ing", "ies", "es", "s", "ed"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _score(topic: GuideTopic, words: set[str], raw: str) -> float:
    lowered = raw.lower()
    score = 0.0
    for keyword in topic.keywords:
        if " " in keyword or "/" in keyword:
            if keyword in lowered:
                score += 2.0
        elif _stem(keyword) in words:
            score += 1.0
    return score
