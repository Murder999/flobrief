"use client";

import Link from "next/link";
import { useState } from "react";

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
  label: string;
  description: string;
  href: string;
  cta: string;
}

const CHECKLIST_ITEMS: ChecklistItem[] = [
  {
    key: "hasAgencyName",
    label: "Ajans bilgilerini tamamla",
    description: "Ajans adınızı ve temel bilgilerinizi ekleyin.",
    href: "/dashboard/settings/agency",
    cta: "Ajansı Düzenle",
  },
  {
    key: "hasBrand",
    label: "İlk markanı ekle",
    description: "Yönettiğiniz markaları platforma ekleyin.",
    href: "/dashboard/brands",
    cta: "Marka Ekle",
  },
  {
    key: "hasMember",
    label: "Ekip üyesi davet et",
    description: "Takım arkadaşlarınızı ajansınıza davet edin.",
    href: "/dashboard/settings/members",
    cta: "Üye Davet Et",
  },
  {
    key: "hasTemplate",
    label: "Brief şablonu oluştur",
    description: "Brief süreçlerinizi hızlandıracak şablonlar oluşturun.",
    href: "/dashboard/templates",
    cta: "Şablon Oluştur",
  },
  {
    key: "hasBrief",
    label: "İlk briefinizi oluştur",
    description: "Platformu kullanmaya başlamak için bir brief oluşturun.",
    href: "/dashboard/briefs/new",
    cta: "Brief Oluştur",
  },
];

const STORAGE_KEY = "flobrief_onboarding_dismissed";

// ── Component ─────────────────────────────────────────────────────────────────

export function OnboardingChecklist({ data }: { data: OnboardingData }) {
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
            <h2 className="text-sm font-semibold text-text">Kurulum Rehberi</h2>
            <p className="text-xs text-text-muted mt-0.5">
              {completedCount}/{totalCount} adım tamamlandı
            </p>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="text-xs text-text-muted hover:text-text transition-colors px-3 py-1.5 rounded-lg hover:bg-surface-2"
        >
          Atla
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
                  {item.label}
                </p>
                {!done && (
                  <Link
                    href={item.href}
                    className="flex-shrink-0 text-xs text-accent hover:text-accent-hover font-medium"
                  >
                    {item.cta} →
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
              Sonraki adım:{" "}
              <span className="text-text font-medium">{nextIncomplete.label}</span>
            </p>
            <Link
              href={nextIncomplete.href}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-medium rounded-lg hover:bg-accent-hover transition-colors"
            >
              {nextIncomplete.cta}
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
