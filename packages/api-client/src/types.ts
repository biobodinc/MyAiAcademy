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
export type SystemMetrics = Schemas["SystemMetrics"];
export type GpuMetrics = Schemas["GpuMetrics"];
export type BatteryMetrics = Schemas["BatteryMetrics"];
export type BenchmarkResult = Schemas["BenchmarkResult"];
export type InferenceBenchmark = Schemas["InferenceBenchmark"];
export type CleanupPlan = Schemas["CleanupPlan"];
export type CleanupCandidate = Schemas["CleanupCandidate"];
export type CleanupRequest = Schemas["CleanupRequest"];
export type CleanupResult = Schemas["CleanupResult"];
export type GuideAnswer = Schemas["GuideAnswer"];
export type GuideTopicRead = Schemas["GuideTopicRead"];
export type JobRead = Schemas["JobRead"];
export type JobSummary = Schemas["JobSummary"];
export type LearnPreview = Schemas["LearnPreview"];
export type EvaluationRead = Schemas["EvaluationRead"];
export type TrainPreview = Schemas["TrainPreview"];
export type TrainRequest = Schemas["TrainRequest"];
export type TrainingRunRead = Schemas["TrainingRunRead"];
export type TrainRoundRead = Schemas["TrainRoundRead"];
export type SecurityOverview = Schemas["SecurityOverview"];
export type DeviceRead = Schemas["DeviceRead"];
export type IssuedCredential = Schemas["IssuedCredential"];
export type PairingCodeRead = Schemas["PairingCodeRead"];
export type AccountState = Schemas["AccountState"];
export type SecretStorageReport = Schemas["SecretStorageReport"];
export type ExportRequest = Schemas["ExportRequest"];
export type ExportResult = Schemas["ExportResult"];
export type EraseRequest = Schemas["EraseRequest"];
export type ErasePlan = Schemas["ErasePlan"];
export type EraseResult = Schemas["EraseResult"];
export type DegreeStatus = Schemas["DegreeStatus"];
export type AchievementStatus = Schemas["AchievementStatus"];
export type SkillPackageInfo = Schemas["SkillPackageInfo"];
