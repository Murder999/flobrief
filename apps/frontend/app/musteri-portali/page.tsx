import type { Metadata } from "next";

import { SeoLandingPage, getLandingPageConfig } from "@/components/marketing/SeoLandingPage";
import { buildLandingMetadata } from "@/components/marketing/seo-metadata";

const config = getLandingPageConfig("musteri-portali");

export const metadata: Metadata = buildLandingMetadata(config);

export default function CustomerPortalLandingPage() {
  return <SeoLandingPage config={config} />;
}
