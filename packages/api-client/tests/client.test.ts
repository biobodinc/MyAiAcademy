import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createLocalServiceClient, ServiceUnreachableError } from "../src";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("createLocalServiceClient", () => {
  it("targets the resolved origin, attaches the token, and buffers POST bodies", async () => {
    const fetchMock = vi.fn(async (url: URL, init: RequestInit) => {
      expect(url.origin).toBe("http://127.0.0.1:41337");
      expect(new Headers(init.headers).get("authorization")).toBe("Bearer secret");
      if (url.pathname === "/api/commands") {
        expect(init.method).toBe("POST");
        expect(new TextDecoder().decode(init.body as ArrayBuffer)).toBe('{"text":"/help"}');
        return json({
          outcome: "ok",
          command: null,
          title: "Help",
          message: "…",
          data: {},
          suggestions: [],
        });
      }
      expect(init.body).toBeUndefined();
      return json({});
    });
    vi.stubGlobal("fetch", fetchMock);
    const provider = vi.fn(async () => ({ baseUrl: "http://127.0.0.1:41337", token: "secret" }));
    const client = createLocalServiceClient(provider);

    const { data } = await client.POST("/api/commands", { body: { text: "/help" } });
    expect(data?.title).toBe("Help");
    await client.GET("/api/status");
    expect(provider).toHaveBeenCalledTimes(1); // cached after first resolution
  });

  it("raises ApiError with the service's detail message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ detail: "Origin not allowed." }, 403)),
    );
    const client = createLocalServiceClient(async () => ({
      baseUrl: "http://127.0.0.1:1",
      token: "t",
    }));
    await expect(client.GET("/api/status")).rejects.toMatchObject<Partial<ApiError>>({
      status: 403,
      detail: "Origin not allowed.",
    });
  });

  it("re-reads credentials after a 401", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => (calls++ === 0 ? json({ detail: "bad" }, 401) : json({}))),
    );
    const provider = vi.fn(async () => ({ baseUrl: "http://127.0.0.1:1", token: "t" }));
    const client = createLocalServiceClient(provider);
    await expect(client.GET("/api/status")).rejects.toBeInstanceOf(ApiError);
    await client.GET("/api/status");
    expect(provider).toHaveBeenCalledTimes(2);
  });

  it("refuses non-loopback addresses and wraps network failures", async () => {
    const bad = createLocalServiceClient(async () => ({
      baseUrl: "http://10.0.0.5:41337",
      token: "t",
    }));
    await expect(bad.GET("/api/status")).rejects.toBeInstanceOf(ServiceUnreachableError);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("ECONNREFUSED");
      }),
    );
    const down = createLocalServiceClient(async () => ({
      baseUrl: "http://127.0.0.1:1",
      token: "t",
    }));
    await expect(down.GET("/api/status")).rejects.toBeInstanceOf(ServiceUnreachableError);
  });
});
