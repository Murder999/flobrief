import { DEFAULT_LOCALE, localeToIntl, normalizeLocale, type Locale } from "./config";

export function resolveFormattingLocale(locale?: Locale | string | null): "en-US" | "tr-TR" {
  const normalized = normalizeLocale(locale);
  if (normalized) return localeToIntl(normalized);
  if (typeof document !== "undefined") return localeToIntl(normalizeLocale(document.documentElement.lang) ?? DEFAULT_LOCALE);
  return localeToIntl(DEFAULT_LOCALE);
}

export function formatLocalizedDate(
  value: Date | string | number,
  locale?: Locale | string | null,
  options: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short", year: "numeric" }
): string {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat(resolveFormattingLocale(locale), options).format(date);
}

export function formatLocalizedDateTime(value: Date | string | number, locale?: Locale | string | null): string {
  return formatLocalizedDate(value, locale, { dateStyle: "medium", timeStyle: "short" });
}

export function formatLocalizedNumber(value: number, locale?: Locale | string | null, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(resolveFormattingLocale(locale), options).format(value);
}

export function formatLocalizedCurrency(
  value: number,
  currency: string,
  locale?: Locale | string | null,
  options?: Omit<Intl.NumberFormatOptions, "style" | "currency">
): string {
  try {
    return new Intl.NumberFormat(resolveFormattingLocale(locale), {
      style: "currency",
      currency,
      ...options,
    }).format(value);
  } catch {
    return `${value.toFixed(options?.minimumFractionDigits ?? 2)} ${currency}`;
  }
}
