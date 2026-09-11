import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../test/utils";
import { ConsolePage } from "./ConsolePage";

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

describe("ConsolePage", () => {
  it("sends the bearer token and shows the mapped command", async () => {
    fetchMock.mockImplementation((url: URL, init: RequestInit) => {
      expect(new Headers(init.headers).get("authorization")).toBe("Bearer test-token");
      expect(url.host).toBe("127.0.0.1:41337");
      return Promise.resolve(
        jsonResponse({
          outcome: "unavailable",
          command: {
            name: "learn",
            raw: "teach yourself video",
            skill: "video",
            skill_text: "video",
            train: null,
            args: ["video"],
            natural_language: true,
          },
          title: "Learning Video is not available yet",
          message: "Nothing has been downloaded or changed.",
          data: {},
          suggestions: ["/skills"],
        }),
      );
    });
    renderWithProviders(<ConsolePage />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Command"), "teach yourself video");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(screen.getByText("Learning Video is not available yet")).toBeInTheDocument(),
    );
    expect(screen.getByText(/mapped from your sentence/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "/skills" })).toBeInTheDocument();
  });

  it("surfaces API errors instead of hiding them", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "Missing or invalid local API token." }, 401),
    );
    renderWithProviders(<ConsolePage />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Command"), "/status");
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Missing or invalid local API token."),
    );
  });
});
