export const SUPPORTED_LOCALES = ["en", "tr"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE_NAME = "postpiloter_locale";
export const LOCALE_STORAGE_KEY = "postpiloter_locale";
export const LOCALE_HEADER_NAME = "x-postpiloter-locale";

export function normalizeLocale(value: string | null | undefined): Locale | null {
  if (!value) return null;
  const language = value.trim().toLowerCase().split(/[-_]/, 1)[0];
  return SUPPORTED_LOCALES.includes(language as Locale) ? (language as Locale) : null;
}

export function localeFromAcceptLanguage(value: string | null): Locale | null {
  if (!value) return null;

  const candidates = value
    .split(",")
    .map((entry) => {
      const [tag, ...parameters] = entry.trim().split(";");
      const qualityParameter = parameters.find((parameter) => parameter.trim().startsWith("q="));
      const quality = qualityParameter ? Number(qualityParameter.trim().slice(2)) : 1;
      return { locale: normalizeLocale(tag), quality: Number.isFinite(quality) ? quality : 0 };
    })
    .filter((candidate): candidate is { locale: Locale; quality: number } => Boolean(candidate.locale))
    .sort((left, right) => right.quality - left.quality);

  return candidates[0]?.locale ?? null;
}

export function localeFromCountry(value: string | null): Locale | null {
  return value?.trim().toUpperCase() === "TR" ? "tr" : null;
}

export function localeToIntl(locale: Locale): "en-US" | "tr-TR" {
  return locale === "tr" ? "tr-TR" : "en-US";
}

const PUBLIC_ROUTE_PREFIXES = [
  "/",
  "/pricing",
  "/contact",
  "/features",
  "/solutions",
  "/resources",
  "/ajans-programi",
  "/musteri-onay-sistemi",
  "/revizyon-takip",
  "/musteri-portali",
  "/online-brief",
  "/hakkimizda",
  "/gizlilik",
  "/kullanim-kosullari",
  "/kvkk",
  "/cerez-politikasi",
];

export function stripLocalePrefix(pathname: string): string {
  if (pathname === "/tr") return "/";
  return pathname.startsWith("/tr/") ? pathname.slice(3) || "/" : pathname;
}

export function isPublicLocalePath(pathname: string): boolean {
  const basePath = stripLocalePrefix(pathname);
  return PUBLIC_ROUTE_PREFIXES.some(
    (prefix) => prefix === "/" ? basePath === "/" : basePath === prefix || basePath.startsWith(`${prefix}/`)
  );
}

export function localizePublicPath(pathname: string, locale: Locale): string {
  if (!isPublicLocalePath(pathname)) return pathname;
  const basePath = stripLocalePrefix(pathname);
  if (locale === "en") return basePath;
  return basePath === "/" ? "/tr" : `/tr${basePath}`;
}
