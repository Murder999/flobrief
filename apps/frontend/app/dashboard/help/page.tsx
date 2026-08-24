"use client";

import { useEffect } from "react";
import { useLocale } from "@/context/locale-context";
import { translate } from "@/lib/i18n/translate";
import type { Locale } from "@/lib/i18n/config";
import type { TranslationKey } from "@/messages";
import { cn } from "@/lib/utils";

interface HelpTopic {
  title: TranslationKey;
  description: TranslationKey;
  sections: TranslationKey;
}

const AGENCY_HELP_TOPICS = {
  portalIntroduction: {
    title: "agency.help.portalIntroduction",
    description: "agency.help.portalIntroDescription",
    sections: "agency.help.portalIntroSections",
  },
  briefCreation: {
    title: "agency.help.briefCreation",
    description: "agency.help.briefCreationDescription",
    sections: "agency.help.briefCreationSections",
  },
  revisionProcess: {
    title: "agency.help.revisionProcess",
    description: "agency.help.revisionProcessDescription",
    sections: "agency.help.revisionProcessSections",
  },
  approvalWorkflow: {
    title: "agency.help.approvalWorkflow",
    description: "agency.help.approvalWorkflowDescription",
    sections: "agency.help.approvalWorkflowSections",
  },
  notificationPreferences: {
    title: "agency.help.notificationPreferences",
    description: "agency.help.notificationPreferencesDescription",
    sections: "agency.help.notificationPreferencesSections",
  },
  reports: {
    title: "agency.help.reports",
    description: "agency.help.reportsDescription",
    sections: "agency.help.reportsSections",
  },
  whiteLabel: {
    title: "agency.help.whiteLabel",
    description: "agency.help.whiteLabelDescription",
    sections: "agency.help.whiteLabelSections",
  },
  teamRoles: {
    title: "agency.help.teamRoles",
    description: "agency.help.teamRolesDescription",
    sections: "agency.help.teamRolesSections",
  },
} satisfies Record<string, HelpTopic>;

export default function AgencyHelpCenter() {
  const { locale } = useLocale();

  useEffect(() => {
    document.title = `${translate(locale, "dashboard.navigation.help") || "Help"} | Flobrief`;
  }, [locale]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-text">
          {translate(locale, "dashboard.navigation.help") || "Yardım Merkezi"}
        </h1>
        <p className="text-text-muted text-sm">
          {translate(locale, "dashboard.navigation.portal") || "Ajans portalı"}
        </p>
      </div>

      <HelpCenterContent
        locale={locale}
        topics={AGENCY_HELP_TOPICS}
        translate={translate}
      />
    </div>
  );
}

function HelpCenterContent({
  locale,
  topics,
  translate: t,
}: {
  locale: Locale;
  topics: Record<string, HelpTopic>;
  translate: typeof translate;
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Category navigation */}
      <div className="lg:col-span-1 space-y-2">
        <div className="bg-surface-2 rounded-2xl p-4 sticky top-6 h-fit">
          <h2 className="text-sm font-semibold text-text-uppercase tracking-wider mb-3">
            {t(locale, "dashboard.navigation.general")}
          </h2>
          <nav className="space-y-1">
            {Object.keys(topics).map((key) => {
              const topic = topics[key];
              const isDefault = key === "portalIntroduction";
              return (
                <button
                  key={key}
                  className={cn(
                    "w-full justify-start rounded-lg border border-preview px-3 py-2 text-sm font-medium transition-colors",
                    isDefault ? "bg-accent-subtle text-accent" : "text-text-secondary hover:text-text hover:bg-hover"
                  )}
                  onClick={() => {}}
                >
                  {t(locale, topic.title)}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Help content area */}
      <div className="lg:col-span-2 space-y-6">
        {Object.keys(topics).map((key) => {
          const topic = topics[key];
          return (
            <div
              key={key}
              className={cn(
                "hidden",
                key === "portalIntroduction" ? "block" : "hidden"
              )}
            >
              <div className="rounded-2xl border border-border p-5">
                <h2 className="text-xl font-bold text-text mb-3">
                    {t(locale, topic.title)}
                </h2>
                <p className="text-text-muted mb-4">{t(locale, topic.description)}</p>
                <ul className="space-y-2 text-sm text-text-muted">
                  {topic.sections ? (
                    <li className="text-xs text-text-muted">
                      {t(locale, topic.sections)}
                    </li>
                  ) : (
                    <li className="text-xs text-text-muted">No details available</li>
                  )}
                </ul>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
