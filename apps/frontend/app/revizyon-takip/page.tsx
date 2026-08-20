import type { Metadata } from "next";

import { SeoLandingPage, getLandingPageConfig } from "@/components/marketing/SeoLandingPage";
import { buildLandingMetadata } from "@/components/marketing/seo-metadata";

const config = getLandingPageConfig("revizyon-takip");

export const metadata: Metadata = buildLandingMetadata(config);

export default function RevisionTrackingLandingPage() {
  return <SeoLandingPage config={config} />;
}
