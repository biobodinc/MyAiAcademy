// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
/**
 * Publishes built installers to the site's own storage and records what was published.
 *
 * The repository is private, so GitHub's release assets are not reachable by a visitor and
 * the download page cannot read them. Files go to Vercel Blob, which the website serves
 * from, and the manifest this writes is what the page renders. The manifest carries a
 * SHA-256 per file: nothing here is signed by a certificate authority, so a published hash
 * is the only integrity claim we can actually back up.
 *
 * Usage:
 *   node scripts/publish_downloads.mjs --dir <artifacts> --version 0.1.3
 *
 * Needs BLOB_READ_WRITE_TOKEN in the environment. Files already published under the same
 * version are overwritten, so re-running a release is not an error.
 */
import { createHash } from "node:crypto";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { basename, join, resolve } from "node:path";

import { put } from "@vercel/blob";

const MANIFEST = "apps/website/lib/release-manifest.json";

/** Files worth offering. Anything else in the artifact directory is build residue. */
const PUBLISHABLE = /\.(exe|msi|dmg|AppImage|deb|rpm|apk|zip|whl)$|\.tar\.gz$/i;

function parseArgs(argv) {
  const args = { dir: null, version: null };
  for (let i = 2; i < argv.length; i += 2) {
    const key = argv[i]?.replace(/^--/, "");
    if (key === "dir" || key === "version") args[key] = argv[i + 1] ?? null;
  }
  if (!args.dir || !args.version) {
    throw new Error("usage: publish_downloads.mjs --dir <artifacts> --version <x.y.z>");
  }
  return args;
}

/** Every file under `dir`, at any depth: the artifact download lands them in per-job folders. */
async function walk(dir) {
  const found = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...(await walk(path)));
    else if (PUBLISHABLE.test(entry.name)) found.push(path);
  }
  return found;
}

async function main() {
  const { dir, version } = parseArgs(process.argv);
  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    throw new Error("BLOB_READ_WRITE_TOKEN is not set, so there is nowhere to publish to.");
  }

  const paths = await walk(resolve(dir));
  if (paths.length === 0) throw new Error(`no publishable artifacts under ${dir}`);

  // A job can be re-run, and two matrix legs can produce the same filename; the last write
  // of a given name wins rather than the page listing it twice.
  const byName = new Map(paths.map((p) => [basename(p), p]));

  const files = [];
  let base = null;
  for (const [fileName, path] of [...byName].sort(([a], [b]) => a.localeCompare(b))) {
    const bytes = await readFile(path);
    const sha256 = createHash("sha256").update(bytes).digest("hex");
    const { size } = await stat(path);

    const { url } = await put(`releases/${version}/${fileName}`, bytes, {
      access: "public",
      addRandomSuffix: false,
      allowOverwrite: true,
      contentType: "application/octet-stream",
    });
    base ??= url.slice(0, url.indexOf(`/releases/${version}/`)) + "/releases";

    files.push({ fileName, sizeBytes: size, sha256 });
    console.log(`${fileName}  ${(size / 1024 ** 2).toFixed(1)} MB  ${sha256.slice(0, 16)}…`);
  }

  await writeFile(
    MANIFEST,
    JSON.stringify({ version, publishedAt: new Date().toISOString(), files }, null, 2) + "\n",
    "utf8",
  );

  console.log(`\n${files.length} file(s) published, manifest written to ${MANIFEST}`);
  console.log(`Set NEXT_PUBLIC_DOWNLOAD_BASE in the Vercel project to:\n  ${base}`);
}

await main();
