/**
 * The phone menu is the only way to reach the other pages below the `md` breakpoint, so
 * these tests cover the behaviour that would strand a visitor if it broke.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NAV_LINKS, SIGN_IN } from "../lib/nav";

let pathname = "/";

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const { MobileNav } = await import("../components/MobileNav");

beforeEach(() => {
  pathname = "/";
});

afterEach(() => {
  vi.clearAllMocks();
});

function menu(): HTMLDetailsElement {
  const toggle = screen.getByRole("group", { hidden: true });
  return toggle as HTMLDetailsElement;
}

describe("MobileNav", () => {
  it("offers every navigation destination and sign-in", () => {
    render(<MobileNav />);
    for (const link of NAV_LINKS) {
      expect(screen.getByRole("link", { name: link.label })).toHaveAttribute("href", link.href);
    }
    expect(screen.getByRole("link", { name: SIGN_IN.label })).toHaveAttribute("href", SIGN_IN.href);
  });

  it("starts closed and opens from the labelled toggle", async () => {
    render(<MobileNav />);
    expect(menu().open).toBe(false);
    await userEvent.click(screen.getByLabelText("Menu"));
    expect(menu().open).toBe(true);
  });

  it("closes on Escape and returns focus to the toggle", async () => {
    render(<MobileNav />);
    const toggle = screen.getByLabelText("Menu");
    await userEvent.click(toggle);
    expect(menu().open).toBe(true);

    await userEvent.keyboard("{Escape}");
    expect(menu().open).toBe(false);
    expect(toggle).toHaveFocus();
  });

  it("closes the moment a link is tapped, before the route changes", async () => {
    render(<MobileNav />);
    await userEvent.click(screen.getByLabelText("Menu"));
    await userEvent.click(screen.getByRole("link", { name: "Security" }));
    expect(menu().open).toBe(false);
  });

  it("closes itself after a client-side navigation", async () => {
    const { rerender } = render(<MobileNav />);
    await userEvent.click(screen.getByLabelText("Menu"));
    expect(menu().open).toBe(true);

    pathname = "/privacy";
    rerender(<MobileNav />);
    expect(menu().open).toBe(false);
  });

  it("marks the current page for screen readers", () => {
    pathname = "/privacy";
    render(<MobileNav />);
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Download" })).not.toHaveAttribute("aria-current");
  });
});
