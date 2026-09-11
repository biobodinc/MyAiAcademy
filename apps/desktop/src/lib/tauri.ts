/**
 * Bridge to the Tauri shell. Every call degrades gracefully when the UI runs in a plain
 * browser during development, so the React app can be developed and tested without
 * compiling Rust.
 */
import { invoke, isTauri } from "@tauri-apps/api/core";

export const inTauri: boolean = isTauri();

export interface ServiceCredentials {
  base_url: string;
  token: string;
}

export type ServiceState =
  | { kind: "starting" }
  | { kind: "running"; base_url: string; pid: number | null }
  | { kind: "failed"; error: string };

export async function getServiceCredentials(): Promise<ServiceCredentials> {
  if (inTauri) return invoke<ServiceCredentials>("local_api_credentials");
  const token = import.meta.env.VITE_MYAI_DEV_TOKEN;
  if (!token) {
    throw new Error(
      "Running outside Tauri without VITE_MYAI_DEV_TOKEN. Copy the token from " +
        "<app-data-dir>/local-api.token into apps/desktop/.env.local.",
    );
  }
  return { base_url: import.meta.env.VITE_MYAI_DEV_BASE_URL ?? "http://127.0.0.1:41337", token };
}

export async function getServiceState(): Promise<ServiceState> {
  if (inTauri) return invoke<ServiceState>("service_state");
  return { kind: "running", base_url: "http://127.0.0.1:41337", pid: null };
}

export async function restartService(): Promise<void> {
  if (inTauri) await invoke("restart_service");
}

export async function pickDirectory(title: string): Promise<string | null> {
  if (!inTauri) {
    // Browser dev fallback: a plain prompt keeps the flow testable.
    return window.prompt(`${title}\n(enter an absolute path)`) ?? null;
  }
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({ directory: true, multiple: false, title });
  return typeof selected === "string" ? selected : null;
}

export async function openExternal(url: string): Promise<void> {
  if (!/^https:\/\//.test(url)) throw new Error("Only https links may be opened.");
  if (inTauri) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
