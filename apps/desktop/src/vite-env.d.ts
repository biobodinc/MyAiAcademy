/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Dev-only: token pasted from <app-data-dir>/local-api.token when running in a browser. */
  readonly VITE_MYAI_DEV_TOKEN?: string;
  /** Dev-only: override the service base URL (default http://127.0.0.1:41337). */
  readonly VITE_MYAI_DEV_BASE_URL?: string;
}
