"""System prompt construction. Everything the model is told is visible to the user."""

from __future__ import annotations

from myai_core.db.models import AIProfile, Memory
from myai_core.knowledge.service import RetrievedChunk

MAX_KNOWLEDGE_CHARS = 6000


def build_system_prompt(
    profile: AIProfile,
    memories: list[Memory],
    knowledge: list[RetrievedChunk],
    skill_instructions: list[str] | None = None,
) -> str:
    parts: list[str] = []
    owner = f" Your owner is {profile.owner_name}." if profile.owner_name else ""
    parts.append(
        f"You are {profile.name}, a personal AI running locally on your owner's computer.{owner}"
    )
    if profile.personality:
        parts.append(f"Personality: {profile.personality}.")
    if profile.communication_style:
        parts.append(f"Communication style: {profile.communication_style}.")
    parts.append(
        "Be honest about what you do not know. You cannot browse the internet, run code, or "
        "access files unless they appear below."
    )
    if skill_instructions:
        parts.append(
            "Skills you have learned (follow these instructions):\n\n"
            + "\n\n".join(skill_instructions)
        )
    if memories:
        lines = "\n".join(f"- {m.content}" for m in memories)
        parts.append(
            f"Things you remember about your owner (they added these on purpose):\n{lines}"
        )
    if knowledge:
        budget = MAX_KNOWLEDGE_CHARS
        blocks: list[str] = []
        for chunk in knowledge:
            snippet = chunk.content[:budget]
            budget -= len(snippet)
            blocks.append(f"[{chunk.document_title} §{chunk.ordinal + 1}]\n{snippet}")
            if budget <= 0:
                break
        parts.append(
            "Relevant passages from your owner's knowledge library. Use them when they help "
            "and cite the source in brackets; say so if they do not answer the question:\n\n"
            + "\n\n".join(blocks)
        )
    return "\n\n".join(parts)
