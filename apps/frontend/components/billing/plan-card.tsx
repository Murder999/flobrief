"use client";

import type { PlanRead } from "@/lib/api-client";
import { Check, Minus, Zap, ArrowRight } from "lucide-react";

interface PlanCardProps {
  plan: PlanRead;
  yearly: boolean;
  currentPlanId?: string;
  onSelect: (plan: PlanRead) => void;
  loading?: boolean;
}

function fmt(cents: number, currency: string) {
  const locale = currency === "TRY" ? "tr-TR" : "en-US";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
  }).format(cents / 100);
}

const FEATURE_LABELS: { key: keyof PlanRead; label: string }[] = [
  { key: "pdf_export_enabled",             label: "PDF Export" },
  { key: "advanced_reporting_enabled",     label: "Gelişmiş Raporlama" },
  { key: "public_report_link_enabled",     label: "Herkese Açık Rapor Linki" },
  { key: "white_label_enabled",            label: "White Label Portal" },
  { key: "whatsapp_infrastructure_enabled",label: "WhatsApp Altyapısı" },
];

export function PlanCard({ plan, yearly, currentPlanId, onSelect, loading }: PlanCardProps) {
  const isCurrent    = plan.id === currentPlanId;
  const isPro        = plan.code === "pro_agency";
  const isEnterprise = plan.monthly_price_cents === 0;

  const priceMonthly =
    yearly && plan.yearly_price_cents
      ? plan.yearly_price_cents / 12
      : plan.monthly_price_cents;

  return (
    <div
      className={`relative flex flex-col rounded-2xl border p-5 transition-all ${
        isPro
          ? "border-accent/50 bg-surface shadow-[0_0_0_1px_var(--color-accent)/10,0_8px_32px_var(--color-accent)/8]"
          : "border-border bg-surface hover:border-border-hover hover:shadow-card-hover"
      }`}
    >
      {isPro && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10">
          <span
            className="flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold text-white"
            style={{ background: "var(--gradient-accent)" }}
          >
            <Zap className="w-3 h-3" />
            Popüler
          </span>
        </div>
      )}

      <div className="mb-4">
        <h3 className="text-sm font-bold text-text">{plan.name}</h3>
        {plan.description && (
          <p className="mt-0.5 text-xs text-text-muted">{plan.description}</p>
        )}
      </div>

      <div className="mb-4 pb-4 border-b border-border">
        {isEnterprise ? (
          <>
            <p className="text-2xl font-bold text-text">Özel Fiyat</p>
            <p className="mt-0.5 text-xs text-text-muted">Satış ekibimizle görüşün</p>
          </>
        ) : (
          <>
            <div className="flex items-end gap-1">
              <p className="text-2xl font-bold text-text">{fmt(priceMonthly, plan.currency)}</p>
              <span className="text-xs text-text-muted mb-1">/ay</span>
            </div>
            {yearly && plan.yearly_price_cents && (
              <p className="mt-0.5 text-xs text-success-text font-medium">
                Yıllık {fmt(plan.yearly_price_cents, plan.currency)}
              </p>
            )}
          </>
        )}
      </div>

      <ul className="flex-1 space-y-2 mb-5 text-sm">
        <li className="flex items-center gap-2 text-text">
          <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
          {plan.max_brands !== null ? `${plan.max_brands} marka` : "Sınırsız marka"}
        </li>
        <li className="flex items-center gap-2 text-text">
          <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
          {plan.max_users !== null ? `${plan.max_users} kullanıcı` : "Sınırsız kullanıcı"}
        </li>
        <li className="flex items-center gap-2 text-text">
          <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
          {plan.max_brief_templates !== null ? `${plan.max_brief_templates} şablon` : "Sınırsız şablon"}
        </li>
        {FEATURE_LABELS.map(({ key, label }) => {
          const enabled = plan[key] as boolean;
          return (
            <li key={key} className={`flex items-center gap-2 ${enabled ? "text-text" : "text-text-muted/50"}`}>
              {enabled
                ? <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
                : <Minus className="w-3.5 h-3.5 text-border flex-shrink-0" />}
              {label}
            </li>
          );
        })}
      </ul>

      <button
        onClick={() => onSelect(plan)}
        disabled={isCurrent || loading}
        className={`w-full rounded-xl py-2.5 text-sm font-semibold transition-all flex items-center justify-center gap-1.5 ${
          isCurrent
            ? "cursor-default bg-surface-2 text-text-muted border border-border"
            : isPro
              ? "text-white hover:opacity-90 disabled:opacity-60"
              : "bg-surface-2 border border-border text-text hover:bg-accent hover:text-white hover:border-transparent disabled:opacity-60"
        }`}
        style={isPro && !isCurrent ? { background: "var(--gradient-accent)" } : undefined}
      >
        {isCurrent
          ? "Mevcut Plan"
          : isEnterprise
            ? "Satışla İletişim"
            : "Planı Seç"}
        {!isCurrent && <ArrowRight className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}
