import { afterEach, describe, expect, it, vi } from "vitest";

import { parseBlock, streamSse } from "../src";

afterEach(() => vi.unstubAllGlobals());

describe("parseBlock", () => {
  it("parses event and multi-line data", () => {
    expect(parseBlock('event: delta\ndata: {"text":"hi"}')).toEqual({
      event: "delta",
      data: { text: "hi" },
    });
    expect(parseBlock("")).toBeNull();
  });
});

describe("streamSse", () => {
  it("yields events across chunk boundaries and sends the token", async () => {
    const encoder = new TextEncoder();
    const parts = ['event: meta\ndata: {"a":1}\n\nevent: del', 'ta\ndata: {"text":"x"}\n\n'];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: URL, init: RequestInit) => {
        expect(new Headers(init.headers).get("authorization")).toBe("Bearer t");
        expect(url.pathname).toBe("/api/chat/conversations/c/messages");
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            for (const p of parts) controller.enqueue(encoder.encode(p));
            controller.close();
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        });
      }),
    );
    const events = [];
    for await (const e of streamSse(
      { baseUrl: "http://127.0.0.1:1", token: "t" },
      "/api/chat/conversations/c/messages",
      {},
    )) {
      events.push(e);
    }
    expect(events).toEqual([
      { event: "meta", data: { a: 1 } },
      { event: "delta", data: { text: "x" } },
    ]);
  });

  it("raises ApiError on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "No local model is set up." }), { status: 409 }),
      ),
    );
    const gen = streamSse({ baseUrl: "http://127.0.0.1:1", token: "t" }, "/x", {});
    await expect(gen.next()).rejects.toMatchObject({
      status: 409,
      detail: "No local model is set up.",
    });
  });
});
