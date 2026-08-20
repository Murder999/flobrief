"use client";

import { Languages } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAuthContext } from "@/context/auth-context";
import { useLocale } from "@/context/locale-context";
import { authApi } from "@/lib/api-client";
import { localizePublicPath, type Locale } from "@/lib/i18n/config";
import { cn } from "@/lib/utils";

function FlagIcon({ locale }: { locale: Locale }) {
  if (locale === "tr") {
    return (
      <svg data-flag="tr" aria-hidden="true" viewBox="0 0 24 16" className="h-3 w-[18px] overflow-hidden rounded-[3px] shadow-sm">
        <rect width="24" height="16" fill="#E30A17" />
        <circle cx="9" cy="8" r="4.2" fill="#fff" />
        <circle cx="10.4" cy="8" r="3.35" fill="#E30A17" />
        <path d="m13.1 8 3.4-1.1-2.1 2.9V6.2l2.1 2.9L13.1 8Z" fill="#fff" />
      </svg>
    );
  }

  return (
    <svg data-flag="en" aria-hidden="true" viewBox="0 0 24 16" className="h-3 w-[18px] overflow-hidden rounded-[3px] shadow-sm">
      <rect width="24" height="16" fill="#21468B" />
      <path d="M0 0 24 16M24 0 0 16" stroke="#fff" strokeWidth="4" />
      <path d="M0 0 24 16M24 0 0 16" stroke="#CF142B" strokeWidth="1.8" />
      <path d="M12 0v16M0 8h24" stroke="#fff" strokeWidth="5" />
      <path d="M12 0v16M0 8h24" stroke="#CF142B" strokeWidth="2.5" />
    </svg>
  );
}

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
        "inline-flex items-center gap-0.5 rounded-xl border border-accent/20 bg-surface/95 p-1 shadow-sm ring-1 ring-accent/5 backdrop-blur",
        className
      )}
      role="group"
      aria-label={t("common.language.label")}
    >
      {!compact && <Languages aria-hidden="true" className="ml-2 h-4 w-4 text-text-muted" />}
      {(["tr", "en"] as const).map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => void changeLocale(option)}
          aria-label={compact ? option.toUpperCase() : t(option === "en" ? "common.language.english" : "common.language.turkish")}
          aria-pressed={locale === option}
          className={cn(
            "inline-flex min-h-8 items-center justify-center gap-1 rounded-lg px-1.5 text-[10px] font-bold tracking-wide transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 sm:px-2",
            locale === option ? "bg-gradient-accent text-white shadow-accent" : "text-text-muted hover:bg-surface-hover hover:text-text"
          )}
        >
          <FlagIcon locale={option} />
          {compact ? option.toUpperCase() : t(option === "en" ? "common.language.english" : "common.language.turkish")}
        </button>
      ))}
    </div>
  );
}
