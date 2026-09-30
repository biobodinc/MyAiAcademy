// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import { afterEach, describe, expect, it } from "vitest";

import { classifyFile, downloadBase, formatSize, toReleaseInfo } from "../lib/releases";

const file = (fileName: string) => ({
  fileName,
  sizeBytes: 1024 ** 2 * 80,
  sha256: "a".repeat(64),
});

describe("classifyFile", () => {
  it("recognises installer types", () => {
    expect(classifyFile("MyAI-Academy_0.1.3_x64-setup.exe")?.platform).toBe("windows");
    expect(classifyFile("MyAI-Academy_0.1.3_x64_en-US.msi")?.platform).toBe("windows");
    expect(classifyFile("MyAI Academy_0.1.3_aarch64.dmg")?.platform).toBe("macos");
    expect(classifyFile("myai-academy_0.1.3_amd64.AppImage")?.platform).toBe("linux");
    expect(classifyFile("myai-cli-0.1.3-windows-x64.zip")?.platform).toBe("cli");
    expect(classifyFile("myai_cli-0.1.3-py3-none-any.whl")?.platform).toBe("cli");
    expect(classifyFile("checksums.txt")).toBeNull();
  });

  it("tells the two Linux architectures apart, since a Chromebook needs the right one", () => {
    expect(classifyFile("myai-academy_0.1.3_arm64.deb")?.label).toContain("ARM64");
    expect(classifyFile("myai-academy_0.1.3_amd64.deb")?.label).toContain("x86-64");
    expect(classifyFile("myai-academy_0.1.3_arm64.AppImage")?.label).toContain("ARM64");
  });
});

describe("toReleaseInfo", () => {
  const base = "https://example.invalid/releases";

  it("builds a URL per file under the configured host", () => {
    const info = toReleaseInfo(
      { version: "0.1.3", publishedAt: "2026-09-30T00:00:00Z", files: [file("a.dmg")] },
      base,
    );
    expect(info?.version).toBe("0.1.3");
    expect(info?.files[0]?.url).toBe(`${base}/0.1.3/a.dmg`);
    expect(info?.files[0]?.sha256).toHaveLength(64);
  });

  it("drops files it cannot place rather than inventing a card for them", () => {
    const info = toReleaseInfo(
      {
        version: "0.1.3",
        publishedAt: "2026-09-30T00:00:00Z",
        files: [file("a.dmg"), file("SHA256SUMS")],
      },
      base,
    );
    expect(info?.files).toHaveLength(1);
  });

  it("honours an explicit platform for a file whose name cannot say", () => {
    const info = toReleaseInfo(
      {
        version: "0.1.3",
        publishedAt: "2026-09-30T00:00:00Z",
        files: [
          { ...file("myai-chromeos.tar.xz"), platform: "chromeos", label: "ChromeOS bundle" },
        ],
      },
      base,
    );
    expect(info?.files[0]?.platform).toBe("chromeos");
  });

  it("offers nothing when no version has been recorded", () => {
    expect(toReleaseInfo({ version: "", publishedAt: "", files: [] }, base)).toBeNull();
  });

  it("escapes a filename rather than letting it break the URL", () => {
    const info = toReleaseInfo(
      { version: "0.1.3", publishedAt: "", files: [file("MyAI Academy_0.1.3_x64-setup.exe")] },
      base,
    );
    expect(info?.files[0]?.url).toContain("MyAI%20Academy");
  });
});

describe("downloadBase", () => {
  const original = process.env.NEXT_PUBLIC_DOWNLOAD_BASE;
  afterEach(() => {
    if (original === undefined) delete process.env.NEXT_PUBLIC_DOWNLOAD_BASE;
    else process.env.NEXT_PUBLIC_DOWNLOAD_BASE = original;
  });

  it("is null when nothing is configured, so the page says there is no download", () => {
    delete process.env.NEXT_PUBLIC_DOWNLOAD_BASE;
    expect(downloadBase()).toBeNull();
  });

  it("strips a trailing slash so URLs never double up", () => {
    process.env.NEXT_PUBLIC_DOWNLOAD_BASE = "https://example.invalid/releases/";
    expect(downloadBase()).toBe("https://example.invalid/releases");
  });
});

describe("formatSize", () => {
  it("formats", () => {
    expect(formatSize(80 * 1024 ** 2)).toBe("80 MB");
    expect(formatSize(2.5 * 1024 ** 3)).toBe("2.5 GB");
  });
});
