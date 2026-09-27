import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function Explodes(): never {
  throw new Error("the dashboard blew up");
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // React reports every caught error through console.error; the test asserts the
    // rendered output instead, and the noise would drown the rest of the run.
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders its children when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>the dashboard</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("the dashboard")).toBeInTheDocument();
  });

  it("names the failure instead of leaving an empty window", () => {
    const { container } = render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>,
    );
    // The regression this guards: an uncaught throw unmounts the tree and the window
    // goes blank, which reads as the app doing nothing rather than the app breaking.
    expect(container).not.toBeEmptyDOMElement();
    expect(screen.getByRole("alert")).toHaveTextContent("the dashboard blew up");
  });

  it("offers a way out rather than stranding the user", () => {
    render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
  });
});
