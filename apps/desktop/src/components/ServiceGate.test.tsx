// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
/**
 * The regression this guards: a single failed poll took the whole app off screen.
 *
 * `useStatus` polls every ten seconds, and the gate used to return its "Cannot reach the local
 * AI service" card on `status.isError` alone. A query keeps its last good data when a refetch
 * fails, so one blip — a busy service, a second copy of myai-core holding the SQLite file —
 * replaced the running application, sidebar included, with a full-window error, and it stayed
 * until a later poll happened to succeed.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { keys } from "../lib/api";
import { ServiceGate } from "./ServiceGate";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubEnv("VITE_MYAI_DEV_TOKEN", "test-token");
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

const STATUS = {
  ai: "available",
  ai_detail: "model ready",
  internet: "available",
  training: "available",
  job: null,
  loaded_model_id: null,
};

function renderGate(seedStatus: boolean) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  if (seedStatus) client.setQueryData(keys.status, STATUS);
  return render(
    <QueryClientProvider client={client}>
      <ServiceGate>
        <p>the dashboard</p>
      </ServiceGate>
    </QueryClientProvider>,
  );
}

describe("ServiceGate", () => {
  it("keeps the app on screen when a status poll fails but the last status is known", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "busy" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      }),
    );
    renderGate(true);

    await waitFor(() => expect(screen.getByText("the dashboard")).toBeInTheDocument());
    expect(screen.queryByText("Cannot reach the local AI service")).not.toBeInTheDocument();
  });

  it("still explains a failure when there is no status to fall back on", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "connection refused" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      }),
    );
    renderGate(false);

    await waitFor(() =>
      expect(screen.getByText("Cannot reach the local AI service")).toBeInTheDocument(),
    );
    expect(screen.queryByText("the dashboard")).not.toBeInTheDocument();
  });

  it("passes the app through when the service answers", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(STATUS), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    renderGate(false);

    await waitFor(() => expect(screen.getByText("the dashboard")).toBeInTheDocument());
  });
});
