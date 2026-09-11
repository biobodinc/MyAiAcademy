from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from myai_core.schemas import ApiModel

_MAX_LIST_ITEMS = 20
_MAX_ITEM_LEN = 80


def _clean_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for raw in values:
        item = " ".join(raw.split())[:_MAX_ITEM_LEN]
        if item and item.lower() not in {c.lower() for c in cleaned}:
            cleaned.append(item)
    return cleaned[:_MAX_LIST_ITEMS]


class ProfileCreate(ApiModel):
    name: str = Field(min_length=1, max_length=64, examples=["Nova"])
    personality: str = Field(default="", max_length=500, examples=["Helpful, curious, concise"])
    communication_style: str = Field(default="", max_length=500)
    goals: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    owner_name: str = Field(default="", max_length=128)

    @field_validator("name", "owner_name", "personality", "communication_style")
    @classmethod
    def _strip(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("goals", "interests")
    @classmethod
    def _lists(cls, value: list[str]) -> list[str]:
        return _clean_list(value)


class ProfileUpdate(ApiModel):
    """All fields optional; only provided ones change. ``expected_version`` enables
    optimistic concurrency so a stale client (or, later, a stale device) cannot
    silently overwrite newer changes (spec §72)."""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    personality: str | None = Field(default=None, max_length=500)
    communication_style: str | None = Field(default=None, max_length=500)
    goals: list[str] | None = None
    interests: list[str] | None = None
    owner_name: str | None = Field(default=None, max_length=128)
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("goals", "interests")
    @classmethod
    def _lists(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_list(value)


class ProfileRead(ApiModel):
    ai_id: str
    name: str
    personality: str
    communication_style: str
    goals: list[str]
    interests: list[str]
    owner_name: str
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )
