from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


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


class Preferences(BaseModel):
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


class PreferencesUpdate(BaseModel):
    experience_mode: ExperienceMode | None = None
    compute_preset: ComputePreset | None = None
    theme: Theme | None = None
    contributor_mode: bool | None = None
    onboarding_step: OnboardingStep | None = None
    onboarding_completed: bool | None = None
