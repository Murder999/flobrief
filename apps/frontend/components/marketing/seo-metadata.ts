import type { Metadata } from "next";

import type { LandingPageConfig } from "./seo-landing-data";

const PUBLIC_ORIGIN = "https://postpiloter.com";

export function buildLandingMetadata(config: LandingPageConfig): Metadata {
  const canonical = `${PUBLIC_ORIGIN}/${config.slug}`;

  return {
    title: { absolute: config.title },
    description: config.metaDescription,
    alternates: { canonical },
    robots: { index: true, follow: true },
    openGraph: {
      type: "website",
      locale: "tr_TR",
      siteName: "PostPiloter",
      url: canonical,
      title: config.title,
      description: config.metaDescription,
    },
  };
}
