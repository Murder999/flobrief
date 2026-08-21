import type { LegalPageConfig } from "./LegalPage";

export const LEGAL_PAGES_CONFIG: Record<string, LegalPageConfig> = {
  terms: {
    titleKey: "marketing.legal.terms.title",
    lastUpdatedKey: "marketing.legal.terms.lastUpdated",
    introKey: "marketing.legal.terms.intro",
    sections: [
      {
        id: "serviceDescription",
        titleKey: "marketing.legal.terms.serviceDescription",
        contentKeys: ["marketing.legal.terms.serviceDescriptionText"],
      },
      {
        id: "accountRegistration",
        titleKey: "marketing.legal.terms.accountRegistration",
        contentKeys: ["marketing.legal.terms.accountRegistrationText"],
      },
      {
        id: "accountSecurity",
        titleKey: "marketing.legal.terms.accountSecurity",
        contentKeys: ["marketing.legal.terms.accountSecurityText"],
      },
      {
        id: "authorizedUse",
        titleKey: "marketing.legal.terms.authorizedUse",
        contentKeys: ["marketing.legal.terms.authorizedUseText"],
      },
      {
        id: "subscriptionPlans",
        titleKey: "marketing.legal.terms.subscriptionPlans",
        contentKeys: ["marketing.legal.terms.subscriptionPlansText"],
      },
      {
        id: "billing",
        titleKey: "marketing.legal.terms.billing",
        contentKeys: ["marketing.legal.terms.billingText"],
      },
      {
        id: "recurringSubscriptions",
        titleKey: "marketing.legal.terms.recurringSubscriptions",
        contentKeys: ["marketing.legal.terms.recurringSubscriptionsText"],
      },
      {
        id: "automaticRenewal",
        titleKey: "marketing.legal.terms.automaticRenewal",
        contentKeys: ["marketing.legal.terms.automaticRenewalText"],
      },
      {
        id: "cancellation",
        titleKey: "marketing.legal.terms.cancellation",
        contentKeys: ["marketing.legal.terms.cancellationText"],
      },
      {
        id: "paddlePayment",
        titleKey: "marketing.legal.terms.paddlePayment",
        contentKeys: ["marketing.legal.terms.paddlePaymentText"],
      },
      {
        id: "changesToPlans",
        titleKey: "marketing.legal.terms.changesToPlans",
        contentKeys: ["marketing.legal.terms.changesToPlansText"],
      },
      {
        id: "userContent",
        titleKey: "marketing.legal.terms.userContent",
        contentKeys: ["marketing.legal.terms.userContentText"],
      },
      {
        id: "uploadedFiles",
        titleKey: "marketing.legal.terms.uploadedFiles",
        contentKeys: ["marketing.legal.terms.uploadedFilesText"],
      },
      {
        id: "customerResponsibilities",
        titleKey: "marketing.legal.terms.customerResponsibilities",
        contentKeys: ["marketing.legal.terms.customerResponsibilitiesText"],
      },
      {
        id: "prohibitedUse",
        titleKey: "marketing.legal.terms.prohibitedUse",
        contentKeys: ["marketing.legal.terms.prohibitedUseText"],
      },
      {
        id: "intellectualProperty",
        titleKey: "marketing.legal.terms.intellectualProperty",
        contentKeys: ["marketing.legal.terms.intellectualPropertyText"],
      },
      {
        id: "serviceAvailability",
        titleKey: "marketing.legal.terms.serviceAvailability",
        contentKeys: ["marketing.legal.terms.serviceAvailabilityText"],
      },
      {
        id: "thirdPartyServices",
        titleKey: "marketing.legal.terms.thirdPartyServices",
        contentKeys: ["marketing.legal.terms.thirdPartyServicesText"],
      },
      {
        id: "suspensionTermination",
        titleKey: "marketing.legal.terms.suspensionTermination",
        contentKeys: ["marketing.legal.terms.suspensionTerminationText"],
      },
      {
        id: "limitationOfLiability",
        titleKey: "marketing.legal.terms.limitationOfLiability",
        contentKeys: ["marketing.legal.terms.limitationOfLiabilityText"],
      },
      {
        id: "changesToTerms",
        titleKey: "marketing.legal.terms.changesToTerms",
        contentKeys: ["marketing.legal.terms.changesToTermsText"],
      },
    ],
    contactKey: "marketing.legal.terms.contact",
    contactTextKey: "marketing.legal.terms.contactText",
    contactEmail: "legal@postpiloter.com",
  },

  privacy: {
    titleKey: "marketing.legal.privacy.title",
    lastUpdatedKey: "marketing.legal.privacy.lastUpdated",
    introKey: "marketing.legal.privacy.intro",
    sections: [
      {
        id: "informationCollected",
        titleKey: "marketing.legal.privacy.informationCollected",
        contentKeys: ["marketing.legal.privacy.informationCollectedText"],
      },
      {
        id: "accountData",
        titleKey: "marketing.legal.privacy.accountData",
        contentKeys: ["marketing.legal.privacy.accountDataText"],
      },
      {
        id: "workspaceData",
        titleKey: "marketing.legal.privacy.workspaceData",
        contentKeys: ["marketing.legal.privacy.workspaceDataText"],
      },
      {
        id: "userContent",
        titleKey: "marketing.legal.privacy.userContent",
        contentKeys: ["marketing.legal.privacy.userContentText"],
      },
      {
        id: "uploadedFiles",
        titleKey: "marketing.legal.privacy.uploadedFiles",
        contentKeys: ["marketing.legal.privacy.uploadedFilesText"],
      },
      {
        id: "usageData",
        titleKey: "marketing.legal.privacy.usageData",
        contentKeys: ["marketing.legal.privacy.usageDataText"],
      },
      {
        id: "cookies",
        titleKey: "marketing.legal.privacy.cookies",
        contentKeys: ["marketing.legal.privacy.cookiesText"],
      },
      {
        id: "authData",
        titleKey: "marketing.legal.privacy.authData",
        contentKeys: ["marketing.legal.privacy.authDataText"],
      },
      {
        id: "billingData",
        titleKey: "marketing.legal.privacy.billingData",
        contentKeys: ["marketing.legal.privacy.billingDataText"],
      },
      {
        id: "paddleProcessing",
        titleKey: "marketing.legal.privacy.paddleProcessing",
        contentKeys: ["marketing.legal.privacy.paddleProcessingText"],
      },
      {
        id: "emailNotifications",
        titleKey: "marketing.legal.privacy.emailNotifications",
        contentKeys: ["marketing.legal.privacy.emailNotificationsText"],
      },
      {
        id: "security",
        titleKey: "marketing.legal.privacy.security",
        contentKeys: ["marketing.legal.privacy.securityText"],
      },
      {
        id: "dataRetention",
        titleKey: "marketing.legal.privacy.dataRetention",
        contentKeys: ["marketing.legal.privacy.dataRetentionText"],
      },
      {
        id: "dataDeletion",
        titleKey: "marketing.legal.privacy.dataDeletion",
        contentKeys: ["marketing.legal.privacy.dataDeletionText"],
      },
      {
        id: "thirdPartyProcessors",
        titleKey: "marketing.legal.privacy.thirdPartyProcessors",
        contentKeys: ["marketing.legal.privacy.thirdPartyProcessorsText"],
      },
      {
        id: "internationalTransfers",
        titleKey: "marketing.legal.privacy.internationalTransfers",
        contentKeys: ["marketing.legal.privacy.internationalTransfersText"],
      },
      {
        id: "userRights",
        titleKey: "marketing.legal.privacy.userRights",
        contentKeys: ["marketing.legal.privacy.userRightsText"],
      },
      {
        id: "kvkk",
        titleKey: "marketing.legal.privacy.kvkk",
        contentKeys: ["marketing.legal.privacy.kvkkText"],
      },
      {
        id: "gdpr",
        titleKey: "marketing.legal.privacy.gdpr",
        contentKeys: ["marketing.legal.privacy.gdprText"],
      },
      {
        id: "childrenPrivacy",
        titleKey: "marketing.legal.privacy.childrenPrivacy",
        contentKeys: ["marketing.legal.privacy.childrenPrivacyText"],
      },
      {
        id: "policyChanges",
        titleKey: "marketing.legal.privacy.policyChanges",
        contentKeys: ["marketing.legal.privacy.policyChangesText"],
      },
    ],
    contactKey: "marketing.legal.privacy.contact",
    contactTextKey: "marketing.legal.privacy.contactText",
    contactEmail: "privacy@postpiloter.com",
  },

  refund: {
    titleKey: "marketing.legal.refund.title",
    lastUpdatedKey: "marketing.legal.refund.lastUpdated",
    introKey: "marketing.legal.refund.intro",
    sections: [
      {
        id: "monthlySubscriptions",
        titleKey: "marketing.legal.refund.monthlySubscriptions",
        contentKeys: ["marketing.legal.refund.monthlySubscriptionsText"],
      },
      {
        id: "annualSubscriptions",
        titleKey: "marketing.legal.refund.annualSubscriptions",
        contentKeys: ["marketing.legal.refund.annualSubscriptionsText"],
      },
      {
        id: "cancellation",
        titleKey: "marketing.legal.refund.cancellation",
        contentKeys: ["marketing.legal.refund.cancellationText"],
      },
      {
        id: "renewal",
        titleKey: "marketing.legal.refund.renewal",
        contentKeys: ["marketing.legal.refund.renewalText"],
      },
      {
        id: "requests",
        titleKey: "marketing.legal.refund.requests",
        contentKeys: ["marketing.legal.refund.requestsText"],
      },
      {
        id: "duplicateCharges",
        titleKey: "marketing.legal.refund.duplicateCharges",
        contentKeys: ["marketing.legal.refund.duplicateChargesText"],
      },
      {
        id: "technicalErrors",
        titleKey: "marketing.legal.refund.technicalErrors",
        contentKeys: ["marketing.legal.refund.technicalErrorsText"],
      },
      {
        id: "consumerRights",
        titleKey: "marketing.legal.refund.consumerRights",
        contentKeys: ["marketing.legal.refund.consumerRightsText"],
      },
      {
        id: "paddleRole",
        titleKey: "marketing.legal.refund.paddleRole",
        contentKeys: ["marketing.legal.refund.paddleRoleText"],
      },
    ],
    contactKey: "marketing.legal.refund.contact",
    contactTextKey: "marketing.legal.refund.contactText",
    contactEmail: "billing@postpiloter.com",
  },

  contact: {
    titleKey: "marketing.legal.contact.title",
    lastUpdatedKey: "marketing.legal.terms.lastUpdated",
    introKey: "marketing.legal.contact.subtitle",
    sections: [
      {
        id: "supportEmail",
        titleKey: "marketing.legal.contact.supportEmail",
        contentKeys: ["marketing.legal.contact.supportEmailText"],
        email: "support@postpiloter.com",
      },
      {
        id: "legalEmail",
        titleKey: "marketing.legal.contact.legalEmail",
        contentKeys: ["marketing.legal.contact.legalEmailText"],
        email: "legal@postpiloter.com",
      },
      {
        id: "salesEmail",
        titleKey: "marketing.legal.contact.salesEmail",
        contentKeys: ["marketing.legal.contact.salesEmailText"],
        email: "sales@postpiloter.com",
      },
      {
        id: "responseTime",
        titleKey: "marketing.legal.contact.responseTime",
        contentKeys: ["marketing.legal.contact.responseTimeText"],
      },
      {
        id: "dashboard",
        titleKey: "marketing.legal.contact.dashboard",
        contentKeys: ["marketing.legal.contact.dashboardText"],
      },
    ],
    contactKey: "marketing.legal.contact.footer",
    contactTextKey: "marketing.legal.contact.footer",
    contactEmail: "support@postpiloter.com",
  },
};

export function getLegalPageConfig(slug: string): LegalPageConfig | undefined {
  return LEGAL_PAGES_CONFIG[slug];
}

const PUBLIC_ORIGIN = "https://postpiloter.com";

const LEGAL_METADATA = {
  terms: {
    en: { title: "Terms of Service | PostPiloter", description: "Read the terms governing access to and use of PostPiloter services, subscriptions, billing, content, and accounts." },
    tr: { title: "Kullanım Koşulları | PostPiloter", description: "PostPiloter hizmetleri, abonelikler, faturalandırma, içerik ve hesap kullanımına ilişkin koşulları inceleyin." },
  },
  privacy: {
    en: { title: "Privacy Policy | PostPiloter", description: "Learn how PostPiloter collects, uses, protects, retains, and processes personal and workspace data." },
    tr: { title: "Gizlilik Politikası | PostPiloter", description: "PostPiloter'ın kişisel ve çalışma alanı verilerini nasıl topladığını, kullandığını, koruduğunu ve sakladığını öğrenin." },
  },
  "refund-policy": {
    en: { title: "Refund Policy | PostPiloter", description: "Review PostPiloter subscription cancellation, renewal, refund request, billing error, and consumer-rights terms." },
    tr: { title: "İade Politikası | PostPiloter", description: "PostPiloter abonelik iptali, yenileme, iade talebi, faturalandırma hatası ve tüketici hakları koşullarını inceleyin." },
  },
  contact: {
    en: { title: "Contact PostPiloter", description: "Contact PostPiloter for support, billing, legal, privacy, sales, and partnership inquiries." },
    tr: { title: "PostPiloter ile İletişime Geçin", description: "Destek, faturalandırma, hukuk, gizlilik, satış ve iş birliği konuları için PostPiloter'a ulaşın." },
  },
} as const;

export function buildLegalMetadata(
  config: LegalPageConfig,
  locale: "en" | "tr",
  slug: string
): import("next").Metadata {
  const normalizedPath = slug.startsWith("/") ? slug : `/${slug}`;
  const metadataKey = normalizedPath.slice(1) as keyof typeof LEGAL_METADATA;
  const copy = LEGAL_METADATA[metadataKey][locale];
  const englishUrl = `${PUBLIC_ORIGIN}${normalizedPath}`;
  const turkishUrl = `${PUBLIC_ORIGIN}/tr${normalizedPath}`;
  const canonical = locale === "tr" ? turkishUrl : englishUrl;

  return {
    title: { absolute: copy.title },
    description: copy.description,
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
      title: copy.title,
      description: copy.description,
    },
  };
}
