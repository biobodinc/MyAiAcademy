import { describe, expect, it } from "vitest";

import { classifyAsset, formatSize, toReleaseInfo } from "../lib/releases";

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
