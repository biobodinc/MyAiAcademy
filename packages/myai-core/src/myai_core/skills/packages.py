"""Skill packages: the bundled resources that ``/learn`` installs (spec §3, §36, §43)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from myai_core.schemas import ApiModel
from myai_core.skills.graders import CHECK_TYPES

BUNDLED_DIR = Path(__file__).parent / "packages"
MANIFEST = "skill.json"
INSTRUCTIONS = "instructions.md"
BENCHMARK = "benchmark.json"
PRACTICE = "practice.json"
TRAINED = "trained.md"


class BenchmarkTask(ApiModel):
    id: str
    area: str
    prompt: str
    checks: list[dict[str, Any]] = Field(min_length=1)
    max_tokens: int | None = Field(default=None, ge=8, le=2048)

    @field_validator("checks")
    @classmethod
    def _known_checks(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for check in value:
            if check.get("type") not in CHECK_TYPES:
                raise ValueError(f"unknown check type {check.get('type')!r}")
        return value


class Benchmark(ApiModel):
    version: str
    default_max_tokens: int = Field(default=128, ge=8, le=2048)
    tasks: list[BenchmarkTask] = Field(min_length=1)

    @property
    def areas(self) -> list[str]:
        seen: list[str] = []
        for task in self.tasks:
            if task.area not in seen:
                seen.append(task.area)
        return seen


class PracticeSet(ApiModel):
    """Tasks used to search for better instructions, never to set a level (Phase 4).

    Kept strictly apart from the benchmark: training selects on these, and the level is
    still measured on the benchmark the training loop never sees. An improvement that
    only exists on the tasks it was selected against is not an improvement.
    """

    version: str
    default_max_tokens: int = Field(default=128, ge=8, le=2048)
    tactics: list[str] = Field(
        default_factory=list,
        description="Guidance lines training may try. Each is kept only if it measures better.",
    )
    tasks: list[BenchmarkTask] = Field(min_length=4)


class SkillManifest(ApiModel):
    id: str
    version: str
    name: str
    license: str
    summary: str
    areas: list[str]
    resources: str


class SkillPackage(ApiModel):
    manifest: SkillManifest
    instructions: str
    benchmark: Benchmark
    practice: PracticeSet | None = Field(
        default=None, description="Absent for a package that cannot be trained yet."
    )
    path: str
    size_bytes: int

    @property
    def id(self) -> str:
        return self.manifest.id


class PackageError(ValueError):
    pass


def load_package(folder: Path) -> SkillPackage:
    try:
        manifest = SkillManifest.model_validate(
            json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
        )
        benchmark = Benchmark.model_validate(
            json.loads((folder / BENCHMARK).read_text(encoding="utf-8"))
        )
        instructions = (folder / INSTRUCTIONS).read_text(encoding="utf-8").strip()
        practice_file = folder / PRACTICE
        practice = (
            PracticeSet.model_validate(json.loads(practice_file.read_text(encoding="utf-8")))
            if practice_file.is_file()
            else None
        )
    except (OSError, ValueError) as exc:
        raise PackageError(f"Invalid skill package at {folder}: {exc}") from exc
    if set(manifest.areas) != set(benchmark.areas):
        raise PackageError(
            f"{manifest.id}: manifest areas {manifest.areas} differ from benchmark areas "
            f"{benchmark.areas}"
        )
    if practice is not None:
        shared = {t.id for t in practice.tasks} & {t.id for t in benchmark.tasks}
        if shared:
            raise PackageError(
                f"{manifest.id}: practice and benchmark share task ids {sorted(shared)}. "
                "Training must never select on a task the level is measured with."
            )
        unknown = {t.area for t in practice.tasks} - set(manifest.areas)
        if unknown:
            raise PackageError(f"{manifest.id}: practice uses unknown areas {sorted(unknown)}")
    size = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
    return SkillPackage(
        manifest=manifest,
        instructions=instructions,
        benchmark=benchmark,
        practice=practice,
        path=str(folder),
        size_bytes=size,
    )


def bundled_package(skill_id: str) -> SkillPackage | None:
    folder = BUNDLED_DIR / skill_id
    if not (folder / MANIFEST).is_file():
        return None
    return load_package(folder)


def bundled_skill_ids() -> list[str]:
    return sorted(p.name for p in BUNDLED_DIR.iterdir() if (p / MANIFEST).is_file())


def install_package(package: SkillPackage, skills_root: Path) -> Path:
    """Copy a package into ``Skills/<id>/<version>/`` and return that folder."""
    dest = skills_root / package.id / package.manifest.version
    dest.mkdir(parents=True, exist_ok=True)
    for name in (MANIFEST, INSTRUCTIONS, BENCHMARK, PRACTICE):
        source = Path(package.path) / name
        if source.is_file():
            shutil.copy2(source, dest / name)
    return dest
