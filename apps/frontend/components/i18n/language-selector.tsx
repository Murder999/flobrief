"use client";

import { Globe2 } from "lucide-react";
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
        "inline-flex items-center gap-1 rounded-2xl border border-accent/25 bg-background/95 p-1.5 shadow-[0_10px_32px_rgba(79,70,229,0.12)] ring-1 ring-white/60 backdrop-blur-xl",
        className
      )}
      role="group"
      aria-label={t("common.language.label")}
    >
      {!compact && <Globe2 aria-hidden="true" className="ml-1.5 h-4 w-4 text-accent" />}
      {(["tr", "en"] as const).map((option) => {
        const languageName = t(option === "en" ? "common.language.english" : "common.language.turkish");
        return (
          <button
            key={option}
            type="button"
            onClick={() => void changeLocale(option)}
            aria-label={compact ? option.toUpperCase() : languageName}
            aria-pressed={locale === option}
            title={languageName}
            className={cn(
              "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-xl px-2.5 text-xs font-bold tracking-wide transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2",
              locale === option
                ? "bg-gradient-accent text-white shadow-accent"
                : "text-text-secondary hover:bg-accent-subtle hover:text-accent"
            )}
          >
            <span aria-hidden="true" className="text-base leading-none">{option === "tr" ? "🇹🇷" : "🇬🇧"}</span>
            <span>{compact ? option.toUpperCase() : languageName}</span>
          </button>
        );
      })}
    </div>
  );
}
