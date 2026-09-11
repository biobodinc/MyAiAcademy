import type { components } from "./generated/schema";

type Schemas = components["schemas"];

export type ModelsOverview = Schemas["ModelsOverview"];
export type ModelEntry = Schemas["ModelEntry"];
export type CatalogModel = Schemas["CatalogModel"];
export type ModelLicense = Schemas["ModelLicense"];
export type DownloadStatus = Schemas["DownloadStatus"];
export type HardwareFit = Schemas["HardwareFit"];
export type ConversationRead = Schemas["ConversationRead"];
export type MessageRead = Schemas["MessageRead"];
export type SendMessage = Schemas["SendMessage"];
export type MemoryRead = Schemas["MemoryRead"];
export type MemoryCreate = Schemas["MemoryCreate"];
export type MemoryUpdate = Schemas["MemoryUpdate"];
export type MemoryCategory = Schemas["MemoryCategory"];
export type KnowledgeOverview = Schemas["KnowledgeOverview"];
export type DocumentRead = Schemas["DocumentRead"];
export type RetrievedChunk = Schemas["RetrievedChunk"];

/** Payloads of the chat SSE events, by event name. */
export interface ChatStreamEvents {
  meta: {
    user_message_id: number;
    model_id: string;
    retrieved: RetrievedChunk[];
    conversation_title: string;
  };
  delta: { text: string };
  done: {
    assistant_message_id: number;
    finish_reason: string;
    duration_ms: number;
    prompt_tokens: number | null;
    completion_tokens: number | null;
  };
  error: { message: string; assistant_message_id?: number };
  command: Schemas["CommandResult"];
}
export type ConversationUpdate = Schemas["ConversationUpdate"];
