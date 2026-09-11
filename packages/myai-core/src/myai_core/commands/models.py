from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from myai_core.schemas import ApiModel


class CommandName(StrEnum):
    LEARN = "learn"
    TRAIN = "train"
    SKILLS = "skills"
    STATUS = "status"
    HARDWARE = "hardware"
    MEMORY = "memory"
    HELP = "help"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    HISTORY = "history"
    SETTINGS = "settings"
    PROJECTS = "projects"


class TrainTarget(ApiModel):
    """Optional qualifiers for ``/train`` (spec §38)."""

    duration_seconds: int | None = Field(default=None, description="From '4h', '90m'.")
    target_level: int | None = Field(default=None, ge=1, le=100, description="From 'level 10'.")
    specialization: str | None = Field(default=None, description="From a trailing word.")
    all_areas: bool = False


class ParsedCommand(ApiModel):
    name: CommandName
    raw: str
    skill: str | None = Field(default=None, description="Resolved catalog skill id, if any.")
    skill_text: str | None = Field(default=None, description="What the user typed for the skill.")
    train: TrainTarget | None = None
    args: list[str] = Field(default_factory=list)
    natural_language: bool = Field(
        default=False, description="True when mapped from a sentence rather than a slash."
    )


class CommandOutcome(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"  # feature not in this build; say so
    ERROR = "error"


class CommandResult(ApiModel):
    outcome: CommandOutcome
    command: ParsedCommand | None
    title: str
    message: str
    data: dict[str, object] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list, description="Commands to offer next.")
