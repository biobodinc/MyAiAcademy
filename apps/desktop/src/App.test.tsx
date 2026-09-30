// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
/**
 * The regression these guard: the window went blank white and stayed that way.
 *
 * `onboarded` used to fall back to false whenever preferences were missing for any reason, so
 * a single failed GET /api/preferences redirected to /onboarding, where the wizard had no
 * preferences either and rendered a bare spinner. The user got a white window reading
 * "Loading" — no sidebar, no message, permanently, because nothing refetches preferences on
 * its own. Nothing threw, so the error boundary never caught it: the app was not crashing, it
 * was showing a loading state for data that was never going to arrive.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

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

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const STATUS = {
  ai: "not_configured",
  ai_detail: "no model yet",
  internet: "available",
  training: "unavailable",
  job: null,
  loaded_model_id: null,
};

/** Answers /api/status, and lets each test decide what /api/preferences does. */
function route(preferences: () => Response) {
  fetchMock.mockImplementation((url: URL | string) => {
    const href = String(url);
    if (href.includes("/api/preferences")) return Promise.resolve(preferences());
    if (href.includes("/api/status")) return Promise.resolve(json(STATUS));
    return Promise.resolve(json({}));
  });
}

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App, when preferences cannot be read", () => {
  it("says so instead of leaving a window that only reads Loading", async () => {
    route(() => json({ detail: "database is locked" }, 503));
    const { container } = renderApp();

    await waitFor(() =>
      expect(screen.getByText("Could not read your preferences")).toBeInTheDocument(),
    );
    expect(container).not.toBeEmptyDOMElement();
    // The old behaviour: the whole window was one spinner and nothing else.
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not mistake a failed read for a user who has not onboarded", async () => {
    route(() => json({ detail: "database is locked" }, 503));
    renderApp();

    await waitFor(() =>
      expect(screen.getByText("Could not read your preferences")).toBeInTheDocument(),
    );
    // Being thrown back into first-run setup is the other half of the bug: the redirect fired
    // because a missing answer was read as "onboarding_completed: false".
    expect(screen.queryByText(/Welcome/)).not.toBeInTheDocument();
  });

  it("offers a way out rather than stranding the user", async () => {
    route(() => json({ detail: "database is locked" }, 503));
    renderApp();

    await waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled());
  });

  it("renders the app normally once preferences load", async () => {
    route(() =>
      json({
        theme: "system",
        experience_mode: "beginner",
        compute_preset: "balanced",
        privacy_mode: "private",
        contributor_mode: false,
        onboarding_step: "done",
        onboarding_completed: true,
        chat_max_tokens: 512,
        chat_temperature: 0.7,
        cpu_utilization_percent: null,
        gpu_utilization_percent: null,
        ram_limit_gib: null,
        temperature_limit_c: null,
        time_limit_minutes: null,
      }),
    );
    renderApp();

    await waitFor(() =>
      expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument(),
    );
    expect(screen.queryByText("Could not read your preferences")).not.toBeInTheDocument();
  });
});
