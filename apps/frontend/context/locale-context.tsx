"use client";

import {
  LOCALE_COOKIE_NAME,
  LOCALE_STORAGE_KEY,
  localeToIntl,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/config";
import { translate, type TranslationValues } from "@/lib/i18n/translate";
import type { TranslationKey } from "@/messages";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

interface LocaleContextValue {
  locale: Locale;
  intlLocale: "en-US" | "tr-TR";
  setLocale: (locale: Locale) => void;
  applyUserLocale: (locale: string | null | undefined) => void;
  t: (key: TranslationKey, values?: TranslationValues) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

function hasManualLocale(): boolean {
  if (typeof window === "undefined") return false;
  return normalizeLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY)) !== null;
}

export function LocaleProvider({ initialLocale, children }: { initialLocale: Locale; children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  useEffect(() => {
    const pathLocale = window.location.pathname === "/tr" || window.location.pathname.startsWith("/tr/")
      ? "tr"
      : null;
    const storedLocale = normalizeLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY));
    if (pathLocale) setLocaleState(pathLocale);
    else if (storedLocale) setLocaleState(storedLocale);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((nextLocale: Locale) => {
    document.documentElement.lang = nextLocale;
    setLocaleState(nextLocale);
    window.localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale);
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${LOCALE_COOKIE_NAME}=${nextLocale}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
  }, []);

  const applyUserLocale = useCallback((value: string | null | undefined) => {
    if (hasManualLocale()) return;
    const userLocale = normalizeLocale(value);
    if (userLocale) setLocaleState(userLocale);
  }, []);

  const contextValue = useMemo<LocaleContextValue>(() => ({
    locale,
    intlLocale: localeToIntl(locale),
    setLocale,
    applyUserLocale,
    t: (key, values) => translate(locale, key, values),
  }), [applyUserLocale, locale, setLocale]);

  return <LocaleContext.Provider value={contextValue}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used inside <LocaleProvider>");
  return context;
}
