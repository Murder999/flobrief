"use client";

import Link from "next/link";
import { ArrowRight, Mail, Shield } from "lucide-react";
import { PublicHeader } from "./PublicHeader";
import { PublicFooter } from "./PublicFooter";
import { useLocale } from "@/context/locale-context";
import { localizePublicPath } from "@/lib/i18n/config";
import type { TranslationKey } from "@/messages";

export interface LegalSection {
  id: string;
  titleKey: TranslationKey;
  contentKeys: TranslationKey[];
  email?: string;
}

export interface LegalPageConfig {
  titleKey: TranslationKey;
  lastUpdatedKey: TranslationKey;
  introKey: TranslationKey;
  sections: LegalSection[];
  contactKey?: TranslationKey;
  contactTextKey?: TranslationKey;
  contactEmail?: string;
}

const SECTION_ICONS: Record<string, React.ElementType> = {
  serviceDescription: Shield,
  accountRegistration: Shield,
  accountSecurity: Shield,
  authorizedUse: Shield,
  subscriptionPlans: Shield,
  billing: Shield,
  recurringSubscriptions: Shield,
  automaticRenewal: Shield,
  cancellation: Shield,
  paddlePayment: Shield,
  changesToPlans: Shield,
  userContent: Shield,
  uploadedFiles: Shield,
  customerResponsibilities: Shield,
  prohibitedUse: Shield,
  intellectualProperty: Shield,
  serviceAvailability: Shield,
  thirdPartyServices: Shield,
  suspensionTermination: Shield,
  limitationOfLiability: Shield,
  changesToTerms: Shield,
  contact: Mail,
  informationCollected: Shield,
  accountData: Shield,
  workspaceData: Shield,
  usageData: Shield,
  cookies: Shield,
  authData: Shield,
  billingData: Shield,
  paddleProcessing: Shield,
  emailNotifications: Shield,
  security: Shield,
  dataRetention: Shield,
  dataDeletion: Shield,
  thirdPartyProcessors: Shield,
  internationalTransfers: Shield,
  userRights: Shield,
  kvkk: Shield,
  gdpr: Shield,
  childrenPrivacy: Shield,
  policyChanges: Shield,
  monthlySubscriptions: Shield,
  annualSubscriptions: Shield,
  renewal: Shield,
  requests: Shield,
  duplicateCharges: Shield,
  technicalErrors: Shield,
  consumerRights: Shield,
  paddleRole: Shield,
};

export function LegalPage({ config }: { config: LegalPageConfig }) {
  const { locale, t } = useLocale();
  const localize = (path: string) => localizePublicPath(path, locale);

  return (
    <div className="min-h-screen bg-background">
      <PublicHeader />
      <main id="main-content" className="pt-16">
        <section className="relative overflow-hidden py-20 sm:py-28">
          <div className="hero-grid absolute inset-0 opacity-20" />
          <div className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[700px] -translate-x-1/2 rounded-full bg-accent-subtle blur-[100px]" />
          <div className="relative mx-auto max-w-4xl px-6 text-center">
            <h1 className="text-4xl font-black leading-[1.05] tracking-[-0.045em] text-text sm:text-5xl">
              {t(config.titleKey)}
            </h1>
            <p className="mt-4 text-base text-text-muted">{t(config.lastUpdatedKey)}</p>
            <p className="mt-6 max-w-3xl mx-auto text-lg leading-relaxed text-text-secondary">{t(config.introKey)}</p>
          </div>
        </section>

        <div className="mx-auto max-w-6xl px-6 pb-20">
          <div className="lg:grid lg:grid-cols-[260px_minmax(0,1fr)] lg:items-start lg:gap-12">
          <nav className="sticky top-24 hidden max-h-[calc(100vh-7rem)] overflow-y-auto lg:block" aria-label={t("marketing.legal.common.tocLabel")}>
            <div className="rounded-xl border border-border bg-surface p-5 shadow-card">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-text-muted">
                {t("marketing.legal.common.onThisPage")}
              </p>
              <ul className="space-y-2">
                {config.sections.map((section) => (
                  <li key={section.id}>
                    <Link
                      href={`#${section.id}`}
                      className="text-sm text-text-muted transition-colors hover:text-text"
                    >
                      {t(section.titleKey)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </nav>

          <div className="min-w-0">
          <div className="space-y-12">
            {config.sections.map((section) => {
                const SectionIcon = SECTION_ICONS[section.id] ?? Shield;
                return (
                  <section key={section.id} id={section.id} className="space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent">
                        <SectionIcon className="h-4.5 w-4.5" />
                      </div>
                      <h2 className="text-2xl font-bold text-text">{t(section.titleKey)}</h2>
                    </div>
                    <div className="ml-12 space-y-3 text-base leading-relaxed text-text-secondary">
                      {section.contentKeys.map((key, idx) => (
                        <p key={idx}>{t(key)}</p>
                      ))}
                      {section.email && (
                        <Link
                          href={`mailto:${section.email}`}
                          className="inline-flex items-center gap-2 font-semibold text-accent underline transition-colors hover:text-text"
                        >
                          <Mail className="h-4 w-4" aria-hidden="true" />
                          {section.email}
                        </Link>
                      )}
                    </div>
                  </section>
                );
              })}

            {config.contactKey && config.contactTextKey && (
              <section className="border-t border-border pt-12">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent">
                    <Mail className="h-4.5 w-4.5" />
                  </div>
                  <h2 className="text-2xl font-bold text-text">{t(config.contactKey)}</h2>
                </div>
                <div className="ml-12 space-y-3 text-base leading-relaxed text-text-secondary">
                  <p>{t(config.contactTextKey)}</p>
                  <div className="mt-4 flex items-center gap-2 text-accent">
                    <ArrowRight className="h-4 w-4" />
                    <Link
                      href={`mailto:${config.contactEmail ?? "support@postpiloter.com"}`}
                      className="underline hover:text-text transition-colors"
                    >
                      {config.contactEmail ?? "support@postpiloter.com"}
                    </Link>
                  </div>
                </div>
              </section>
            )}
          </div>

          <div className="mt-16 rounded-2xl border border-border bg-surface p-8 text-center">
            <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent">
              <Shield className="h-5 w-5" />
            </div>
            <h2 className="text-2xl font-bold text-text sm:text-3xl">
              {t("marketing.legal.common.questionsTitle")}
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-text-secondary">
              {t("marketing.legal.common.questionsText")}
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href={localize("/contact")}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-gradient-accent px-6 text-sm font-bold text-white shadow-accent transition-transform hover:scale-[1.02]"
              >
                {t("marketing.legal.nav.contact")}
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href={localize("/pricing")}
                className="inline-flex min-h-11 items-center justify-center rounded-xl border border-border bg-background px-6 text-sm font-semibold text-text hover:border-border-hover"
              >
                {t("marketing.legal.common.viewPricing")}
              </Link>
            </div>
          </div>
          </div>
          </div>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
