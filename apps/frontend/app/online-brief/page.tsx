import type { Metadata } from "next";

import { SeoLandingPage, getLandingPageConfig } from "@/components/marketing/SeoLandingPage";
import { buildLandingMetadata } from "@/components/marketing/seo-metadata";

const config = getLandingPageConfig("online-brief");

export const metadata: Metadata = buildLandingMetadata(config);

export default function OnlineBriefLandingPage() {
  return <SeoLandingPage config={config} />;
}
