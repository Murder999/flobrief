import type { TranslationKey } from "@/messages";
import { DEFAULT_LOCALE, normalizeLocale, type Locale } from "./config";
import { translate, type TranslationValues } from "./translate";

export function currentLocale(): Locale {
  if (typeof document === "undefined") return DEFAULT_LOCALE;
  return normalizeLocale(document.documentElement.lang) ?? DEFAULT_LOCALE;
}

export function translateCurrent(key: TranslationKey, values?: TranslationValues): string {
  return translate(currentLocale(), key, values);
}
