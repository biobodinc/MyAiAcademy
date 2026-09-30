// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
export type { ChatStreamEvents, MemoryCategory, MemoryUpdate, SseEvent } from "@myai/api-client";

export interface DocumentAddPathBody {
  path: string;
  title?: string | null;
}
