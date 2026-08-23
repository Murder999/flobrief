"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { planApi, type PlanRead } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { storePendingPlan } from "@/lib/workspace";
import {
  Check, Minus, ChevronDown, ArrowLeft, Zap,
  Building2, Sparkles, Shield, Users, FileText,
  BarChart3, Globe, MessageSquare, Star, ArrowRight,
  Loader2,
} from "lucide-react";
import { useLocale } from "@/context/locale-context";
import { LanguageSelector } from "@/components/i18n/language-selector";
import { PostPiloterLogo } from "@/components/brand/PostPiloterLogo";
import { usePaddlePricePreview } from "@/lib/billing/usePaddlePricePreview";
import { openCheckout } from "@/lib/billing/paddle";
import type { TranslationKey } from "@/messages";

const ES = [0.16, 1, 0.3, 1] as const;
const vUp = { hidden: { opacity: 0, y: 16 }, visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: ES } } };

/* ── helpers ─────────────────────────────────────────────────────────────── */

function fmt(cents: number, currency: string, intlLocale: string) {
  return new Intl.NumberFormat(intlLocale, { style: "currency", currency, minimumFractionDigits: 0 }).format(cents / 100);
}

/* ── Plan card ───────────────────────────────────────────────────────────── */

const PLAN_META: Record<string, { icon: React.ElementType; color: string; popular?: boolean }> = {
  brand_solo:     { icon: Users,     color: "text-success" },
  starter_agency: { icon: Building2, color: "text-info" },
  pro_agency:     { icon: Zap,       color: "text-accent", popular: true },
  agency_plus:    { icon: Sparkles,  color: "text-purple" },
  enterprise:     { icon: Shield,    color: "text-text-secondary" },
};

function PricingCard({
  plan, yearly, onSelect, highlighted,
}: {
  plan: PlanRead; yearly: boolean; onSelect: (p: PlanRead) => void; highlighted: boolean;
}) {
  const { intlLocale, t, locale } = useLocale();
  const meta = PLAN_META[plan.code] ?? { icon: Star, color: "text-text" };
  const Icon = meta.icon;
  const isEnterprise = plan.monthly_price_cents === 0;
  const period = yearly ? "yearly" : "monthly";

  const { price, loading: priceLoading, error: priceError } = usePaddlePricePreview(
    isEnterprise ? null : (plan.code as "brand_solo" | "starter_agency" | "pro_agency" | "agency_plus"),
    period
  );

  const handleCheckout = async () => {
    if (isEnterprise) {
      window.location.href = "mailto:sales@postpiloter.com?subject=Enterprise Plan";
      return;
    }
    if (priceError || !price) {
      return;
    }
    await onSelect(plan);
  };

  return (
    <div
      className={`relative flex h-full flex-col rounded-2xl border p-6 transition-all duration-200 ${
        highlighted
          ? "border-accent/50 bg-surface shadow-[0_0_0_1px_var(--color-accent)/10,0_8px_40px_var(--color-accent)/10] scale-[1.02]"
          : "border-border bg-surface hover:border-border-hover hover:shadow-card-hover"
      }`}
    >
      {meta.popular && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10">
          <span
            className="flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold text-white"
            style={{ background: "var(--gradient-accent)" }}
          >
            <Zap className="w-3 h-3" />
            {t("marketing.pricing.popular")}
          </span>
        </div>
      )}

      <div className="mb-5 min-h-[100px]">
        <div className={`w-9 h-9 rounded-xl bg-surface-2 flex items-center justify-center mb-3 ${meta.color}`}>
          <Icon className="w-4.5 h-4.5" style={{ width: "1.125rem", height: "1.125rem" }} />
        </div>
        <h3 className="text-base font-bold text-text line-clamp-1">{t((`marketing.pricing.plan.${plan.code}.name`) as TranslationKey)}</h3>
        <p className="mt-1 text-xs text-text-muted leading-relaxed line-clamp-2">{t((`marketing.pricing.plan.${plan.code}.description`) as TranslationKey)}</p>
      </div>

      <div className="mb-6 pb-6 border-b border-border">
        {isEnterprise ? (
          <>
            <p className="text-3xl font-bold text-text">{t("marketing.pricing.customPrice")}</p>
            <p className="mt-1 text-xs text-text-muted">{t("marketing.pricing.talkToSales")}</p>
          </>
        ) : priceError ? (
          <div className="flex flex-col items-center gap-2 text-center py-4">
            <div className="text-3xl font-bold text-text-muted">—</div>
            <p className="text-sm text-danger-text">{t("marketing.pricing.priceUnavailable")}</p>
            <p className="text-xs text-text-muted">Checkout devre dışı</p>
          </div>
        ) : priceLoading ? (
          <>
            <div className="flex items-end gap-1">
              <div className="text-3xl font-bold text-text animate-pulse">
                <span className="bg-surface-2 rounded w-24 h-10" />
              </div>
              <span className="text-sm text-text-muted mb-1">{t("marketing.pricing.perMonth")}</span>
            </div>
            <p className="mt-1 text-xs text-text-muted">{t("marketing.pricing.loadingPrice")}</p>
          </>
        ) : price ? (
          <>
            <div className="flex items-end gap-1">
              <p className="text-3xl font-bold text-text">{price.formattedTotal}</p>
              <span className="text-sm text-text-muted mb-1">{t("marketing.pricing.perMonth")}</span>
            </div>
            {yearly && plan.yearly_price_cents && (
              <p className="mt-1 text-xs text-success-text font-medium">
                {t("marketing.pricing.yearlySavings", { price: price.formattedTotal })}
              </p>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 text-center py-4">
            <div className="text-3xl font-bold text-text-muted">—</div>
            <p className="text-sm text-danger-text">{t("marketing.pricing.priceUnavailable")}</p>
          </div>
        )}
      </div>

      <ul className="flex-1 space-y-2.5 mb-6 text-sm">
        <li className="flex items-center gap-2.5 text-text">
          <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
          {plan.max_brands !== null ? t("marketing.pricing.limit.brands", { count: plan.max_brands }) : t("marketing.pricing.limit.unlimitedBrands")}
        </li>
        <li className="flex items-center gap-2.5 text-text">
          <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
          {plan.max_users !== null ? t("marketing.pricing.limit.users", { count: plan.max_users }) : t("marketing.pricing.limit.unlimitedUsers")}
        </li>
        <li className="flex items-center gap-2.5 text-text">
          <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
          {plan.max_brief_templates !== null ? t("marketing.pricing.limit.templates", { count: plan.max_brief_templates }) : t("marketing.pricing.limit.unlimitedTemplates")}
        </li>
        <li className="flex items-center gap-2.5 text-text">
          <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
          {plan.max_storage_gb !== null ? t("marketing.pricing.limit.storage", { count: plan.max_storage_gb }) : t("marketing.pricing.limit.unlimitedStorage")}
        </li>
        {(plan.pdf_export_enabled) && (
          <li className="flex items-center gap-2.5 text-text">
            <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
            {t("marketing.pricing.feature.pdf")}
          </li>
        )}
        {(plan.advanced_reporting_enabled) && (
          <li className="flex items-center gap-2.5 text-text">
            <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
            {t("marketing.pricing.feature.reporting")}
          </li>
        )}
        {(plan.white_label_enabled) && (
          <li className="flex items-center gap-2.5 text-text">
            <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
            {t("marketing.pricing.feature.whiteLabel")}
          </li>
        )}
        {(plan.whatsapp_infrastructure_enabled) && (
          <li className="flex items-center gap-2.5 text-text">
            <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
            {t("marketing.pricing.feature.whatsapp")}
          </li>
        )}
        {isEnterprise && (
          <li className="flex items-center gap-2.5 text-text">
            <Check className="w-3.5 h-3.5 text-success flex-shrink-0" />
            {t("marketing.pricing.feature.prioritySupport")}
          </li>
        )}
      </ul>

      <button
        onClick={handleCheckout}
        disabled={priceLoading && !isEnterprise}
        className={`mt-auto w-full rounded-xl py-2.5 text-sm font-semibold transition-all ${
          highlighted
            ? "text-white hover:opacity-90"
            : isEnterprise
              ? "bg-surface-2 border border-border text-text hover:bg-surface-3"
              : "bg-surface-2 border border-border text-text hover:bg-accent hover:text-white hover:border-accent/0"
        } ${priceLoading && !isEnterprise ? "opacity-50 cursor-wait" : ""}`}
        style={highlighted ? { background: "var(--gradient-accent)" } : undefined}
      >
        {isEnterprise
          ? t("marketing.pricing.contactSales")
          : priceLoading
          ? (
            <>
              <Loader2 className="inline w-3.5 h-3.5 ml-1.5 -mt-px animate-spin" />
              <span className="inline-block ml-1">{t("marketing.pricing.loading")}</span>
            </>
          )
          : t("marketing.pricing.selectPlan")}
        {!isEnterprise && !priceLoading && <ArrowRight className="inline w-3.5 h-3.5 ml-1.5 -mt-px" />}
      </button>
    </div>
  );
}

/* ── Feature comparison ──────────────────────────────────────────────────── */

type CellValue = string | boolean;
type Row = { labelKey: TranslationKey; icon: React.ElementType; values: CellValue[] };

const TABLE_PLANS = ["Solo", "Starter", "Pro", "Plus", "Enterprise"];
const TABLE_POPULAR_INDEX = TABLE_PLANS.indexOf("Pro");

const TABLE_ROWS: Row[] = [
  { labelKey: "marketing.pricing.row.brands",          icon: Building2,     values: ["1", "5", "15", "unlimited", "unlimited"] },
  { labelKey: "marketing.pricing.row.users",           icon: Users,         values: ["5", "10", "25", "unlimited", "unlimited"] },
  { labelKey: "marketing.pricing.row.templates",       icon: FileText,      values: ["10", "25", "unlimited", "unlimited", "unlimited"] },
  { labelKey: "marketing.pricing.row.storage",         icon: BarChart3,     values: ["10 GB", "25 GB", "50 GB", "200 GB", "unlimited"] },
  { labelKey: "marketing.pricing.feature.pdf",         icon: FileText,      values: [true, true, true, true, true] },
  { labelKey: "marketing.pricing.feature.reporting",   icon: BarChart3,     values: [false, true, true, true, true] },
  { labelKey: "marketing.pricing.feature.publicLink",  icon: Globe,         values: [false, true, true, true, true] },
  { labelKey: "marketing.pricing.feature.whiteLabel",  icon: Sparkles,      values: [false, false, false, true, true] },
  { labelKey: "marketing.pricing.feature.whatsapp",    icon: MessageSquare, values: [false, false, true, true, true] },
  { labelKey: "marketing.pricing.feature.prioritySupport", icon: Shield,    values: [false, false, false, false, true] },
];

function ComparisonTable() {
  const { t } = useLocale();
  return (
    <div className="overflow-x-auto rounded-2xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2">
            <th className="px-5 py-4 text-left text-xs font-semibold text-text-muted uppercase tracking-wider w-52">
              {t("marketing.pricing.feature")}
            </th>
            {TABLE_PLANS.map((name, i) => (
              <th
                key={name}
                className={`px-5 py-4 text-center text-xs font-bold uppercase tracking-wider ${
                  i === TABLE_POPULAR_INDEX ? "text-accent" : "text-text-muted"
                }`}
              >
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {TABLE_ROWS.map(({ labelKey, icon: Icon, values }) => (
            <tr key={labelKey} className="hover:bg-surface-2 transition-colors">
              <td className="px-5 py-3.5">
                <div className="flex items-center gap-2.5 text-text">
                  <Icon className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
                  {t(labelKey)}
                </div>
              </td>
              {values.map((val, i) => (
                <td key={i} className="px-5 py-3.5 text-center">
                  {typeof val === "boolean" ? (
                    val ? (
                      <Check className="w-4 h-4 text-success mx-auto" />
                    ) : (
                      <Minus className="w-4 h-4 text-border mx-auto" />
                    )
                  ) : (
                    <span className={`text-sm font-medium ${i === TABLE_POPULAR_INDEX ? "text-accent" : "text-text"}`}>
                      {val === "unlimited" ? t("marketing.pricing.unlimited") : val}
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── FAQ ─────────────────────────────────────────────────────────────────── */

const FAQS = [1, 2, 3, 4, 5] as const;

function FAQ() {
  const { t } = useLocale();
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-2">
      {FAQS.map((item, i) => (
        <div key={i} className="border border-border rounded-xl overflow-hidden bg-surface">
          <button
            className="w-full flex items-center justify-between px-5 py-4 text-left text-sm font-semibold text-text hover:bg-surface-2 transition-colors"
            onClick={() => setOpen(open === i ? null : i)}
          >
            {t((`marketing.pricing.faq.${item}.q`) as TranslationKey)}
            <ChevronDown
              className={`w-4 h-4 text-text-muted flex-shrink-0 ml-3 transition-transform duration-200 ${open === i ? "rotate-180" : ""}`}
            />
          </button>
          <AnimatePresence initial={false}>
            {open === i && (
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: "auto" }}
                exit={{ height: 0 }}
                transition={{ duration: 0.2, ease: ES }}
                className="overflow-hidden"
              >
                <p className="px-5 pb-4 text-sm text-text-muted leading-relaxed border-t border-border pt-3">
                  {t((`marketing.pricing.faq.${item}.a`) as TranslationKey)}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

const PLAN_ORDER = ["brand_solo", "starter_agency", "pro_agency", "agency_plus", "enterprise"];

export default function PricingPage() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const { user } = useAuth();
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [yearly, setYearly] = useState(false);

  useEffect(() => {
    planApi
      .list()
      .then((data) =>
        setPlans(
          data
            .filter((p) => PLAN_ORDER.includes(p.code))
            .sort((a, b) => PLAN_ORDER.indexOf(a.code) - PLAN_ORDER.indexOf(b.code))
        )
      )
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function handleSelect(plan: PlanRead) {
    if (plan.monthly_price_cents === 0) {
      window.location.href = "mailto:sales@postpiloter.com?subject=Enterprise Plan";
      return;
    }

    const planCode = plan.code as "brand_solo" | "starter_agency" | "pro_agency" | "agency_plus";
    const period = yearly ? "yearly" : "monthly";

    openCheckout({
      planCode,
      period,
      locale: locale as "tr" | "en",
      customerEmail: user?.email,
      yearly,
      planId: plan.id,
    });
  }

  return (
    <div className="min-h-screen bg-background">

      {/* Nav */}
      <nav className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="mx-auto max-w-6xl px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <PostPiloterLogo className="h-7 w-auto transition-transform group-hover:scale-[1.02]" priority />
          </Link>
          <div className="flex items-center gap-3">
            <LanguageSelector compact />
            <Link href="/" className="flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors">
              <ArrowLeft className="w-3.5 h-3.5" />
              {t("marketing.pricing.home")}
            </Link>
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-6 py-20">

        {/* Hero */}
        <motion.div
          className="text-center mb-14 relative"
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.08 } } }}
        >
          <div className="pointer-events-none absolute -top-20 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-accent/6 rounded-full blur-3xl" />

          <motion.div variants={vUp} className="relative">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-xs font-medium text-accent mb-5">
              <Zap className="w-3.5 h-3.5" />
              {t("marketing.pricing.eyebrow")}
            </span>
          </motion.div>

          <motion.h1
            variants={vUp}
            className="relative text-4xl sm:text-5xl font-bold text-text tracking-tight mb-4 leading-tight"
          >
            {t("marketing.pricing.title")}
          </motion.h1>

          <motion.p variants={vUp} className="relative text-base text-text-muted max-w-lg mx-auto mb-8 leading-relaxed">
            {t("marketing.pricing.description")}
          </motion.p>

          {/* Billing toggle */}
          <motion.div variants={vUp} className="relative inline-flex items-center gap-1 rounded-xl border border-border bg-surface p-1">
            <button
              onClick={() => setYearly(false)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                !yearly ? "bg-background shadow-sm text-text" : "text-text-muted hover:text-text"
              }`}
            >
              {t("marketing.pricing.monthly")}
            </button>
            <button
              onClick={() => setYearly(true)}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                yearly ? "bg-background shadow-sm text-text" : "text-text-muted hover:text-text"
              }`}
            >
              {t("marketing.pricing.yearly")}
              <span className="rounded-full bg-success/15 border border-success/20 px-2 py-0.5 text-[11px] font-semibold text-success-text">
                −%20
              </span>
            </button>
          </motion.div>
        </motion.div>

        {/* Plan cards */}
        {loading ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5 mb-20">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-[420px] animate-pulse rounded-2xl border border-border bg-surface" />
            ))}
          </div>
        ) : (
          <motion.div
            className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5 items-stretch mb-20"
            initial="hidden"
            animate="visible"
            variants={{ visible: { transition: { staggerChildren: 0.07, delayChildren: 0.15 } } }}
          >
            {plans.map((plan) => (
              <motion.div key={plan.id} variants={vUp} className="h-full">
                <PricingCard
                  plan={plan}
                  yearly={yearly}
                  highlighted={plan.code === "pro_agency"}
                  onSelect={handleSelect}
                />
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Comparison table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, ease: ES }}
          className="mb-20"
        >
          <div className="flex items-center gap-3 mb-6">
            <h2 className="text-xl font-bold text-text">{t("marketing.pricing.comparison")}</h2>
            <div className="flex-1 h-px bg-border" />
          </div>
          <ComparisonTable />
        </motion.div>

        {/* FAQ */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, ease: ES }}
          className="mb-20"
        >
          <div className="flex items-center gap-3 mb-6">
            <h2 className="text-xl font-bold text-text">{t("marketing.pricing.faqTitle")}</h2>
            <div className="flex-1 h-px bg-border" />
          </div>
          <div className="max-w-2xl">
            <FAQ />
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, ease: ES }}
          className="relative rounded-2xl border border-border bg-surface overflow-hidden p-10 text-center"
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-accent/4 via-transparent to-purple/3" />
          <div className="relative">
            <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
              <MessageSquare className="w-6 h-6 text-accent" />
            </div>
            <h2 className="text-2xl font-bold text-text mb-2">{t("marketing.pricing.ctaTitle")}</h2>
            <p className="text-text-muted mb-6 max-w-md mx-auto text-sm leading-relaxed">
              {t("marketing.pricing.ctaDescription")}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a
                href="mailto:sales@postpiloter.com"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90"
                style={{ background: "var(--gradient-accent)" }}
              >
                {t("marketing.pricing.contactSales")}
                <ArrowRight className="w-4 h-4" />
              </a>
              <Link
                href="/auth/register"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold text-text border border-border bg-background hover:border-border-hover hover:shadow-sm transition-all"
              >
                {t("marketing.actions.freeSignup")}
              </Link>
            </div>
            <p className="mt-4 text-xs text-text-muted">{t("marketing.pricing.trialNote")}</p>
          </div>
        </motion.div>
      </div>

      {/* Footer */}
      <div className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-text-muted">
          <span>© {new Date().getFullYear()} PostPiloter. {t("marketing.footer.rights")}</span>
          <div className="flex items-center gap-4">
            <Link href="/pricing" className="hover:text-text transition-colors">{t("marketing.pricing.nav")}</Link>
            <a href="mailto:sales@postpiloter.com" className="hover:text-text transition-colors">{t("marketing.pricing.contact")}</a>
            <Link href="/" className="hover:text-text transition-colors">{t("marketing.pricing.home")}</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
