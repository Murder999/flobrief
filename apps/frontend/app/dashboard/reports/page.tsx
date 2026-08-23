"use client";

import { InfoTooltip } from "@/components/contextual-help/InfoTooltip";
import {
  ReportEmptyState,
  ReportErrorState,
  ReportListSkeleton,
  ReportPeriod,
  ReportStatusBadge,
  ReportTypeLabel,
  ReportsSectionHeading,
} from "@/components/reports/reporting";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { useWorkspace } from "@/context/workspace-context";
import { useLocale } from "@/context/locale-context";
import { useAuth } from "@/hooks/useAuth";
import { agencyApi, reportApi, type BrandRead, type ReportRead, type ReportType } from "@/lib/api-client";
import { formatLocalizedDate } from "@/lib/i18n/format";
import { ArrowRight, CircleHelp, FileBarChart, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const LIMIT = 20;

export default function ReportsPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();
  const { locale, t } = useLocale();
  const agencyId = activeAgency?.id ?? null;

  const [items, setItems] = useState<ReportRead[]>([]);
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [offset, setOffset] = useState(0);
  const [brandId, setBrandId] = useState("");
  const [reportType, setReportType] = useState<"" | ReportType>("");

  const loadReports = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(false);
    try {
      const data = await reportApi.list(agencyId, accessToken, {
        brand_id: brandId || undefined,
        report_type: reportType || undefined,
        limit: LIMIT,
        offset,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, brandId, offset, reportType]);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi.listBrands(agencyId, accessToken).then(setBrands).catch(() => setBrands([]));
  }, [accessToken, agencyId]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !agencyId) setLoading(false);
  }, [agencyId, workspaceLoading, workspaceReady]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  function updateBrand(value: string) {
    setBrandId(value);
    setOffset(0);
  }

  function updateType(value: string) {
    setReportType(value as "" | ReportType);
    setOffset(0);
  }

  function clearFilters() {
    setBrandId("");
    setReportType("");
    setOffset(0);
  }

  const brandNames = new Map(brands.map((brand) => [brand.id, brand.name]));
  const hasFilters = Boolean(brandId || reportType);

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-text">{t("reports.agency.title")}</h1>
            <InfoTooltip text={t("reports.agency.help")} title={t("reports.agency.helpTitle")} placement="bottom">
              <button
                type="button"
                aria-label={t("reports.agency.helpTitle")}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-hover hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
              >
                <CircleHelp className="h-4 w-4" aria-hidden="true" />
              </button>
            </InfoTooltip>
          </div>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">{t("reports.agency.subtitle")}</p>
        </div>
        <Link href="/dashboard/reports/new" className="self-start">
          <Button type="button" size="md">
            <Plus className="h-4 w-4" aria-hidden="true" />
            {t("reports.agency.create")}
          </Button>
        </Link>
      </header>

      {!loading && !agencyId ? (
        <ReportEmptyState
          title={t("reports.agency.noWorkspaceTitle")}
          description={t("reports.agency.noWorkspaceDescription")}
          action={
            <Link href="/onboarding/create-agency">
              <Button type="button" size="sm">{t("reports.agency.createWorkspace")}</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-5">
          <Card className="p-4 shadow-none sm:p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <ReportsSectionHeading title={t("reports.agency.filters")} description={t("reports.agency.help")} />
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:w-[34rem]">
                <Select
                  id="report-brand-filter"
                  aria-label={t("reports.agency.filterBrand")}
                  label={t("reports.agency.filterBrand")}
                  value={brandId}
                  onChange={(event) => updateBrand(event.target.value)}
                  options={[
                    { value: "", label: t("reports.common.allBrands") },
                    ...brands.map((brand) => ({ value: brand.id, label: brand.name })),
                  ]}
                />
                <Select
                  id="report-type-filter"
                  aria-label={t("reports.agency.filterType")}
                  label={t("reports.agency.filterType")}
                  value={reportType}
                  onChange={(event) => updateType(event.target.value)}
                  options={[
                    { value: "", label: t("reports.common.allTypes") },
                    { value: "monthly_brand", label: t("reports.type.monthlyBrand") },
                    { value: "agency_overview", label: t("reports.type.agencyOverview") },
                    { value: "campaign_summary", label: t("reports.type.campaignSummary") },
                  ]}
                />
              </div>
            </div>
            {hasFilters ? (
              <button
                type="button"
                onClick={clearFilters}
                className="mt-3 text-xs font-medium text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
              >
                {t("reports.common.clearFilters")}
              </button>
            ) : null}
          </Card>

          <div className="flex items-end justify-between gap-4">
            <ReportsSectionHeading title={t("reports.agency.listTitle")} description={t("reports.agency.listDescription")} />
            {!loading && total > 0 ? (
              <span className="text-xs text-text-muted tabular-nums">{total}</span>
            ) : null}
          </div>

          {error ? (
            <ReportErrorState
              title={t("reports.agency.loadErrorTitle")}
              description={t("reports.agency.loadErrorDescription")}
              onRetry={loadReports}
            />
          ) : loading ? (
            <ReportListSkeleton />
          ) : items.length === 0 ? (
            <ReportEmptyState
              title={t(hasFilters ? "reports.agency.filteredEmptyTitle" : "reports.agency.emptyTitle")}
              description={t(hasFilters ? "reports.agency.filteredEmptyDescription" : "reports.agency.emptyDescription")}
              action={hasFilters ? (
                <Button type="button" variant="outline" size="sm" onClick={clearFilters}>
                  {t("reports.common.clearFilters")}
                </Button>
              ) : (
                <Link href="/dashboard/reports/new">
                  <Button type="button" size="sm">{t("reports.agency.create")}</Button>
                </Link>
              )}
            />
          ) : (
            <Card className="overflow-hidden shadow-none">
              <div className="hidden grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-5 border-b border-border bg-surface-2/60 px-5 py-2.5 text-[11px] font-medium uppercase tracking-wider text-text-muted md:grid">
                <span>{t("reports.agency.listTitle")}</span>
                <span>{t("reports.common.period")}</span>
                <span>{t("reports.common.created")}</span>
                <span className="sr-only">{t("reports.common.open")}</span>
              </div>
              <div className="divide-y divide-border">
                {items.map((report) => (
                  <Link
                    key={report.id}
                    href={`/dashboard/reports/${report.id}`}
                    className="group grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3 px-4 py-4 transition-colors hover:bg-hover/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/30 sm:px-5 md:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center md:gap-5"
                  >
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2 text-text-muted group-hover:text-accent">
                        <FileBarChart className="h-4 w-4" aria-hidden="true" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-text group-hover:text-accent">{report.title}</p>
                        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
                          <span><ReportTypeLabel type={report.report_type} /></span>
                          <span aria-hidden="true">·</span>
                          <span className="truncate">{report.brand_id ? brandNames.get(report.brand_id) ?? t("reports.common.notAvailable") : t("reports.common.allBrands")}</span>
                        </p>
                      </div>
                    </div>
                    <div className="justify-self-end md:order-none md:justify-self-start">
                      <ReportStatusBadge status={report.status} />
                    </div>
                    <p className="col-span-2 text-xs text-text-muted md:col-span-1">
                      <ReportPeriod start={report.period_start} end={report.period_end} />
                    </p>
                    <p className="hidden text-xs text-text-muted tabular-nums md:block">
                      {formatLocalizedDate(report.created_at, locale)}
                    </p>
                    <ArrowRight className="hidden h-4 w-4 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent md:block" aria-hidden="true" />
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {!loading && !error && total > LIMIT ? (
            <nav aria-label={t("reports.agency.listTitle")} className="flex flex-col items-center justify-between gap-3 border-t border-border pt-4 sm:flex-row">
              <Button type="button" variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - LIMIT))}>
                {t("reports.common.previous")}
              </Button>
              <span className="text-xs text-text-muted tabular-nums">
                {t("reports.common.results", { start: offset + 1, end: Math.min(offset + LIMIT, total), total })}
              </span>
              <Button type="button" variant="outline" size="sm" disabled={offset + LIMIT >= total} onClick={() => setOffset((value) => value + LIMIT)}>
                {t("reports.common.next")}
              </Button>
            </nav>
          ) : null}
        </div>
      )}
    </main>
  );
}
