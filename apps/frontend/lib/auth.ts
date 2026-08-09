import type { AuthUser } from "./api-client";

export type UserType = "agency_user" | "brand_user" | "platform_admin";

export function isPlatformAdmin(user: AuthUser | null): boolean {
  return user?.user_type === "platform_admin";
}

export function isAgencyUser(user: AuthUser | null): boolean {
  return user?.user_type === "agency_user";
}

export function isBrandUser(user: AuthUser | null): boolean {
  return user?.user_type === "brand_user";
}

export function getDisplayName(user: AuthUser | null): string {
  if (!user) return "";
  return user.full_name || user.email;
}

export function getInitials(fullName: string): string {
  return fullName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join("");
}

export function getRedirectAfterLogin(userType: UserType): string {
  if (userType === "platform_admin") return "/platform";
  if (userType === "brand_user") return "/brand/dashboard";
  return "/dashboard";
}

export function isSafeReturnTo(url: string): boolean {
  if (!url || typeof url !== "string") return false;
  if (!url.startsWith("/")) return false;
  if (url.startsWith("//")) return false;
  return true;
}
