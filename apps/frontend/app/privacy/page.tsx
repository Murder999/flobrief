import { LegalPage } from "@/components/marketing/LegalPage";
import { getLegalPageConfig, buildLegalMetadata } from "@/components/marketing/legal-data";
import { headers } from "next/headers";
import { LOCALE_HEADER_NAME, normalizeLocale } from "@/lib/i18n/config";
import type { Metadata } from "next";

const config = getLegalPageConfig("privacy")!;

export async function generateMetadata(): Promise<Metadata> {
  const locale = normalizeLocale(headers().get(LOCALE_HEADER_NAME)) ?? "en";
  return buildLegalMetadata(config, locale, "/privacy");
}

export default function PrivacyPage() {
  return <LegalPage config={config} />;
}