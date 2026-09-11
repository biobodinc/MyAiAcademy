"""Static catalog of skills and their tree (spec §3, §35).

The catalog describes *what can be learned*, not what has been learned. It contains no
resource sizes or time estimates: those belong to real skill packages (Phase 3) and must
never be invented.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from myai_core.schemas import ApiModel


class SkillDomain(StrEnum):
    CORE = "core"
    CREATIVE = "creative"
    TECHNICAL = "technical"
    KNOWLEDGE = "knowledge"


class SkillAvailability(StrEnum):
    """Honest availability of the skill's implementation in this build."""

    PLANNED = "planned"  # provider interface exists, no implementation
    EXPERIMENTAL = "experimental"
    AVAILABLE = "available"


class SkillDefinition(ApiModel):
    id: str
    name: str
    domain: SkillDomain
    icon: str = Field(description="Emoji used consistently across desktop, mobile and CLI.")
    description: str
    specializations: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list, description="Skill ids that must be learned.")
    availability: SkillAvailability
    planned_phase: int


CATALOG: tuple[SkillDefinition, ...] = (
    SkillDefinition(
        id="conversation",
        name="Conversation",
        domain=SkillDomain.CORE,
        icon="💬",
        description="Talk naturally, remember context, follow instructions.",
        specializations=["Clarity", "Tone", "Instruction following"],
        availability=SkillAvailability.PLANNED,
        planned_phase=2,
    ),
    SkillDefinition(
        id="writing",
        name="Writing",
        domain=SkillDomain.CREATIVE,
        icon="✍️",
        description="Drafting, editing and styling prose.",
        specializations=["Editing", "Storytelling", "Technical writing"],
        requires=["conversation"],
        availability=SkillAvailability.PLANNED,
        planned_phase=3,
    ),
    SkillDefinition(
        id="coding",
        name="Coding",
        domain=SkillDomain.TECHNICAL,
        icon="💻",
        description="Write, explain and debug code.",
        specializations=["Debugging", "Reasoning", "Code quality", "Refactoring"],
        requires=["conversation"],
        availability=SkillAvailability.PLANNED,
        planned_phase=3,
    ),
    SkillDefinition(
        id="research",
        name="Research",
        domain=SkillDomain.KNOWLEDGE,
        icon="🔎",
        description="Retrieve, compare and summarise information from your knowledge.",
        specializations=["Summarisation", "Source comparison", "Citation"],
        requires=["conversation"],
        availability=SkillAvailability.PLANNED,
        planned_phase=3,
    ),
    SkillDefinition(
        id="science",
        name="Science",
        domain=SkillDomain.KNOWLEDGE,
        icon="🧪",
        description="Quantitative reasoning and scientific explanation.",
        specializations=["Mathematics", "Data analysis", "Explanation"],
        requires=["research"],
        availability=SkillAvailability.PLANNED,
        planned_phase=3,
    ),
    SkillDefinition(
        id="images",
        name="Images",
        domain=SkillDomain.CREATIVE,
        icon="🖼️",
        description="Generate and edit images.",
        specializations=["Composition", "Style", "Consistency"],
        availability=SkillAvailability.PLANNED,
        planned_phase=10,
    ),
    SkillDefinition(
        id="video",
        name="Video",
        domain=SkillDomain.CREATIVE,
        icon="🎬",
        description="Plan and generate video.",
        specializations=[
            "Cinematography",
            "Lighting",
            "Motion",
            "Storytelling",
            "Character consistency",
        ],
        requires=["images"],
        availability=SkillAvailability.PLANNED,
        planned_phase=10,
    ),
    SkillDefinition(
        id="music",
        name="Music",
        domain=SkillDomain.CREATIVE,
        icon="🎵",
        description="Compose and arrange music.",
        specializations=["Structure", "Style understanding", "Composition"],
        availability=SkillAvailability.PLANNED,
        planned_phase=10,
    ),
    SkillDefinition(
        id="games",
        name="Games",
        domain=SkillDomain.CREATIVE,
        icon="🎮",
        description="Design game mechanics, levels and narratives.",
        specializations=["Mechanics", "Level design", "Narrative"],
        requires=["writing", "coding"],
        availability=SkillAvailability.PLANNED,
        planned_phase=10,
    ),
)

_BY_ID: dict[str, SkillDefinition] = {s.id: s for s in CATALOG}
_ALIASES: dict[str, str] = {
    "code": "coding",
    "programming": "coding",
    "chat": "conversation",
    "image": "images",
    "picture": "images",
    "pictures": "images",
    "videos": "video",
    "song": "music",
    "songs": "music",
    "game": "games",
    "write": "writing",
}


def get_skill(skill_id: str) -> SkillDefinition | None:
    return _BY_ID.get(skill_id)


def resolve_skill_id(text: str) -> str | None:
    """Map user input (``"Video"``, ``"code"``) to a catalog id, or ``None``."""
    key = text.strip().lower()
    if key in _BY_ID:
        return key
    return _ALIASES.get(key)


def all_skills() -> tuple[SkillDefinition, ...]:
    return CATALOG
