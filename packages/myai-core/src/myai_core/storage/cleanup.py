"""Storage cleanup (spec §63): find reclaimable files and delete only what the user picked.

Rules that keep this safe:

* Only files inside the managed category folders are ever considered, resolved with
  symlinks followed so nothing outside the storage root can be reached.
* Deletion accepts *paths from the candidate list only*; a path the scan did not
  produce is refused, so a stale UI or a typo cannot delete arbitrary files.
* Candidates under protected categories (checkpoints, training data, memory) require an
  explicit acknowledgement flag; without it the request is refused with the warning.
* Every deletion is written to the audit log with the path and size, never contents.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from myai_core.schemas import ApiModel
from myai_core.storage.layout import PROTECTED_CATEGORIES, StorageCategory

PARTIAL_SUFFIX = ".part"
MODEL_SUFFIXES = frozenset({".gguf", ".safetensors", ".bin"})


class CleanupKind(StrEnum):
    PARTIAL_DOWNLOAD = "partial_download"
    ORPHANED_MODEL = "orphaned_model"


KIND_DESCRIPTIONS: dict[CleanupKind, str] = {
    CleanupKind.PARTIAL_DOWNLOAD: (
        "An interrupted download. Deleting it means the download restarts from zero "
        "instead of resuming."
    ),
    CleanupKind.ORPHANED_MODEL: (
        "A model file that MyAI does not track (removed from the catalog or copied in by "
        "hand). Import it under Models to use it, or delete it here."
    ),
}


class CleanupCandidate(ApiModel):
    path: str
    category: StorageCategory
    kind: CleanupKind
    size_bytes: int
    protected: bool = Field(description="Under a category that warns before deletion.")
    reason: str


class CleanupPlan(ApiModel):
    candidates: list[CleanupCandidate]
    reclaimable_bytes: int
    protected_bytes: int


class CleanupRequest(ApiModel):
    paths: list[str] = Field(min_length=1, max_length=500)
    acknowledge_protected: bool = Field(
        default=False,
        description="Must be true to delete anything under a protected category.",
    )


class CleanupResult(ApiModel):
    deleted: list[str]
    freed_bytes: int
    refused: list[str] = Field(description="Paths that were not deleted and why.")


class ProtectedDeletionError(ValueError):
    """Refusing to delete protected resources without acknowledgement (spec §63)."""


def find_candidates(
    category_paths: dict[StorageCategory, Path], tracked_model_files: Iterable[str]
) -> CleanupPlan:
    tracked = {_resolve(Path(p)) for p in tracked_model_files}
    candidates: list[CleanupCandidate] = []
    for category, folder in category_paths.items():
        if not folder.is_dir():
            continue
        protected = category in PROTECTED_CATEGORIES
        for file in _walk_files(folder):
            kind = _classify(category, file, tracked)
            if kind is None:
                continue
            try:
                size = file.stat().st_size
            except OSError:
                continue
            candidates.append(
                CleanupCandidate(
                    path=str(file),
                    category=category,
                    kind=kind,
                    size_bytes=size,
                    protected=protected,
                    reason=KIND_DESCRIPTIONS[kind],
                )
            )
    candidates.sort(key=lambda c: (-c.size_bytes, c.path))
    return CleanupPlan(
        candidates=candidates,
        reclaimable_bytes=sum(c.size_bytes for c in candidates),
        protected_bytes=sum(c.size_bytes for c in candidates if c.protected),
    )


def delete_candidates(plan: CleanupPlan, request: CleanupRequest) -> CleanupResult:
    """Delete the requested subset of ``plan``. Unknown paths are refused, not deleted."""
    by_path = {c.path: c for c in plan.candidates}
    chosen = [by_path.get(p) for p in request.paths]
    wanted = [c for c in chosen if c is not None]
    refused = [
        f"{p}: not in the current cleanup list"
        for p, c in zip(request.paths, chosen, strict=True)
        if c is None
    ]

    protected = [c for c in wanted if c.protected]
    if protected and not request.acknowledge_protected:
        names = ", ".join(Path(c.path).name for c in protected[:3])
        more = "" if len(protected) <= 3 else f" and {len(protected) - 3} more"
        raise ProtectedDeletionError(
            f"{names}{more} belong to protected training resources. Confirm that you "
            "understand they cannot be recovered before deleting."
        )

    deleted: list[str] = []
    freed = 0
    for candidate in wanted:
        path = Path(candidate.path)
        try:
            if path.is_symlink() or not path.is_file():
                refused.append(f"{candidate.path}: not a regular file any more")
                continue
            path.unlink()
        except OSError as exc:
            refused.append(f"{candidate.path}: {exc.strerror or exc}")
            continue
        deleted.append(candidate.path)
        freed += candidate.size_bytes
    return CleanupResult(deleted=deleted, freed_bytes=freed, refused=refused)


def _classify(category: StorageCategory, file: Path, tracked: set[Path]) -> CleanupKind | None:
    if file.name.endswith(PARTIAL_SUFFIX):
        return CleanupKind.PARTIAL_DOWNLOAD
    if category is StorageCategory.MODELS and file.suffix.lower() in MODEL_SUFFIXES:
        return None if _resolve(file) in tracked else CleanupKind.ORPHANED_MODEL
    return None


def _walk_files(folder: Path) -> Iterable[Path]:
    stack = [folder]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue  # never follow links out of the managed tree
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            yield Path(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path
