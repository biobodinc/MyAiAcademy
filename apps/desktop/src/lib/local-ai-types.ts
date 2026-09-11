export type { ChatStreamEvents, MemoryCategory, MemoryUpdate, SseEvent } from "@myai/api-client";

export interface DocumentAddPathBody {
  path: string;
  title?: string | null;
}
