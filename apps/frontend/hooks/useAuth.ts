"use client";

import { useAuthContext } from "@/context/auth-context";

export function useAuth() {
  return useAuthContext();
}

export function useUser() {
  const { user } = useAuthContext();
  return user;
}

export function useAccessToken() {
  const { accessToken } = useAuthContext();
  return accessToken;
}
