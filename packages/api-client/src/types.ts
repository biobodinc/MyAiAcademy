/**
 * Friendly aliases over the generated OpenAPI schema types.
 * Regenerate with `pnpm api:export && pnpm api:types` after changing the Python API.
 */
import type { components } from "./generated/schema";

type Schemas = components["schemas"];

export type ServiceStatus = Schemas["ServiceStatus"];
export type Availability = Schemas["Availability"];
export type HardwareReport = Schemas["HardwareReport"];
export type GpuInfo = Schemas["GpuInfo"];
export type StorageVolume = Schemas["StorageVolume"];
export type HardwareTier = Schemas["HardwareTier"];
export type StorageOverview = Schemas["StorageOverview"];
export type StorageLocationCheck = Schemas["StorageLocationCheck"];
export type CategoryUsage = Schemas["CategoryUsage"];
export type StorageCategory = Schemas["StorageCategory"];
export type ProfileRead = Schemas["ProfileRead"];
export type ProfileCreate = Schemas["ProfileCreate"];
export type ProfileUpdate = Schemas["ProfileUpdate"];
export type Preferences = Schemas["Preferences"];
export type PreferencesUpdate = Schemas["PreferencesUpdate"];
export type ExperienceMode = Schemas["ExperienceMode"];
export type ComputePreset = Schemas["ComputePreset"];
export type Theme = Schemas["Theme"];
export type OnboardingStep = Schemas["OnboardingStep"];
export type SkillsSummary = Schemas["SkillsSummary"];
export type SkillStatus = Schemas["SkillStatus"];
export type LevelBand = Schemas["LevelBand"];
export type CommandResult = Schemas["CommandResult"];
export type CommandOutcome = Schemas["CommandOutcome"];
export type ParsedCommand = Schemas["ParsedCommand"];
export type AuditEventRead = Schemas["AuditEventRead"];
export type PrivacySummary = Schemas["PrivacySummary"];
