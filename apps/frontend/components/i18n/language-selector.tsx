"use client";

import { Languages } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAuthContext } from "@/context/auth-context";
import { useLocale } from "@/context/locale-context";
import { authApi } from "@/lib/api-client";
import { localizePublicPath, type Locale } from "@/lib/i18n/config";
import { cn } from "@/lib/utils";

export function LanguageSelector({ compact = false, className }: { compact?: boolean; className?: string }) {
  const { locale, setLocale, t } = useLocale();
  const { accessToken, refreshUser } = useAuthContext();
  const pathname = usePathname();

  async function changeLocale(nextLocale: Locale) {
    if (nextLocale === locale) return;
    setLocale(nextLocale);
    const visiblePath = typeof window === "undefined" ? pathname : window.location.pathname;
    const localizedPath = localizePublicPath(visiblePath, nextLocale);
    if (localizedPath !== visiblePath) window.location.assign(localizedPath);

    if (accessToken) {
      try {
        await authApi.updateProfile({ locale: nextLocale }, accessToken);
        await refreshUser();
      } catch {
        // The local manual preference remains valid if profile synchronization is temporarily unavailable.
      }
    }
  }

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-xl border border-border bg-surface p-1 shadow-sm",
        className
      )}
      role="group"
      aria-label={t("common.language.label")}
    >
      {!compact && <Languages aria-hidden="true" className="ml-2 h-4 w-4 text-text-muted" />}
      {(["en", "tr"] as const).map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => void changeLocale(option)}
          aria-pressed={locale === option}
          className={cn(
            "min-h-9 rounded-lg px-2.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
            locale === option ? "bg-primary text-white shadow-sm" : "text-text-muted hover:bg-surface-hover hover:text-text"
          )}
        >
          {compact ? option.toUpperCase() : t(option === "en" ? "common.language.english" : "common.language.turkish")}
        </button>
      ))}
    </div>
  );
}
