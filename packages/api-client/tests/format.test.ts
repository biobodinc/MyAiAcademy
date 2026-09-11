import { describe, expect, it } from "vitest";

import { assertLoopback, formatBytes, formatPercent, titleCase } from "../src";

describe("formatBytes", () => {
  it("formats units", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(18 * 1024 ** 3)).toBe("18.0 GB");
    expect(formatBytes(1.01 * 1024 ** 4, 2)).toBe("1.01 TB");
    expect(formatBytes(null)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("clamps", () => {
    expect(formatPercent(0.62)).toBe("62%");
    expect(formatPercent(2)).toBe("100%");
    expect(formatPercent(-1)).toBe("0%");
  });
});

describe("titleCase", () => {
  it("handles snake case", () => {
    expect(titleCase("not_configured")).toBe("Not Configured");
  });
});

describe("assertLoopback", () => {
  it("accepts loopback only", () => {
    expect(() => assertLoopback("http://127.0.0.1:41337")).not.toThrow();
    expect(() => assertLoopback("http://localhost:1")).not.toThrow();
    expect(() => assertLoopback("http://192.168.1.5:41337")).toThrow();
    expect(() => assertLoopback("https://127.0.0.1")).toThrow();
  });
});
