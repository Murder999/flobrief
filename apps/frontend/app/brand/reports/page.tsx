"use client";

import { InfoTooltip } from "@/components/contextual-help/InfoTooltip";
import {
  ReportAnalytics,
  ReportAnalyticsSkeleton,
  ReportEmptyState,
  ReportErrorState,
  ReportListSkeleton,
  ReportPeriod,
  ReportStatusBadge,
  ReportTypeLabel,
  ReportsSectionHeading,
  formatReportGeneratedAt,
} from "@/components/reports/reporting";
import { Card } from "@/components/ui/card";
import { useLocale } from "@/context/locale-context";
import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, type BrandReportWithSnapshot, type ReportRead } from "@/lib/api-client";
import { ChevronRight, CircleHelp } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export default function BrandReportsPage() {
  const { accessToken } = useAuth();
  const { locale, t } = useLocale();
  const [reports, setReports] = useState<ReportRead[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedReport, setSelectedReport] = useState<BrandReportWithSnapshot | null>(null);
  const [listError, setListError] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(false);

  const loadList = useCallback(async () => {
    if (!accessToken) return;
    setListError(false);
    setReports(null);
    try {
      const data = await brandPortalApi.listReports(accessToken);
      const items = Array.isArray(data) ? data : [];
      setReports(items);
      setSelectedId((current) => current && items.some((item) => item.id === current) ? current : items[0]?.id ?? null);
    } catch {
      setListError(true);
      setReports([]);
      setSelectedId(null);
    }
  }, [accessToken]);

  const loadDetail = useCallback(async () => {
    if (!accessToken || !selectedId) {
      setSelectedReport(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(false);
    try {
      setSelectedReport(await brandPortalApi.getReport(selectedId, accessToken));
    } catch {
      setSelectedReport(null);
      setDetailError(true);
    } finally {
      setDetailLoading(false);
    }
  }, [accessToken, selectedId]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
      <header className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-text">{t("reports.brand.title")}</h1>
          <InfoTooltip text={t("reports.brand.help")} title={t("reports.brand.helpTitle")} placement="bottom" learnMoreHref="/brand/help?topic=report-view">
            <button
              type="button"
              aria-label={t("reports.brand.helpTitle")}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-hover hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
            >
              <CircleHelp className="h-4 w-4" aria-hidden="true" />
            </button>
          </InfoTooltip>
        </div>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">{t("reports.brand.subtitle")}</p>
      </header>

      {listError ? (
        <ReportErrorState
          title={t("reports.brand.loadErrorTitle")}
          description={t("reports.brand.loadErrorDescription")}
          onRetry={loadList}
        />
      ) : reports === null ? (
        <ReportListSkeleton rows={4} />
      ) : reports.length === 0 ? (
        <ReportEmptyState title={t("reports.brand.emptyTitle")} description={t("reports.brand.emptyDescription")} />
      ) : (
        <div className="grid min-w-0 grid-cols-1 gap-6 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <section className="min-w-0">
            <div className="mb-3">
              <ReportsSectionHeading title={t("reports.brand.listTitle")} description={t("reports.brand.listDescription")} />
            </div>
            <Card className="overflow-hidden shadow-none xl:sticky xl:top-5">
              <div className="divide-y divide-border">
                {reports.map((report) => {
                  const selected = report.id === selectedId;
                  return (
                    <button
                      key={report.id}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => setSelectedId(report.id)}
                      className={`grid w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/30 ${selected ? "bg-accent/5" : "hover:bg-hover/70"}`}
                    >
                      <div className="min-w-0">
                        <p className={`truncate text-sm font-semibold ${selected ? "text-accent" : "text-text"}`}>{report.title}</p>
                        <p className="mt-1 text-xs text-text-muted"><ReportTypeLabel type={report.report_type} /></p>
                        <p className="mt-1 text-xs text-text-muted"><ReportPeriod start={report.period_start} end={report.period_end} /></p>
                      </div>
                      <div className="flex flex-col items-end justify-between gap-3">
                        <ReportStatusBadge status={report.status} />
                        <ChevronRight className={`h-4 w-4 ${selected ? "text-accent" : "text-text-muted"}`} aria-hidden="true" />
                      </div>
                    </button>
                  );
                })}
              </div>
            </Card>
          </section>

          <section className="min-w-0" aria-live="polite">
            {detailError ? (
              <ReportErrorState
                title={t("reports.brand.detailErrorTitle")}
                description={t("reports.brand.detailErrorDescription")}
                onRetry={loadDetail}
              />
            ) : detailLoading || !selectedReport ? (
              <ReportAnalyticsSkeleton />
            ) : (
              <div className="space-y-5">
                <Card className="p-4 shadow-none sm:p-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <ReportStatusBadge status={selectedReport.status} />
                        <span className="text-xs font-medium text-text-muted"><ReportTypeLabel type={selectedReport.report_type} /></span>
                      </div>
                      <h2 className="mt-3 break-words text-xl font-semibold tracking-tight text-text">{selectedReport.title}</h2>
                      <p className="mt-2 text-xs text-text-muted">
                        {t("reports.common.period")}: <ReportPeriod start={selectedReport.period_start} end={selectedReport.period_end} />
                      </p>
                    </div>
                    {selectedReport.snapshot ? (
                      <p className="flex-shrink-0 text-xs text-text-muted tabular-nums">
                        {t("reports.common.updated")}: {formatReportGeneratedAt(selectedReport.snapshot.created_at, locale)}
                      </p>
                    ) : null}
                  </div>
                </Card>

                {selectedReport.snapshot ? (
                  <ReportAnalytics metrics={selectedReport.snapshot.metrics} audience="brand" />
                ) : (
                  <ReportEmptyState title={t("reports.detail.emptyTitle")} description={t("reports.detail.emptyDescription")} />
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
