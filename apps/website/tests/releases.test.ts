// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  classifyAsset,
  fetchLatestRelease,
  formatSize,
  isGitHubRelease,
  toReleaseInfo,
} from "../lib/releases";

const asset = (name: string) => ({
  name,
  browser_download_url: `https://x/${name}`,
  size: 1024 ** 2 * 80,
});

describe("classifyAsset", () => {
  it("recognises installer types", () => {
    expect(classifyAsset(asset("MyAI-Academy_0.1.0_x64-setup.exe"))?.platform).toBe("windows");
    expect(classifyAsset(asset("MyAI-Academy_0.1.0_x64_en-US.msi"))?.platform).toBe("windows");
    expect(classifyAsset(asset("MyAI Academy_0.1.0_aarch64.dmg"))?.platform).toBe("macos");
    expect(classifyAsset(asset("myai-academy_0.1.0_amd64.AppImage"))?.platform).toBe("linux");
    expect(classifyAsset(asset("myai-cli-0.1.0-windows-x64.zip"))?.platform).toBe("cli");
    expect(classifyAsset(asset("myai_cli-0.1.0-py3-none-any.whl"))?.platform).toBe("cli");
    expect(classifyAsset(asset("checksums.txt"))).toBeNull();
  });
});

describe("toReleaseInfo", () => {
  it("strips the v prefix and drops unknown assets", () => {
    const info = toReleaseInfo({
      tag_name: "v0.1.0",
      published_at: "2026-09-11T00:00:00Z",
      html_url: "https://github.com/x/y/releases/tag/v0.1.0",
      draft: false,
      prerelease: false,
      assets: [asset("a.dmg"), asset("SHA256SUMS")],
    });
    expect(info.version).toBe("0.1.0");
    expect(info.assets).toHaveLength(1);
  });
});

describe("formatSize", () => {
  it("formats", () => {
    expect(formatSize(80 * 1024 ** 2)).toBe("80 MB");
    expect(formatSize(2.5 * 1024 ** 3)).toBe("2.5 GB");
  });
});

describe("isGitHubRelease", () => {
  it("rejects anything that is not a release", () => {
    // What GitHub actually answers with when there is no published release yet.
    expect(isGitHubRelease({ message: "Not Found" })).toBe(false);
    expect(isGitHubRelease(null)).toBe(false);
    expect(isGitHubRelease("v0.1.0")).toBe(false);
  });

  it("accepts a release body", () => {
    expect(
      isGitHubRelease({
        tag_name: "v0.1.0",
        published_at: "2026-09-11T00:00:00Z",
        html_url: "https://example.invalid",
        assets: [],
      }),
    ).toBe(true);
  });
});

describe("fetchLatestRelease", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const respond = (status: number, body: unknown) => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      json: () => Promise.resolve(body),
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  };

  it("reads the newest published release", async () => {
    respond(200, {
      tag_name: "v0.2.0",
      published_at: "2026-09-30T00:00:00Z",
      html_url: "https://github.com/x/y/releases/tag/v0.2.0",
      draft: false,
      prerelease: false,
      assets: [asset("MyAI Academy_0.2.0_x64-setup.exe")],
    });
    const info = await fetchLatestRelease();
    expect(info?.version).toBe("0.2.0");
    expect(info?.assets[0]?.platform).toBe("windows");
  });

  it("offers nothing when no release is published", async () => {
    respond(404, { message: "Not Found" });
    await expect(fetchLatestRelease()).resolves.toBeNull();
  });

  it("refuses to advertise a draft or a prerelease", async () => {
    respond(200, {
      tag_name: "v0.1.0",
      published_at: "2026-09-11T00:00:00Z",
      html_url: "https://example.invalid",
      draft: true,
      prerelease: false,
      assets: [],
    });
    await expect(fetchLatestRelease()).resolves.toBeNull();
  });

  it("degrades to the empty state when the network fails", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchLatestRelease()).resolves.toBeNull();
  });
});
