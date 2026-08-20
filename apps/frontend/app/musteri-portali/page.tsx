import { SeoLandingPage } from "@/components/marketing/SeoLandingPage";
import { SEO_LANDING_PAGES } from "@/components/marketing/seo-landing-data";
import { buildRequestLandingMetadata } from "@/components/marketing/seo-metadata";

const config = SEO_LANDING_PAGES["musteri-portali"];

export const generateMetadata = () => buildRequestLandingMetadata(config);

export default function CustomerPortalLandingPage() {
  return <SeoLandingPage config={config} />;
}
