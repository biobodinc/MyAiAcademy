import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LevelBadge, ProgressBar, StatusPill } from "./ui";

describe("ProgressBar", () => {
  it("clamps and exposes aria values", () => {
    render(<ProgressBar value={62} label="Video" />);
    const bar = screen.getByRole("progressbar", { name: "Video" });
    expect(bar).toHaveAttribute("aria-valuenow", "62");
    render(<ProgressBar value={500} max={100} label="Over" />);
    expect(screen.getByRole("progressbar", { name: "Over" })).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
  });
});

describe("LevelBadge", () => {
  it("labels the level for assistive tech", () => {
    render(<LevelBadge level={24} />);
    expect(screen.getByLabelText("Level 24")).toHaveTextContent("24");
  });
});

describe("StatusPill", () => {
  it("renders children", () => {
    render(<StatusPill tone="success">MyAI running locally</StatusPill>);
    expect(screen.getByText("MyAI running locally")).toBeInTheDocument();
  });
});
