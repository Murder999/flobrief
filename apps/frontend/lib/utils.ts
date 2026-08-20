import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatLocalizedDate } from "@/lib/i18n/format";
import type { Locale } from "@/lib/i18n/config";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatDate(date: Date | string, options?: Intl.DateTimeFormatOptions, locale?: Locale): string {
  return formatLocalizedDate(date, locale, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...options,
  });
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return `${str.slice(0, length)}…`;
}

/**
 * True only for a same-app relative path ("/dashboard/briefs/…"). Rejects
 * protocol-relative ("//host/…"), absolute ("https://…"), and scheme URLs
 * ("javascript:…") — defense in depth even though the backend only ever
 * emits trusted relative routes for notification action_url.
 */
export function isSafeInternalPath(url: string | null | undefined): url is string {
  if (!url) return false;
  if (!url.startsWith("/") || url.startsWith("//")) return false;
  return true;
}
