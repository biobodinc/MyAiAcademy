/**
 * React Query hooks over the typed local-service client.
 * Query keys are centralised so mutations can invalidate precisely.
 */
import {
  ApiError,
  createLocalServiceClient,
  type CommandResult,
  type PreferencesUpdate,
  type ProfileCreate,
  type ProfileUpdate,
  type StorageCategory,
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
