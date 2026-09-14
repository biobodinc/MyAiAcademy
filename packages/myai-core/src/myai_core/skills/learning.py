"""Learning a skill (spec §3, §36, §88): install its package, benchmark it, set its level.

Honesty rules enforced here:

* A skill is *learned* only when its benchmark has run; installing files alone changes
  nothing visible (§36: "Do not falsely say it was learned if only resources were
  downloaded").
* Levels are written here and nowhere else (ADR-0007), always with an evaluation row.
* Creative skills without a measurable benchmark cannot be learned; the preview says so.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.audit.service import AuditCategory, AuditService
from myai_core.db.models import SkillEvaluation, SkillState
from myai_core.hardware.benchmark import BenchmarkResult
from myai_core.hardware.models import HardwareReport, HardwareTier
from myai_core.preferences.schemas import ComputePreset
from myai_core.schemas import ApiModel
from myai_core.skills.catalog import SkillDefinition, get_skill
from myai_core.skills.creative import all_statuses as all_creative_statuses
from myai_core.skills.evaluate import EvaluationOutcome, level_from_score
from myai_core.skills.packages import (
    INSTRUCTIONS,
    TRAINED,
    SkillPackage,
    bundled_package,
    install_package,
    load_package,
)
from myai_core.storage import StorageCategory, StorageManager

ESTIMATED_TOKENS_PER_TASK = 60
MAX_PROMPT_INSTRUCTION_CHARS = 8000
MAX_PROMPT_CHARS_PER_SKILL = 3000

RECOMMENDED_COMPUTE: dict[HardwareTier, ComputePreset] = {
    HardwareTier.ENTRY: ComputePreset.LOW,
    HardwareTier.BASIC: ComputePreset.BALANCED,
    HardwareTier.CAPABLE: ComputePreset.BALANCED,
    HardwareTier.POWERFUL: ComputePreset.HIGH,
    HardwareTier.WORKSTATION: ComputePreset.HIGH,
}


class PackageInfo(ApiModel):
    version: str
    size_bytes: int
    task_count: int
    areas: list[str]
    license: str
    resources: str


class LearnPreview(ApiModel):
    """What ``/learn <skill>`` shows before anything happens (spec §36)."""

    skill_id: str
    name: str
    icon: str
    already_learned: bool
    learnable: bool
    blockers: list[str] = Field(description="Why learning cannot start; empty when it can.")
    package: PackageInfo | None
    model_id: str | None
    recommended_compute: ComputePreset
    estimated_minutes_min: float | None
    estimated_minutes_max: float | None
    estimate_note: str
    what_happens: str


class EvaluationRead(ApiModel):
    id: int
    skill_id: str
    job_id: str | None
    model_id: str
    package_version: str
    score: float
    level_before: int
    level_after: int
    area_scores: dict[str, float]
    task_results: list[dict[str, object]]
    evaluated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LearningError(ValueError):
    pass


class SkillLearningService:
    def __init__(self, session: Session, ai_id: str, storage: StorageManager) -> None:
        self._session = session
        self._ai_id = ai_id
        self._storage = storage

    # --- state ------------------------------------------------------------------------------

    def state_for(self, skill_id: str) -> SkillState | None:
        return self._session.scalar(
            select(SkillState).where(
                SkillState.ai_id == self._ai_id, SkillState.skill_id == skill_id
            )
        )

    def levels(self) -> dict[str, int]:
        rows = self._session.scalars(select(SkillState).where(SkillState.ai_id == self._ai_id))
        return {row.skill_id: row.level for row in rows if row.status == "learned"}

    def is_learned(self, skill_id: str) -> bool:
        state = self.state_for(skill_id)
        return bool(state and state.status == "learned")

    # --- preview ----------------------------------------------------------------------------

    def preview(
        self,
        skill_id: str,
        *,
        hardware: HardwareReport | None,
        measured: BenchmarkResult | None,
        active_model_id: str | None,
        runtime_available: bool,
    ) -> LearnPreview:
        skill = self._require_skill(skill_id)
        package = bundled_package(skill_id)
        blockers: list[str] = []
        if package is None:
            blockers.append(_no_package_reason(skill))
        missing = [r for r in skill.requires if not self.is_learned(r)]
        if missing:
            blockers.append("Requires: " + ", ".join(m.title() for m in missing) + " first.")
        if not runtime_available:
            blockers.append("The local inference runtime is not available.")
        elif active_model_id is None:
            blockers.append("No local model is installed; learning runs a benchmark with it.")
        if self._storage.get_config() is None:
            blockers.append("Choose a MyAI storage location first.")
        already = self.is_learned(skill_id)
        tier = hardware.tier.tier if hardware else HardwareTier.ENTRY
        est_min = est_max = None
        note = "Run the hardware benchmark for a time estimate."
        if package is not None and measured and measured.inference:
            tps = measured.inference.generation_tokens_per_second
            first = measured.inference.prompt_seconds
            if tps > 0:
                per_task = first + ESTIMATED_TOKENS_PER_TASK / tps
                total = per_task * len(package.benchmark.tasks) / 60
                est_min, est_max = round(total * 0.7, 1), round(total * 1.6, 1)
                note = (
                    f"Based on {tps:g} tokens/s measured with {measured.inference.model_id}. "
                    "A range, not a promise."
                )
        return LearnPreview(
            skill_id=skill.id,
            name=skill.name,
            icon=skill.icon,
            already_learned=already,
            learnable=not blockers and not already,
            blockers=blockers,
            package=(
                PackageInfo(
                    version=package.manifest.version,
                    size_bytes=package.size_bytes,
                    task_count=len(package.benchmark.tasks),
                    areas=package.benchmark.areas,
                    license=package.manifest.license,
                    resources=package.manifest.resources,
                )
                if package
                else None
            ),
            model_id=active_model_id,
            recommended_compute=RECOMMENDED_COMPUTE[tier],
            estimated_minutes_min=est_min,
            estimated_minutes_max=est_max,
            estimate_note=note,
            what_happens=(
                f"Installs the {skill.name} package (instructions your AI follows from now on) "
                f"and runs its benchmark with your local model. The level it scores becomes "
                f"{skill.name}'s level. Nothing is downloaded and the model is not retrained."
            ),
        )

    # --- install / apply --------------------------------------------------------------------

    def install(self, skill_id: str) -> tuple[SkillPackage, Path]:
        package = bundled_package(skill_id)
        if package is None:
            raise LearningError(f"No skill package for '{skill_id}'.")
        root = self._storage.category_path(StorageCategory.SKILLS)
        path = install_package(package, root)
        state = self.state_for(skill_id)
        if state is None:
            state = SkillState(ai_id=self._ai_id, skill_id=skill_id, status="unlearned", level=0)
            self._session.add(state)
        state.package_version = package.manifest.version
        state.installed_path = str(path)
        self._session.flush()
        return package, path

    def installed_package(self, skill_id: str) -> SkillPackage:
        state = self.state_for(skill_id)
        if state is not None and state.installed_path and Path(state.installed_path).is_dir():
            try:
                return load_package(Path(state.installed_path))
            except ValueError:
                pass  # fall back to the bundled copy below
        package = bundled_package(skill_id)
        if package is None:
            raise LearningError(f"No skill package for '{skill_id}'.")
        return package

    def apply_evaluation(
        self,
        skill_id: str,
        outcome: EvaluationOutcome,
        *,
        model_id: str,
        package_version: str,
        job_id: str | None,
    ) -> SkillEvaluation:
        """Record the run and set the level. The one and only level writer (ADR-0007)."""
        state = self.state_for(skill_id)
        if state is None:
            state = SkillState(ai_id=self._ai_id, skill_id=skill_id, status="unlearned", level=0)
            self._session.add(state)
            self._session.flush()
        before = state.level
        after = level_from_score(outcome.score)
        first_time = state.status != "learned"
        state.status = "learned"
        state.level = after
        state.last_evaluation_score = outcome.score
        state.version += 1
        if first_time:
            state.learned_at = datetime.now(tz=UTC)
        row = SkillEvaluation(
            ai_id=self._ai_id,
            skill_id=skill_id,
            job_id=job_id,
            model_id=model_id,
            package_version=package_version,
            score=outcome.score,
            level_before=before,
            level_after=after,
            area_scores=dict(outcome.area_scores),
            task_results=[t.model_dump() for t in outcome.tasks],
        )
        self._session.add(row)
        self._session.flush()
        skill = get_skill(skill_id)
        name = skill.name if skill else skill_id
        AuditService(self._session).record(
            AuditCategory.SYSTEM,
            "skill_learned" if first_time else "skill_evaluated",
            (
                f"{name} learned at level {after}"
                if first_time
                else f"{name} re-evaluated: level {before} → {after}"
            ),
            {
                "skill_id": skill_id,
                "score": outcome.score,
                "level_before": before,
                "level_after": after,
                "model_id": model_id,
            },
        )
        return row

    # --- history / prompt ---------------------------------------------------------------------

    def history(self, skill_id: str | None = None, limit: int = 50) -> list[SkillEvaluation]:
        stmt = select(SkillEvaluation).where(SkillEvaluation.ai_id == self._ai_id)
        if skill_id is not None:
            stmt = stmt.where(SkillEvaluation.skill_id == skill_id)
        stmt = stmt.order_by(SkillEvaluation.evaluated_at.desc(), SkillEvaluation.id.desc())
        return list(self._session.scalars(stmt.limit(limit)).all())

    def latest_area_scores(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for row in self.history(limit=500):
            if row.skill_id not in out:
                out[row.skill_id] = {k: float(v) for k, v in row.area_scores.items()}  # type: ignore[arg-type]
        return out

    def instructions_for_prompt(self) -> list[str]:
        """Instruction texts of learned skills, in catalog order, capped in size.

        Trained instructions are longer than the package's own, and the prompt cannot grow
        without limit. When a skill's trained text will not fit what is left, its package
        instructions are used instead of dropping the skill altogether: the skill keeps its
        own voice, it just loses the practised additions. A skill is skipped only when even
        that does not fit.
        """
        texts: list[str] = []
        budget = MAX_PROMPT_INSTRUCTION_CHARS
        rows = self._session.scalars(
            select(SkillState).where(
                SkillState.ai_id == self._ai_id, SkillState.status == "learned"
            )
        ).all()
        for state in sorted(rows, key=lambda r: r.skill_id):
            trained = _read_instructions(state.installed_path, state.skill_id)
            base = _read_instructions(None, state.skill_id)
            for text in (trained, base):
                if text and len(text) <= min(budget, MAX_PROMPT_CHARS_PER_SKILL):
                    budget -= len(text)
                    texts.append(text)
                    break
        return texts

    def _require_skill(self, skill_id: str) -> SkillDefinition:
        skill = get_skill(skill_id)
        if skill is None:
            raise LearningError(f"Unknown skill '{skill_id}'.")
        return skill


def _read_instructions(installed_path: str | None, skill_id: str) -> str:
    """The instructions this skill contributes to the chat prompt.

    Training writes its result to ``trained.md`` beside the package rather than over
    ``instructions.md``, so what the package shipped is always recoverable and a trained
    skill can be put back exactly as it was.
    """
    if installed_path:
        folder = Path(installed_path)
        for name in (TRAINED, INSTRUCTIONS):
            try:
                text = (folder / name).read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if text:
                return text
    package = bundled_package(skill_id)
    return package.instructions if package else ""


def _no_package_reason(skill: SkillDefinition) -> str:
    """Why a skill cannot be learned, naming the actual obstacle rather than a phase number.

    Images, video and music are not waiting on a benchmark; they are waiting on something
    that can produce a picture or a sound, which this build has none of and will not
    substitute an online service for. Saying "planned for Phase 10" would hide that.
    """
    for status in all_creative_statuses():
        if status.skill_id == skill.id and not status.available:
            return f"{skill.name} cannot be learned here. {status.detail} Needs: {status.needs}"
    return (
        f"{skill.name} has no skill package yet: there is no measurable benchmark for it in "
        f"this build (planned for Phase {skill.planned_phase})."
    )
