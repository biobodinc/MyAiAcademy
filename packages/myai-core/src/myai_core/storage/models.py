from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from myai_core.storage.layout import StorageCategory


class CategoryUsage(BaseModel):
    category: StorageCategory
    path: str
    bytes_used: int
    file_count: int
    exists: bool
    protected: bool = Field(
        description="Warn before deleting (checkpoints, training data, memory)."
    )


class StorageOverview(BaseModel):
    configured: bool
    root_path: str | None
    categories: list[CategoryUsage]
    total_bytes_used: int
    volume_total_bytes: int | None = None
    volume_free_bytes: int | None = None
    configured_at: datetime | None = None
    category_overrides: dict[str, str] = Field(default_factory=dict)


class StorageLocationCheck(BaseModel):
    """Result of validating a candidate storage root before committing to it."""

    path: str
    ok: bool
    problems: list[str] = Field(default_factory=list)
    is_existing_myai_storage: bool = False
    free_bytes: int | None = None
    total_bytes: int | None = None
    is_removable: bool | None = None


class StorageSetupRequest(BaseModel):
    root_path: str = Field(min_length=1)


class CategoryOverrideRequest(BaseModel):
    category: StorageCategory
    path: str | None = Field(default=None, description="``None`` clears the override.")
