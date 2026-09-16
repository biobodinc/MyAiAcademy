/**
 * Talking to the account server from the browser.
 *
 * The account server is a separate service (`packages/myai-server`) and is not deployed
 * anywhere yet. `ACCOUNT_API` is empty unless someone sets `NEXT_PUBLIC_ACCOUNT_API` at
 * build time, and every page checks `accountsAvailable()` before offering a form. That is
 * deliberate: a sign-in box that posts into the void is worse than a page saying plainly
 * that there is nothing to sign in to, and it keeps this site honest in both configurations
 * without maintaining two versions of the truth.
 *
 * **Where the session token lives.** `localStorage`, sent as a Bearer header. The
 * alternative — an httpOnly cookie — would need credentialed CORS between this origin and
 * the API, which brings CSRF defences the server does not have yet; the server deliberately
 * sets `allow_credentials=False`. The cost is that a script injected into this page could
 * read the token, so nothing on these pages renders untrusted HTML.
 */

const TOKEN_KEY = "myai.session";

export const ACCOUNT_API = (process.env.NEXT_PUBLIC_ACCOUNT_API ?? "").trim().replace(/\/$/, "");

export function accountsAvailable(): boolean {
  return ACCOUNT_API.length > 0;
}

export interface Account {
  account_id: string;
  email: string | null;
  email_verified: boolean;
  oauth_provider: string | null;
  created_at: string;
}

export interface Device {
  device_id: string;
  device_name: string;
  last_seen: string | null;
  created_at: string;
  revoked: boolean;
}

export interface AuditEvent {
  event_type: string;
  device_id: string | null;
  ip_address: string | null;
  created_at: string;
  details: string | null;
}

export interface AuthResult {
  token: string;
  account: Account;
}

export interface SignUpResult extends AuthResult {
  verification_email_sent: boolean;
  detail: string;
}

/** An error carrying what the server actually said, so a form can show it verbatim. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function storedToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    // Private windows and blocked site data both throw rather than returning null.
    return null;
  }
}

export function storeToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Not fatal: the session still works until the tab closes.
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to clear */
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers, ...rest } = init;
  let response: Response;
  try {
    response = await fetch(`${ACCOUNT_API}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
  } catch {
    // A network failure is not the same as a refusal, and saying "check your details"
    // when the server is unreachable sends people hunting for a problem they do not have.
    throw new ApiError(0, "Could not reach the account server. Check your connection.");
  }

  if (response.status === 204) return undefined as T;

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : "Something went wrong. Try again.",
    );
  }
  return body as T;
}

export const api = {
  signUp: (email: string, password: string) =>
    request<SignUpResult>("/api/accounts/sign-up", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  signIn: (email: string, password: string) =>
    request<AuthResult>("/api/accounts/sign-in", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  signOut: (token: string) =>
    request<{ detail: string }>("/api/accounts/sign-out", { method: "POST", token }),

  me: (token: string) => request<Account>("/api/accounts/me", { token }),

  verifyEmail: (verificationToken: string) =>
    request<Account>("/api/accounts/verify-email", {
      method: "POST",
      body: JSON.stringify({ token: verificationToken }),
    }),

  resendVerification: (token: string) =>
    request<{ detail: string }>("/api/accounts/resend-verification", { method: "POST", token }),

  changePassword: (token: string, current_password: string, new_password: string) =>
    request<AuthResult>("/api/accounts/change-password", {
      method: "POST",
      token,
      body: JSON.stringify({ current_password, new_password }),
    }),

  activity: (token: string) => request<AuditEvent[]>("/api/accounts/activity", { token }),

  devices: (token: string) => request<Device[]>("/api/devices", { token }),

  createPairingCode: (token: string) =>
    request<{ code: string; expires_at: string; expires_in_seconds: number; note: string }>(
      "/api/devices/pairing-codes",
      { method: "POST", token },
    ),

  renameDevice: (token: string, deviceId: string, device_name: string) =>
    request<Device>(`/api/devices/${encodeURIComponent(deviceId)}`, {
      method: "PATCH",
      token,
      body: JSON.stringify({ device_name }),
    }),

  revokeDevice: (token: string, deviceId: string) =>
    request<Device>(`/api/devices/${encodeURIComponent(deviceId)}/revoke`, {
      method: "POST",
      token,
    }),
};
