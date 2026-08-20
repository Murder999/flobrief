import type { Metadata } from "next";

import { SeoLandingPage, getLandingPageConfig } from "@/components/marketing/SeoLandingPage";
import { buildLandingMetadata } from "@/components/marketing/seo-metadata";

const config = getLandingPageConfig("musteri-onay-sistemi");

export const metadata: Metadata = buildLandingMetadata(config);

export default function CustomerApprovalLandingPage() {
  return <SeoLandingPage config={config} />;
}
