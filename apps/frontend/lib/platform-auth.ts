import { platformApi } from "@/lib/api-client";

// Platform admin credentials are held in memory only for the lifetime of the
// tab — never in localStorage/sessionStorage/IndexedDB. A page reload wipes
// this module's state, which is intentional: apps/frontend/app/platform/layout.tsx
// re-bootstraps the session from the HttpOnly `platform_refresh_token` cookie
// on mount instead. This keeps a stolen XSS payload or a shared-machine
// browser-storage dump from yielding a durable admin credential.
let accessToken: string | null = null;
let mfaSessionToken: string | null = null;

export const platformAuthStorage = {
  getToken(): string | null {
    return accessToken;
  },

  setToken(token: string): void {
    accessToken = token;
  },

  clearToken(): void {
    accessToken = null;
  },

  getMfaSession(): string | null {
    return mfaSessionToken;
  },

  setMfaSession(token: string): void {
    mfaSessionToken = token;
  },

  clearMfaSession(): void {
    mfaSessionToken = null;
  },

  clearAll(): void {
    accessToken = null;
    mfaSessionToken = null;
    impersonationState.clear();
  },
};

// Single-flight guard so concurrent callers (interval refresh timer + a page
// mount + React Strict Mode's double effect invocation in dev) collapse into
// one network call and share its result instead of racing separate refreshes
// against the rotating refresh-token cookie.
let refreshInFlight: Promise<boolean> | null = null;

/**
 * Bootstraps or renews the platform admin session from the HttpOnly refresh
 * cookie. Returns true and updates in-memory state on success; clears state
 * and returns false on failure (caller should redirect to /platform/login).
 */
export async function refreshPlatformSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const result = await platformApi.refresh();
      platformAuthStorage.setToken(result.access_token);
      return true;
    } catch {
      platformAuthStorage.clearAll();
      return false;
    }
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

// Impersonation is a separate, higher-privilege bearer token for the
// impersonated tenant user. It never touches browser storage either — held
// in memory only, cleared on tab reload same as the admin token, and backed
// by a Redis session on the API side so ending it (or starting a new one)
// actually revokes the previous JWT rather than just forgetting it client-side.
let impersonationEmail: string | null = null;
const impersonationListeners = new Set<() => void>();

function notifyImpersonationListeners(): void {
  impersonationListeners.forEach((listener) => listener());
}

export const impersonationState = {
  getEmail(): string | null {
    return impersonationEmail;
  },
  setActive(email: string): void {
    impersonationEmail = email;
    notifyImpersonationListeners();
  },
  clear(): void {
    impersonationEmail = null;
    notifyImpersonationListeners();
  },
  subscribe(listener: () => void): () => void {
    impersonationListeners.add(listener);
    return () => impersonationListeners.delete(listener);
  },
};
