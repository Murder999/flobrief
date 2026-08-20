import type { Metadata } from "next";
import { headers } from "next/headers";

import type { LandingPageConfig } from "./seo-landing-data";
import { SEO_LANDING_PAGES_EN } from "./seo-landing-data-en";
import { LOCALE_HEADER_NAME, normalizeLocale } from "@/lib/i18n/config";

const PUBLIC_ORIGIN = "https://postpiloter.com";

export function buildLandingMetadata(config: LandingPageConfig, locale: "en" | "tr" = "en"): Metadata {
  if (locale === "en") config = SEO_LANDING_PAGES_EN[config.slug];
  const englishUrl = `${PUBLIC_ORIGIN}/${config.slug}`;
  const turkishUrl = `${PUBLIC_ORIGIN}/tr/${config.slug}`;
  const canonical = locale === "tr" ? turkishUrl : englishUrl;

  return {
    title: { absolute: config.title },
    description: config.metaDescription,
    alternates: {
      canonical,
      languages: { en: englishUrl, tr: turkishUrl, "x-default": englishUrl },
    },
    robots: { index: true, follow: true },
    openGraph: {
      type: "website",
      locale: locale === "tr" ? "tr_TR" : "en_US",
      alternateLocale: [locale === "tr" ? "en_US" : "tr_TR"],
      siteName: "PostPiloter",
      url: canonical,
      title: config.title,
      description: config.metaDescription,
    },
  };
}

export function buildRequestLandingMetadata(config: LandingPageConfig): Metadata {
  const locale = normalizeLocale(headers().get(LOCALE_HEADER_NAME)) ?? "en";
  return buildLandingMetadata(config, locale);
}
