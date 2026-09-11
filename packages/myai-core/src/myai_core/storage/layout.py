"""The application-managed directory layout under the MyAI storage root.

MyAI/
├── Core/          runtime files owned by the app (never user-edited)
├── Models/        downloaded foundation/skill models
├── Skills/        skill packages (datasets, adapters, evaluation packs)
├── Training/      staged training data and job working directories
├── Checkpoints/   LoRA/adapter checkpoints produced by training
├── Memory/        local memory store exports/indexes
├── Knowledge/     user documents and their retrieval indexes
├── Projects/      first-class project folders
└── Generated/     generated media and artefacts

Each category may be redirected to another location (e.g. an external SSD) via
``StorageConfig.category_overrides``. The app never repartitions disks.
"""

from __future__ import annotations

from enum import StrEnum


class StorageCategory(StrEnum):
    CORE = "core"
    MODELS = "models"
    SKILLS = "skills"
    TRAINING = "training"
    CHECKPOINTS = "checkpoints"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    PROJECTS = "projects"
    GENERATED = "generated"


STORAGE_CATEGORIES: dict[StorageCategory, str] = {
    StorageCategory.CORE: "Core",
    StorageCategory.MODELS: "Models",
    StorageCategory.SKILLS: "Skills",
    StorageCategory.TRAINING: "Training",
    StorageCategory.CHECKPOINTS: "Checkpoints",
    StorageCategory.MEMORY: "Memory",
    StorageCategory.KNOWLEDGE: "Knowledge",
    StorageCategory.PROJECTS: "Projects",
    StorageCategory.GENERATED: "Generated",
}

ROOT_MARKER_FILE = ".myai-storage"
"""Written into the root so a re-attached drive can be recognised as MyAI storage."""

# Categories the user should be warned about before deleting (spec §63).
PROTECTED_CATEGORIES = frozenset(
    {StorageCategory.CHECKPOINTS, StorageCategory.TRAINING, StorageCategory.MEMORY}
)
