import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../test/utils";
import { GuidePanel } from "./GuidePanel";

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

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("GuidePanel", () => {
  it("shows the answer and labels its source", async () => {
    fetchMock.mockImplementation((url: URL) => {
      if (url.pathname.endsWith("/guide/topics")) {
        return Promise.resolve(
          jsonResponse([{ id: "training", title: "Training", question: "What is training?" }]),
        );
      }
      return Promise.resolve(
        jsonResponse({
          matched: true,
          topic_id: "training",
          title: "Training",
          answer: "Training is how your AI improves a specific skill.",
          confidence: 0.8,
          source: "Built-in guide (not your AI model)",
          related: [],
        }),
      );
    });
    renderWithProviders(<GuidePanel />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Ask the guide"), "what is training");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(screen.getByText(/improves a specific skill/)).toBeInTheDocument());
    expect(screen.getByText("Built-in guide (not your AI model)")).toBeInTheDocument();
  });
});
