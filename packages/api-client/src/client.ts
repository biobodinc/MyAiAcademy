/**
 * Typed HTTP client for the MyAI Academy local service.
 *
 * The client is transport-agnostic: callers supply a credentials *provider*, so the
 * desktop shell can read the token from disk via Tauri and the mobile app (Phase 6) can
 * supply device credentials instead. No credential is ever baked into this package.
 *
 * Credentials are resolved lazily on the first request and cached; a 401 clears the
 * cache so a rotated token is picked up on the next call.
 */
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./generated/schema";

export interface LocalServiceCredentials {
  /** e.g. `http://127.0.0.1:41337` (without `/api`). */
  baseUrl: string;
  token: string;
}

export type CredentialsProvider = () => Promise<LocalServiceCredentials>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly path: string,
  ) {
    super(`${status} ${path}: ${detail}`);
    this.name = "ApiError";
  }
}

export class ServiceUnreachableError extends Error {
  constructor(cause: unknown) {
    super("The MyAI local service is not reachable.", { cause });
    this.name = "ServiceUnreachableError";
  }
}

const LOOPBACK = /^http:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$/;

export function assertLoopback(baseUrl: string): void {
  if (!LOOPBACK.test(baseUrl)) {
    throw new Error(`Refusing non-loopback service address: ${baseUrl}`);
  }
}

function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : String(d)))
        .join("; ");
    }
  }
  return fallback;
}

const BODYLESS = new Set(["GET", "HEAD"]);

/** A placeholder origin; every request is re-targeted at the resolved credentials. */
const PLACEHOLDER_BASE = "http://127.0.0.1:0";

export function createLocalServiceClient(getCredentials: CredentialsProvider) {
  let cached: LocalServiceCredentials | null = null;

  async function credentials(): Promise<LocalServiceCredentials> {
    cached ??= await getCredentials();
    assertLoopback(cached.baseUrl);
    return cached;
  }

  /**
   * Re-targets the request at the real service origin and attaches the bearer token.
   * The body is buffered rather than streamed: request bodies here are small JSON, and
   * re-wrapping a streamed body requires `duplex: "half"`, which not every runtime
   * supports.
   */
  const targetedFetch = async (request: Request): Promise<Response> => {
    let creds: LocalServiceCredentials;
    try {
      creds = await credentials();
    } catch (error) {
      throw new ServiceUnreachableError(error);
    }
    const url = new URL(request.url);
    const base = new URL(creds.baseUrl);
    url.protocol = base.protocol;
    url.host = base.host;

    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${creds.token}`);
    const init: RequestInit = { method: request.method, headers, signal: request.signal };
    if (!BODYLESS.has(request.method)) init.body = await request.arrayBuffer();

    try {
      return await globalThis.fetch(url, init);
    } catch (error) {
      throw new ServiceUnreachableError(error);
    }
  };

  const errors: Middleware = {
    async onResponse({ response, request }) {
      if (response.status === 401) cached = null;
      if (!response.ok) {
        const text = await response.text();
        let parsed: unknown = undefined;
        try {
          parsed = JSON.parse(text);
        } catch {
          /* non-JSON error body */
        }
        throw new ApiError(
          response.status,
          extractDetail(parsed, text || response.statusText),
          new URL(request.url).pathname,
        );
      }
      return response;
    },
  };

  const client = createClient<paths>({ baseUrl: PLACEHOLDER_BASE, fetch: targetedFetch });
  client.use(errors);
  return client;
}

export type LocalServiceClient = ReturnType<typeof createLocalServiceClient>;
