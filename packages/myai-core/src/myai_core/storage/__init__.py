"""User-chosen MyAI storage root and its managed directory layout (spec §21–§22, §63)."""

from myai_core.storage.layout import STORAGE_CATEGORIES, StorageCategory
from myai_core.storage.manager import StorageManager

__all__ = ["STORAGE_CATEGORIES", "StorageCategory", "StorageManager"]
