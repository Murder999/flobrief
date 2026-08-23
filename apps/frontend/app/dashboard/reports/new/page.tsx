"use client";

import { ReportsSectionHeading } from "@/components/reports/reporting";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useLocale } from "@/context/locale-context";
import { useWorkspace } from "@/context/workspace-context";
import { useAuth } from "@/hooks/useAuth";
import { agencyApi, reportApi, type BrandRead, type ReportType } from "@/lib/api-client";
import type { TranslationKey } from "@/messages";
import { ArrowLeft, Check, Database, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const REPORT_TYPES: Array<{
  value: ReportType;
  label: TranslationKey;
  description: TranslationKey;
}> = [
  { value: "monthly_brand", label: "reports.type.monthlyBrand", description: "reports.new.type.monthlyDescription" },
  { value: "agency_overview", label: "reports.type.agencyOverview", description: "reports.new.type.agencyDescription" },
  { value: "campaign_summary", label: "reports.type.campaignSummary", description: "reports.new.type.campaignDescription" },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function firstOfMonth(): string {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function NewReportPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const { t } = useLocale();
  const agencyId = activeAgency?.id ?? null;
  const router = useRouter();

  const [reportType, setReportType] = useState<ReportType>("monthly_brand");
  const [periodStart, setPeriodStart] = useState(firstOfMonth());
  const [periodEnd, setPeriodEnd] = useState(today());
  const [title, setTitle] = useState("");
  const [brandId, setBrandId] = useState("");
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [brandsLoading, setBrandsLoading] = useState(true);
  const [brandsError, setBrandsError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadBrands = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setBrandsLoading(true);
    setBrandsError(false);
    try {
      setBrands(await agencyApi.listBrands(agencyId, accessToken));
    } catch {
      setBrands([]);
      setBrandsError(true);
    } finally {
      setBrandsLoading(false);
    }
  }, [accessToken, agencyId]);

  useEffect(() => {
    loadBrands();
  }, [loadBrands]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!accessToken || !agencyId) return;
    if (!title.trim()) {
      setError(t("reports.new.titleRequired"));
      return;
    }
    if (periodStart > periodEnd) {
      setError(t("reports.new.invalidPeriod"));
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const report = await reportApi.create(
        {
          report_type: reportType,
          period_start: periodStart,
          period_end: periodEnd,
          title: title.trim(),
          brand_id: brandId || null,
        },
        agencyId,
        accessToken
      );
      router.push(`/dashboard/reports/${report.id}`);
    } catch {
      setError(t("reports.new.createError"));
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
      <header className="mb-6">
        <button
          type="button"
          onClick={() => router.push("/dashboard/reports")}
          className="mb-4 inline-flex min-h-9 items-center gap-2 rounded-lg text-sm text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {t("reports.new.back")}
        </button>
        <h1 className="text-2xl font-semibold tracking-tight text-text">{t("reports.new.title")}</h1>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">{t("reports.new.subtitle")}</p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-5">
        <Card className="p-4 shadow-none sm:p-6">
          <ReportsSectionHeading title={t("reports.new.scopeTitle")} description={t("reports.new.scopeDescription")} />

          <fieldset className="mt-6">
            <legend className="text-xs font-medium tracking-wide text-text-muted">{t("reports.new.typeLabel")}</legend>
            <div className="mt-2 grid grid-cols-1 gap-2">
              {REPORT_TYPES.map((type) => {
                const selected = reportType === type.value;
                return (
                  <label
                    key={type.value}
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3.5 transition-colors ${selected ? "border-accent/60 bg-accent/5" : "border-border bg-surface hover:border-border-hover"}`}
                  >
                    <input
                      type="radio"
                      name="reportType"
                      value={type.value}
                      checked={selected}
                      onChange={() => setReportType(type.value)}
                      className="sr-only"
                    />
                    <span className={`mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border ${selected ? "border-accent bg-accent text-white" : "border-border bg-surface-2"}`}>
                      {selected ? <Check className="h-3 w-3" aria-hidden="true" /> : null}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-text">{t(type.label)}</span>
                      <span className="mt-0.5 block text-xs leading-5 text-text-muted">{t(type.description)}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              type="date"
              label={t("reports.new.startDate")}
              value={periodStart}
              onChange={(event) => setPeriodStart(event.target.value)}
              required
            />
            <Input
              type="date"
              label={t("reports.new.endDate")}
              value={periodEnd}
              onChange={(event) => setPeriodEnd(event.target.value)}
              required
            />
          </div>

          <div className="mt-4">
            <Select
              id="report-brand-scope"
              label={t("reports.new.brandLabel")}
              aria-label={t("reports.new.brandLabel")}
              value={brandId}
              onChange={(event) => setBrandId(event.target.value)}
              disabled={brandsLoading || brandsError}
              options={[
                { value: "", label: brandsLoading ? `${t("reports.common.allBrands")}...` : t("reports.common.allBrands") },
                ...brands.map((brand) => ({ value: brand.id, label: brand.name })),
              ]}
            />
            <p className="mt-1.5 text-xs leading-5 text-text-muted">{t("reports.new.brandHint")}</p>
            {brandsError ? (
              <div role="alert" className="mt-2 flex flex-wrap items-center gap-2 text-xs text-danger">
                <span>{t("reports.new.brandsError")}</span>
                <button type="button" onClick={loadBrands} className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
                  <RefreshCw className="h-3 w-3" aria-hidden="true" />
                  {t("reports.new.retryBrands")}
                </button>
              </div>
            ) : null}
          </div>

          <div className="mt-4">
            <Input
              type="text"
              label={t("reports.new.titleLabel")}
              placeholder={t("reports.new.titlePlaceholder")}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={500}
              required
            />
          </div>
        </Card>

        <Card className="flex items-start gap-3 p-4 shadow-none sm:p-5">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
            <Database className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-text">{t("reports.new.includedTitle")}</h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">{t("reports.new.includedDescription")}</p>
          </div>
        </Card>

        {error ? (
          <div role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        ) : null}

        <div className="flex flex-col-reverse gap-3 border-t border-border pt-5 sm:flex-row sm:justify-end">
          <Button type="button" variant="ghost" onClick={() => router.push("/dashboard/reports")}>
            {t("reports.new.cancel")}
          </Button>
          <Button type="submit" isLoading={submitting} disabled={!agencyId}>
            {submitting ? t("reports.new.submitting") : t("reports.new.submit")}
          </Button>
        </div>
      </form>
    </main>
  );
}
