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
    except (OSError, ValueError) as exc:
        raise PackageError(f"Invalid skill package at {folder}: {exc}") from exc
    if set(manifest.areas) != set(benchmark.areas):
        raise PackageError(
            f"{manifest.id}: manifest areas {manifest.areas} differ from benchmark areas "
            f"{benchmark.areas}"
        )
    size = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
    return SkillPackage(
        manifest=manifest,
        instructions=instructions,
        benchmark=benchmark,
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
    for name in (MANIFEST, INSTRUCTIONS, BENCHMARK):
        shutil.copy2(Path(package.path) / name, dest / name)
    return dest
