"use client";

import Link from "next/link";
import { useState } from "react";
import { useLocale } from "@/context/locale-context";
import type { TranslationKey } from "@/messages";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface OnboardingData {
  hasAgencyName: boolean;
  hasBrand: boolean;
  hasMember: boolean;
  hasTemplate: boolean;
  hasBrief: boolean;
}

interface ChecklistItem {
  key: keyof OnboardingData;
  labelKey: TranslationKey;
  href: string;
  ctaKey: TranslationKey;
}

const CHECKLIST_ITEMS: ChecklistItem[] = [
  {
    key: "hasAgencyName",
    labelKey: "dashboard.onboarding.agency",
    href: "/dashboard/settings/agency",
    ctaKey: "dashboard.onboarding.editAgency",
  },
  {
    key: "hasBrand",
    labelKey: "dashboard.onboarding.brand",
    href: "/dashboard/brands",
    ctaKey: "dashboard.onboarding.addBrand",
  },
  {
    key: "hasMember",
    labelKey: "dashboard.onboarding.member",
    href: "/dashboard/settings/members",
    ctaKey: "dashboard.onboarding.inviteMember",
  },
  {
    key: "hasTemplate",
    labelKey: "dashboard.onboarding.template",
    href: "/dashboard/templates",
    ctaKey: "dashboard.onboarding.createTemplate",
  },
  {
    key: "hasBrief",
    labelKey: "dashboard.onboarding.brief",
    href: "/dashboard/briefs/new",
    ctaKey: "dashboard.onboarding.createBrief",
  },
];

const STORAGE_KEY = "flobrief_onboarding_dismissed";

// ── Component ─────────────────────────────────────────────────────────────────

export function OnboardingChecklist({ data }: { data: OnboardingData }) {
  const { t } = useLocale();
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(STORAGE_KEY) === "true";
  });

  const completedCount = CHECKLIST_ITEMS.filter((item) => data[item.key]).length;
  const totalCount = CHECKLIST_ITEMS.length;

  if (dismissed || completedCount === totalCount) return null;

  const handleDismiss = () => {
    localStorage.setItem(STORAGE_KEY, "true");
    setDismissed(true);
  };

  const nextIncomplete = CHECKLIST_ITEMS.find((item) => !data[item.key]);
  const progressPct = (completedCount / totalCount) * 100;

  return (
    <div className="mb-8 bg-surface border border-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-accent/10 rounded-lg flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-text">{t("dashboard.onboarding.title")}</h2>
            <p className="text-xs text-text-muted mt-0.5">
              {t("dashboard.onboarding.progress", { completed: completedCount, total: totalCount })}
            </p>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="text-xs text-text-muted hover:text-text transition-colors px-3 py-1.5 rounded-lg hover:bg-surface-2"
        >
          {t("dashboard.onboarding.skip")}
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-0.5 bg-surface-2">
        <div
          className="h-full bg-accent transition-all duration-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Steps */}
      <div className="px-6 py-4">
        <div className="space-y-3">
          {CHECKLIST_ITEMS.map((item) => {
            const done = data[item.key];
            return (
              <div key={item.key} className="flex items-center gap-3">
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 border-2 transition-colors ${
                    done
                      ? "bg-emerald-500 border-emerald-500"
                      : "border-border bg-transparent"
                  }`}
                >
                  {done && (
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <p className={`flex-1 text-sm ${done ? "text-text-muted line-through" : "text-text"}`}>
                  {t(item.labelKey)}
                </p>
                {!done && (
                  <Link
                    href={item.href}
                    className="flex-shrink-0 text-xs text-accent hover:text-accent-hover font-medium"
                  >
                    {t(item.ctaKey)} →
                  </Link>
                )}
              </div>
            );
          })}
        </div>

        {/* Next step CTA */}
        {nextIncomplete && (
          <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
            <p className="text-xs text-text-muted">
              {t("dashboard.onboarding.next")}{" "}
              <span className="text-text font-medium">{t(nextIncomplete.labelKey)}</span>
            </p>
            <Link
              href={nextIncomplete.href}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-medium rounded-lg hover:bg-accent-hover transition-colors"
            >
              {t(nextIncomplete.ctaKey)}
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
