"use client";

import { authApi, type AuthUser, type LoginRequest, type RegisterRequest, ApiError } from "@/lib/api-client";
import { getRedirectAfterLogin, isSafeReturnTo } from "@/lib/auth";
import { useLocale } from "@/context/locale-context";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  isLoading: boolean;
  isInitialized: boolean;
}

interface AuthContextValue extends AuthState {
  login: (data: LoginRequest, returnTo?: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { applyUserLocale, locale } = useLocale();
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    isLoading: false,
    isInitialized: false,
  });

  const refreshing = useRef(false);

  const refreshSession = useCallback(async (): Promise<boolean> => {
    if (refreshing.current) return false;
    refreshing.current = true;
    try {
      const data = await authApi.refresh();
      const user = await authApi.me(data.access_token);
      applyUserLocale(user.locale);
      setState((s) => ({
        ...s,
        user,
        accessToken: data.access_token,
        isInitialized: true,
      }));
      return true;
    } catch {
      setState((s) => ({
        ...s,
        user: null,
        accessToken: null,
        isInitialized: true,
      }));
      return false;
    } finally {
      refreshing.current = false;
    }
  }, [applyUserLocale]);

  useEffect(() => {
    // Platform admin sessions are a fully separate auth model (bearer token
    // held in memory via platformAuthStorage, refreshed from its own
    // platform_refresh_token HttpOnly cookie — see CLAUDE.md: platform_admin
    // is tenant-independent and never holds an agency/brand session).
    // Calling the agency/brand refresh-cookie flow on every /platform/* page
    // load always 401s there and is pure console noise.
    if (typeof window !== "undefined" && window.location.pathname.startsWith("/platform")) {
      setState((s) => ({ ...s, isInitialized: true }));
      return;
    }
    refreshSession();
  }, [refreshSession]);

  const login = useCallback(
    async (data: LoginRequest, returnTo?: string): Promise<void> => {
      setState((s) => ({ ...s, isLoading: true }));
      try {
        const tokens = await authApi.login(data);
        const user = await authApi.me(tokens.access_token);
        applyUserLocale(user.locale);
        setState((s) => ({
          ...s,
          user,
          accessToken: tokens.access_token,
          isLoading: false,
        }));
        const redirect =
          returnTo && isSafeReturnTo(returnTo)
            ? returnTo
            : getRedirectAfterLogin(user.user_type);
        router.push(redirect);
      } catch (err) {
        setState((s) => ({ ...s, isLoading: false }));
        throw err;
      }
    },
    [applyUserLocale, router]
  );

  const register = useCallback(async (data: RegisterRequest): Promise<AuthUser> => {
    setState((s) => ({ ...s, isLoading: true }));
    try {
      const user = await authApi.register({ ...data, locale: data.locale ?? locale });
      setState((s) => ({ ...s, isLoading: false }));
      return user;
    } catch (err) {
      setState((s) => ({ ...s, isLoading: false }));
      throw err;
    }
  }, [locale]);

  const refreshUser = useCallback(async (): Promise<void> => {
    const token = state.accessToken;
    if (!token) return;
    try {
      const user = await authApi.me(token);
      applyUserLocale(user.locale);
      setState((s) => ({ ...s, user }));
    } catch {
      // silent — token might be expired
    }
  }, [applyUserLocale, state.accessToken]);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await authApi.logout();
    } catch {
      // silent — still clear local state
    } finally {
      setState({
        user: null,
        accessToken: null,
        isLoading: false,
        isInitialized: true,
      });
      router.push("/auth/login");
    }
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        register,
        logout,
        refreshSession,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuthContext must be used inside <AuthProvider>");
  }
  return ctx;
}

export { ApiError };
