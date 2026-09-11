/**
 * Server-sent events over fetch (EventSource cannot send an Authorization header).
 * Parses the `event:` / `data:` framing the local service emits for chat.
 */
import type { LocalServiceCredentials } from "./client";
import { assertLoopback, ApiError, ServiceUnreachableError } from "./client";

export interface SseEvent<T = unknown> {
  event: string;
  data: T;
}

export async function* streamSse<T = unknown>(
  creds: LocalServiceCredentials,
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent<T>> {
  assertLoopback(creds.baseUrl);
  let response: Response;
  const init: RequestInit = {
    method: "POST",
    headers: {
      Authorization: `Bearer ${creds.token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
  };
  if (signal) init.signal = signal;
  try {
    response = await globalThis.fetch(new URL(path, creds.baseUrl), init);
  } catch (error) {
    throw new ServiceUnreachableError(error);
  }
  if (!response.ok) {
    const text = await response.text();
    let detail = text || response.statusText;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail, path);
  }
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseBlock<T>(block);
        if (parsed) yield parsed;
        boundary = buffer.indexOf("\n\n");
      }
    }
    const tail = parseBlock<T>(buffer);
    if (tail) yield tail;
  } finally {
    reader.releaseLock();
  }
}

export function parseBlock<T>(block: string): SseEvent<T> | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) as T };
}
