/**
 * React Query hooks over the typed local-service client.
 * Query keys are centralised so mutations can invalidate precisely.
 */
import {
  ApiError,
  createLocalServiceClient,
  type CleanupRequest,
  type CommandResult,
  type GuideAnswer,
  type ImportRequest,
  type PreferencesUpdate,
  type ProfileCreate,
  type ProfileUpdate,
  type StorageCategory,
  type EraseRequest,
  type ExportRequest,
  type NetworkAccessRequest,
  type PackageRequest,
  type PreviewRequest,
  type RestoreRequest,
  type TrainRequest,
} from "@myai/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getServiceCredentials } from "./tauri";

export const api = createLocalServiceClient(async () => {
  const creds = await getServiceCredentials();
  return { baseUrl: creds.base_url, token: creds.token };
});

export const keys = {
  status: ["status"] as const,
  hardware: ["hardware"] as const,
  metrics: ["hardware", "metrics"] as const,
  benchmark: ["hardware", "benchmark"] as const,
  cleanup: ["storage", "cleanup"] as const,
  guideTopics: ["guide", "topics"] as const,
  storage: ["storage"] as const,
  storageCheck: (path: string) => ["storage", "check", path] as const,
  externalCandidates: ["storage", "external"] as const,
  profile: ["profile"] as const,
  preferences: ["preferences"] as const,
  skills: ["skills"] as const,
  audit: ["audit"] as const,
  privacy: ["privacy"] as const,
};

async function unwrap<T>(promise: Promise<{ data?: T; error?: unknown }>): Promise<T> {
  const { data, error } = await promise;
  if (error) throw error instanceof Error ? error : new Error(JSON.stringify(error));
  return data as T;
}

export function useStatus(refetchInterval = 10_000) {
  return useQuery({
    queryKey: keys.status,
    queryFn: () => unwrap(api.GET("/api/status")),
    refetchInterval,
  });
}

export function useHardware() {
  return useQuery({
    queryKey: keys.hardware,
    queryFn: () => unwrap(api.GET("/api/hardware")),
    staleTime: 60_000,
  });
}

export function useRefreshHardware() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.GET("/api/hardware", { params: { query: { refresh: true } } })),
    onSuccess: (data) => qc.setQueryData(keys.hardware, data),
  });
}

/** Whole-machine utilisation; polled while the dashboard is visible. */
export function useMetrics(refetchInterval: number | false = 5_000) {
  return useQuery({
    queryKey: keys.metrics,
    queryFn: () => unwrap(api.GET("/api/hardware/metrics")),
    refetchInterval,
  });
}

export function useBenchmark() {
  return useQuery({
    queryKey: keys.benchmark,
    queryFn: () => unwrap(api.GET("/api/hardware/benchmark")),
  });
}

export function useRunBenchmark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/hardware/benchmark")),
    onSuccess: (data) => {
      qc.setQueryData(keys.benchmark, data);
      void qc.invalidateQueries({ queryKey: keys.hardware });
      void qc.invalidateQueries({ queryKey: keys.audit });
    },
  });
}

export function useCleanupPlan() {
  return useQuery({
    queryKey: keys.cleanup,
    queryFn: () => unwrap(api.GET("/api/storage/cleanup")),
  });
}

export function useRunCleanup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CleanupRequest) => unwrap(api.POST("/api/storage/cleanup", { body })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.cleanup });
      void qc.invalidateQueries({ queryKey: keys.storage });
      void qc.invalidateQueries({ queryKey: keys.audit });
    },
  });
}

export function useGuideTopics() {
  return useQuery({
    queryKey: keys.guideTopics,
    queryFn: () => unwrap(api.GET("/api/guide/topics")),
    staleTime: Infinity,
  });
}

export function useAskGuide() {
  return useMutation({
    mutationFn: (question: string): Promise<GuideAnswer> =>
      unwrap(api.POST("/api/guide/ask", { body: { question } })),
  });
}

export function useStorage() {
  return useQuery({ queryKey: keys.storage, queryFn: () => unwrap(api.GET("/api/storage")) });
}

export function useStorageCheck(path: string) {
  return useQuery({
    queryKey: keys.storageCheck(path),
    queryFn: () => unwrap(api.GET("/api/storage/check", { params: { query: { path } } })),
    enabled: path.trim().length > 0,
    retry: false,
  });
}

export function useExternalCandidates() {
  return useQuery({
    queryKey: keys.externalCandidates,
    queryFn: () => unwrap(api.GET("/api/storage/external-candidates")),
  });
}

export function useConfigureStorageRoot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (root_path: string) =>
      unwrap(api.PUT("/api/storage/root", { body: { root_path } })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.storage });
      void qc.invalidateQueries({ queryKey: keys.status });
      void qc.invalidateQueries({ queryKey: keys.audit });
    },
  });
}

export function useSetCategoryOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { category: StorageCategory; path: string | null }) =>
      unwrap(api.PUT("/api/storage/overrides", { body: input })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.storage }),
  });
}

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: () => unwrap(api.GET("/api/profile")) });
}

export function useCreateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileCreate) => unwrap(api.POST("/api/profile", { body })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.profile });
      void qc.invalidateQueries({ queryKey: keys.status });
      void qc.invalidateQueries({ queryKey: keys.skills });
    },
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileUpdate) => unwrap(api.PATCH("/api/profile", { body })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.profile });
      void qc.invalidateQueries({ queryKey: keys.audit });
    },
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: keys.preferences,
    queryFn: () => unwrap(api.GET("/api/preferences")),
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PreferencesUpdate) => unwrap(api.PATCH("/api/preferences", { body })),
    onSuccess: (data) => {
      qc.setQueryData(keys.preferences, data);
      void qc.invalidateQueries({ queryKey: keys.status });
      void qc.invalidateQueries({ queryKey: keys.privacy });
      void qc.invalidateQueries({ queryKey: keys.audit });
    },
  });
}

export function useSkills() {
  return useQuery({ queryKey: keys.skills, queryFn: () => unwrap(api.GET("/api/skills")) });
}

// --- Phase 3: skills, jobs ----------------------------------------------------------------

export const securityKeys = {
  overview: ["security"] as const,
  devices: ["security", "devices"] as const,
  erasePreview: ["privacy", "erase-preview"] as const,
};

export const syncKeys = {
  overview: ["sync"] as const,
  conflicts: ["sync", "conflicts"] as const,
};

function invalidateSecurity(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: securityKeys.overview });
  void qc.invalidateQueries({ queryKey: securityKeys.devices });
  void qc.invalidateQueries({ queryKey: keys.audit });
  void qc.invalidateQueries({ queryKey: keys.privacy });
}

export const skillKeys = {
  learnPreview: (id: string) => ["skills", "learn-preview", id] as const,
  evaluations: (id: string) => ["skills", "evaluations", id] as const,
  trainPreview: (id: string, request: TrainRequest) =>
    ["skills", "train-preview", id, request] as const,
  training: (id: string) => ["skills", "training", id] as const,
  history: ["skills", "history"] as const,
  jobs: ["jobs"] as const,
  currentJob: ["jobs", "current"] as const,
};

function invalidateSkills(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: keys.skills });
  void qc.invalidateQueries({ queryKey: ["skills"] });
  void qc.invalidateQueries({ queryKey: skillKeys.jobs });
  void qc.invalidateQueries({ queryKey: keys.status });
  void qc.invalidateQueries({ queryKey: keys.audit });
}

export function useLearnPreview(skillId: string | null) {
  return useQuery({
    queryKey: skillKeys.learnPreview(skillId ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/skills/{skill_id}/learn-preview", {
          params: { path: { skill_id: skillId ?? "" } },
        }),
      ),
    enabled: skillId !== null,
  });
}

export function useStartLearn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skill_id: string) =>
      unwrap(api.POST("/api/skills/{skill_id}/learn", { params: { path: { skill_id } } })),
    onSuccess: () => {
      invalidateSkills(qc);
    },
  });
}

export function useStartEvaluate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skill_id: string) =>
      unwrap(api.POST("/api/skills/{skill_id}/evaluate", { params: { path: { skill_id } } })),
    onSuccess: () => {
      invalidateSkills(qc);
    },
  });
}

export function useEvaluations(skillId: string | null) {
  return useQuery({
    queryKey: skillKeys.evaluations(skillId ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/skills/{skill_id}/evaluations", {
          params: { path: { skill_id: skillId ?? "" } },
        }),
      ),
    enabled: skillId !== null,
  });
}

/** What training would do with these qualifiers. Starts nothing. */
export function useTrainPreview(skillId: string | null, request: TrainRequest) {
  return useQuery({
    queryKey: skillKeys.trainPreview(skillId ?? "", request),
    queryFn: () =>
      unwrap(
        api.POST("/api/skills/{skill_id}/train-preview", {
          params: { path: { skill_id: skillId ?? "" } },
          body: request,
        }),
      ),
    enabled: skillId !== null,
  });
}

export function useStartTrain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ skill_id, request }: { skill_id: string; request: TrainRequest }) =>
      unwrap(
        api.POST("/api/skills/{skill_id}/train", {
          params: { path: { skill_id } },
          body: request,
        }),
      ),
    onSuccess: () => {
      invalidateSkills(qc);
    },
  });
}

export function useTrainingRuns(skillId: string | null) {
  return useQuery({
    queryKey: skillKeys.training(skillId ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/skills/{skill_id}/training", {
          params: { path: { skill_id: skillId ?? "" } },
        }),
      ),
    enabled: skillId !== null,
  });
}

/** Put back the instructions the package shipped with. The level is left as measured. */
export function useRevertTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skill_id: string) =>
      unwrap(
        api.POST("/api/skills/{skill_id}/training/revert", { params: { path: { skill_id } } }),
      ),
    onSuccess: () => {
      invalidateSkills(qc);
    },
  });
}

/** Who may act as this AI, and how this installation's secrets are stored. */
export function useSecurityOverview() {
  return useQuery({
    queryKey: securityKeys.overview,
    queryFn: () => unwrap(api.GET("/api/security")),
  });
}

export function useDevices() {
  return useQuery({
    queryKey: securityKeys.devices,
    queryFn: () => unwrap(api.GET("/api/security/devices")),
  });
}

export function useSyncOverview() {
  return useQuery({
    queryKey: syncKeys.overview,
    queryFn: () => unwrap(api.GET("/api/sync")),
  });
}

export function useSyncConflicts() {
  return useQuery({
    queryKey: syncKeys.conflicts,
    queryFn: () => unwrap(api.GET("/api/sync/conflicts")),
  });
}

export function useDismissConflict() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(
        api.POST("/api/sync/conflicts/{conflict_id}/dismiss", {
          params: { path: { conflict_id: id } },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: syncKeys.conflicts });
      void qc.invalidateQueries({ queryKey: syncKeys.overview });
    },
  });
}

export function useCreatePairingCode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label: string) =>
      unwrap(api.POST("/api/security/pairing-codes", { body: { label } })),
    onSuccess: () => {
      invalidateSecurity(qc);
    },
  });
}

export function useRevokeDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ device_id, reason }: { device_id: string; reason: string }) =>
      unwrap(
        api.POST("/api/security/devices/{device_id}/revoke", {
          params: { path: { device_id } },
          body: { reason },
        }),
      ),
    onSuccess: () => {
      invalidateSecurity(qc);
    },
  });
}

/** Turn network access for paired devices on or off. Owner only, and audited. */
export function useSetNetworkAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NetworkAccessRequest) => unwrap(api.POST("/api/security/network", { body })),
    onSuccess: () => {
      invalidateSecurity(qc);
    },
  });
}

/** A pairing code together with the certificate a device should pin. */
export function useCreatePairingInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label: string) =>
      unwrap(api.POST("/api/security/pairing-invite", { body: { label } })),
    onSuccess: () => {
      invalidateSecurity(qc);
    },
  });
}

export function useErasePreview() {
  return useQuery({
    queryKey: securityKeys.erasePreview,
    queryFn: () => unwrap(api.GET("/api/privacy/erase-preview")),
  });
}

/** Write a portable `.myai` package of this AI. */
export function useWritePackage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PackageRequest) => unwrap(api.POST("/api/portable", { body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.audit }),
  });
}

/** Read a package and report what importing it would do. Changes nothing. */
export function usePreviewPackage() {
  return useMutation({
    mutationFn: (body: PreviewRequest) => unwrap(api.POST("/api/portable/preview", { body })),
  });
}

/** Replaces this installation's AI. The caller must have collected the typed confirmation. */
export function useRestorePackage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RestoreRequest) => unwrap(api.POST("/api/portable/import", { body })),
    onSuccess: () => void qc.invalidateQueries(),
  });
}

export function useExportData() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ExportRequest) => unwrap(api.POST("/api/privacy/export", { body })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.audit });
    },
  });
}

/** Deletes everything, irreversibly. The caller must have collected the confirmation. */
export function useEraseData() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EraseRequest) => unwrap(api.POST("/api/privacy/erase", { body })),
    onSuccess: () => {
      void qc.invalidateQueries();
    },
  });
}

export function useSkillHistory(limit = 30) {
  return useQuery({
    queryKey: [...skillKeys.history, limit] as const,
    queryFn: () => unwrap(api.GET("/api/skills/history", { params: { query: { limit } } })),
  });
}

/** The running job, polled while one exists. */
export function useCurrentJob(refetchInterval: number | false = 1_000) {
  return useQuery({
    queryKey: skillKeys.currentJob,
    queryFn: () => unwrap(api.GET("/api/jobs/current")),
    refetchInterval: (q) => (q.state.data ? refetchInterval : 5_000),
  });
}

export function useJobs(limit = 20) {
  return useQuery({
    queryKey: [...skillKeys.jobs, limit] as const,
    queryFn: () => unwrap(api.GET("/api/jobs", { params: { query: { limit } } })),
  });
}

export function useJobAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { job_id: string; action: "pause" | "resume" | "cancel" }) =>
      unwrap(
        api.POST(`/api/jobs/{job_id}/${input.action}` as "/api/jobs/{job_id}/pause", {
          params: { path: { job_id: input.job_id } },
        }),
      ),
    onSuccess: () => {
      invalidateSkills(qc);
    },
  });
}

export function useAudit(limit = 100) {
  return useQuery({
    queryKey: [...keys.audit, limit],
    queryFn: () => unwrap(api.GET("/api/audit", { params: { query: { limit } } })),
  });
}

export function usePrivacy() {
  return useQuery({ queryKey: keys.privacy, queryFn: () => unwrap(api.GET("/api/privacy")) });
}

export function useRunCommand() {
  return useMutation({
    mutationFn: (text: string): Promise<CommandResult> =>
      unwrap(api.POST("/api/commands", { body: { text } })),
  });
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error) return error.message;
  return String(error);
}

// --- Phase 2: local AI --------------------------------------------------------------------

import type {
  ChatStreamEvents,
  DocumentAddPathBody,
  MemoryCategory,
  MemoryUpdate,
  SseEvent,
} from "./local-ai-types";
import { streamSse } from "@myai/api-client";

export const localAiKeys = {
  models: ["models"] as const,
  recommendedModel: ["models", "recommended"] as const,
  download: (id: string) => ["models", "download", id] as const,
  conversations: ["chat", "conversations"] as const,
  messages: (id: string) => ["chat", "messages", id] as const,
  memory: (q: string) => ["memory", q] as const,
  knowledge: ["knowledge"] as const,
  knowledgeSearch: (q: string) => ["knowledge", "search", q] as const,
};

export function useModels(refetchInterval?: number | false) {
  return useQuery({
    queryKey: localAiKeys.models,
    queryFn: () => unwrap(api.GET("/api/models")),
    refetchInterval: refetchInterval ?? false,
  });
}

export function useRecommendedModel() {
  return useQuery({
    queryKey: localAiKeys.recommendedModel,
    queryFn: () => unwrap(api.GET("/api/models/recommended")),
  });
}

function invalidateModels(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: localAiKeys.models });
  void qc.invalidateQueries({ queryKey: keys.status });
  void qc.invalidateQueries({ queryKey: keys.audit });
}

export function useAcceptLicense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model_id: string) =>
      unwrap(api.POST("/api/models/{model_id}/accept-license", { params: { path: { model_id } } })),
    onSuccess: () => {
      invalidateModels(qc);
    },
  });
}

export function useStartDownload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model_id: string) =>
      unwrap(api.POST("/api/models/{model_id}/download", { params: { path: { model_id } } })),
    onSuccess: () => {
      invalidateModels(qc);
    },
  });
}

export function useCancelDownload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (job_id: string) =>
      unwrap(api.POST("/api/models/downloads/{job_id}/cancel", { params: { path: { job_id } } })),
    onSuccess: () => {
      invalidateModels(qc);
    },
  });
}

export function useSetActiveModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model_id: string) =>
      unwrap(api.POST("/api/models/active", { body: { model_id } })),
    onSuccess: () => {
      invalidateModels(qc);
    },
  });
}

export function useRemoveModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model_id: string) =>
      unwrap(api.DELETE("/api/models/{model_id}", { params: { path: { model_id } } })),
    onSuccess: () => {
      invalidateModels(qc);
    },
  });
}

export function useLoadActiveModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/models/load")),
    onSuccess: () => {
      invalidateModels(qc);
    },
  });
}

export function useProviders() {
  return useQuery({
    queryKey: [...localAiKeys.models, "providers"] as const,
    queryFn: () => unwrap(api.GET("/api/models/providers")),
    staleTime: 60_000,
  });
}

export function useImportModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ImportRequest) => unwrap(api.POST("/api/models/import", { body })),
    onSuccess: () => {
      invalidateModels(qc);
      void qc.invalidateQueries({ queryKey: keys.cleanup });
    },
  });
}

export function useUnloadModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/models/unload")),
    onSuccess: () => {
      invalidateModels(qc);
    },
  });
}

export function useRenameConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { conversation_id: string; title: string }) =>
      unwrap(
        api.PATCH("/api/chat/conversations/{conversation_id}", {
          params: { path: { conversation_id: input.conversation_id } },
          body: { title: input.title },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: localAiKeys.conversations }),
  });
}

export function useConversations() {
  return useQuery({
    queryKey: localAiKeys.conversations,
    queryFn: () => unwrap(api.GET("/api/chat/conversations")),
  });
}

export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: localAiKeys.messages(conversationId ?? ""),
    queryFn: () =>
      unwrap(
        api.GET("/api/chat/conversations/{conversation_id}/messages", {
          params: { path: { conversation_id: conversationId ?? "" } },
        }),
      ),
    enabled: conversationId !== null,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) =>
      unwrap(api.POST("/api/chat/conversations", { body: { title: title ?? null } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: localAiKeys.conversations }),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (conversation_id: string) =>
      unwrap(
        api.DELETE("/api/chat/conversations/{conversation_id}", {
          params: { path: { conversation_id } },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: localAiKeys.conversations }),
  });
}

/** Stream one chat turn. Yields typed SSE events; the caller updates UI state. */
export async function* streamChatTurn(
  conversationId: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent<ChatStreamEvents[keyof ChatStreamEvents]>> {
  const creds = await getServiceCredentials();
  yield* streamSse<ChatStreamEvents[keyof ChatStreamEvents]>(
    { baseUrl: creds.base_url, token: creds.token },
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
    { content },
    signal,
  );
}

export function useMemories(query = "") {
  return useQuery({
    queryKey: localAiKeys.memory(query),
    queryFn: () => unwrap(api.GET("/api/memory", { params: { query: query ? { q: query } : {} } })),
  });
}

export function useAddMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { content: string; category: MemoryCategory }) =>
      unwrap(api.POST("/api/memory", { body: input })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["memory"] }),
  });
}

export function useUpdateMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { memory_id: number; body: MemoryUpdate }) =>
      unwrap(
        api.PATCH("/api/memory/{memory_id}", {
          params: { path: { memory_id: input.memory_id } },
          body: input.body,
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["memory"] }),
  });
}

export function useDeleteMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (memory_id: number) =>
      unwrap(api.DELETE("/api/memory/{memory_id}", { params: { path: { memory_id } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["memory"] }),
  });
}

export function useClearMemories() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/memory")),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["memory"] }),
  });
}

export function useKnowledge() {
  return useQuery({
    queryKey: localAiKeys.knowledge,
    queryFn: () => unwrap(api.GET("/api/knowledge")),
  });
}

export function useKnowledgeSearch(query: string) {
  return useQuery({
    queryKey: localAiKeys.knowledgeSearch(query),
    queryFn: () => unwrap(api.GET("/api/knowledge/search", { params: { query: { q: query } } })),
    enabled: query.trim().length > 0,
  });
}

export function useAddKnowledgeFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DocumentAddPathBody) => unwrap(api.POST("/api/knowledge/files", { body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });
}

export function useAddKnowledgeText() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; text: string }) =>
      unwrap(api.POST("/api/knowledge/text", { body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (document_id: string) =>
      unwrap(api.DELETE("/api/knowledge/{document_id}", { params: { path: { document_id } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });
}
