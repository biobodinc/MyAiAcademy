from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from myai_core.schemas import ApiModel


class ExperienceMode(StrEnum):
    BEGINNER = "beginner"
    ADVANCED = "advanced"


class ComputePreset(StrEnum):
    """Spec §31. Percentages are the share of GPU/CPU a job may use."""

    LOW = "low"  # 25 %
    BALANCED = "balanced"  # 50 %
    HIGH = "high"  # 75 %
    MAXIMUM = "maximum"  # 100 %


COMPUTE_PRESET_PERCENT: dict[ComputePreset, int] = {
    ComputePreset.LOW: 25,
    ComputePreset.BALANCED: 50,
    ComputePreset.HIGH: 75,
    ComputePreset.MAXIMUM: 100,
}


class Theme(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class PrivacyMode(StrEnum):
    """Only ``private`` exists. Contributor mode (spec §9) is an additional opt-in flag,
    never a replacement for private mode."""

    PRIVATE = "private"


class OnboardingStep(StrEnum):
    WELCOME = "welcome"
    NAME_AI = "name_ai"
    INTERESTS = "interests"
    HARDWARE_SCAN = "hardware_scan"
    STORAGE = "storage"
    PRIVACY = "privacy"
    ACCOUNT = "account"  # optional; Phase 5
    LOCAL_MODEL = "local_model"  # Phase 2
    DONE = "done"


class AdvancedComputeSettings(ApiModel):
    """Spec §31 advanced controls. Each is ``None`` until the user sets it, in which case
    it overrides what the compute preset would choose. Which ones are enforced today is
    stated per field so nothing is silently ignored:

    * ``cpu_utilization_percent`` - enforced now: caps inference threads.
    * ``ram_limit_gib`` - enforced now: a model whose file is larger than this is refused.
    * ``gpu_utilization_percent``, ``temperature_limit_c``, ``time_limit_minutes`` -
      stored now, consumed by training jobs (Phase 4). The UI labels them as such.
    """

    cpu_utilization_percent: int | None = Field(default=None, ge=10, le=100)
    gpu_utilization_percent: int | None = Field(default=None, ge=10, le=100)
    ram_limit_gib: float | None = Field(default=None, ge=1, le=4096)
    temperature_limit_c: int | None = Field(default=None, ge=50, le=100)
    time_limit_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 30)


ADVANCED_KEYS: frozenset[str] = frozenset(AdvancedComputeSettings.model_fields)
"""Preference keys that may be *cleared* by sending ``null``."""


class Preferences(AdvancedComputeSettings):
    experience_mode: ExperienceMode = ExperienceMode.BEGINNER
    compute_preset: ComputePreset = ComputePreset.BALANCED
    theme: Theme = Theme.SYSTEM
    privacy_mode: PrivacyMode = PrivacyMode.PRIVATE
    contributor_mode: bool = Field(
        default=False,
        description="Explicit opt-in to community contribution (spec §9). Default OFF.",
    )
    onboarding_step: OnboardingStep = OnboardingStep.WELCOME
    onboarding_completed: bool = False


class PreferencesUpdate(AdvancedComputeSettings):
    """All fields optional. Advanced fields accept ``null`` to clear an override."""

    experience_mode: ExperienceMode | None = None
    compute_preset: ComputePreset | None = None
    theme: Theme | None = None
    contributor_mode: bool | None = None
    onboarding_step: OnboardingStep | None = None
    onboarding_completed: bool | None = None
