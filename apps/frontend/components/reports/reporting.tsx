"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useLocale } from "@/context/locale-context";
import type { ReportMetrics, ReportStatus, ReportType } from "@/lib/api-client";
import { formatLocalizedDate, formatLocalizedDateOnly, formatLocalizedNumber } from "@/lib/i18n/format";
import type { TranslationKey } from "@/messages";
import { AlertCircle, BarChart3, FileBarChart, RefreshCw } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

const REPORT_TYPE_KEYS: Record<ReportType, TranslationKey> = {
  monthly_brand: "reports.type.monthlyBrand",
  agency_overview: "reports.type.agencyOverview",
  campaign_summary: "reports.type.campaignSummary",
};

const REPORT_STATUS_KEYS: Record<ReportStatus, TranslationKey> = {
  draft: "reports.status.draft",
  generated: "reports.status.generated",
  shared: "reports.status.shared",
  archived: "reports.status.archived",
};

const REPORT_STATUS_VARIANTS: Record<ReportStatus, "default" | "info" | "success"> = {
  draft: "default",
  generated: "info",
  shared: "success",
  archived: "default",
};

const CALENDAR_STATUS_KEYS: Record<string, TranslationKey> = {
  draft: "reports.calendar.draft",
  planned: "reports.calendar.planned",
  scheduled: "reports.calendar.scheduled",
  published: "reports.calendar.published",
  cancelled: "reports.calendar.cancelled",
};

export function ReportTypeLabel({ type }: { type: ReportType }) {
  const { t } = useLocale();
  return <>{t(REPORT_TYPE_KEYS[type])}</>;
}

export function ReportStatusBadge({ status }: { status: ReportStatus }) {
  const { t } = useLocale();
  return (
    <Badge variant={REPORT_STATUS_VARIANTS[status]} dot>
      {t(REPORT_STATUS_KEYS[status])}
    </Badge>
  );
}

export function ReportPeriod({ start, end }: { start: string; end: string }) {
  const { locale } = useLocale();
  return (
    <span className="tabular-nums">
      {formatLocalizedDateOnly(start, locale)} - {formatLocalizedDateOnly(end, locale)}
    </span>
  );
}

export function ReportEmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Card className="flex min-h-64 flex-col items-center justify-center px-5 py-12 text-center shadow-none">
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface-2 text-text-muted">
        <FileBarChart className="h-5 w-5" aria-hidden="true" />
      </div>
      <h2 className="text-sm font-semibold text-text">{title}</h2>
      <p className="mt-1.5 max-w-md text-sm leading-6 text-text-muted">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </Card>
  );
}

export function ReportErrorState({
  title,
  description,
  onRetry,
}: {
  title: string;
  description: string;
  onRetry: () => void;
}) {
  const { t } = useLocale();
  return (
    <Card role="alert" className="flex min-h-52 flex-col items-center justify-center px-5 py-10 text-center shadow-none">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertCircle className="h-5 w-5" aria-hidden="true" />
      </div>
      <h2 className="text-sm font-semibold text-text">{title}</h2>
      <p className="mt-1.5 max-w-md text-sm leading-6 text-text-muted">{description}</p>
      <Button type="button" variant="outline" size="sm" className="mt-5" onClick={onRetry}>
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
        {t("reports.common.retry")}
      </Button>
    </Card>
  );
}

function ReportKpi({ label, value, description }: { label: string; value: string; description: string }) {
  return (
    <div className="min-w-0 border-t-2 border-t-accent/50 bg-surface px-4 py-4 sm:px-5">
      <p className="text-xs font-medium text-text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-text tabular-nums">{value}</p>
      <p className="mt-1.5 text-xs leading-5 text-text-muted">{description}</p>
    </div>
  );
}

function ReportSection({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card className="overflow-hidden shadow-none">
      <div className="border-b border-border px-4 py-4 sm:px-5">
        <h2 className="text-sm font-semibold text-text">{title}</h2>
        <p className="mt-1 text-xs leading-5 text-text-muted">{description}</p>
      </div>
      <div className="px-4 py-4 sm:px-5">{children}</div>
    </Card>
  );
}

function DistributionList({
  values,
  labelFor,
}: {
  values: Record<string, number>;
  labelFor: (value: string) => string;
}) {
  const { locale, t } = useLocale();
  const rows = Object.entries(values).sort(([, left], [, right]) => right - left);
  const total = rows.reduce((sum, [, value]) => sum + value, 0);

  if (rows.length === 0 || total === 0) {
    return <p className="py-5 text-center text-sm text-text-muted">{t("reports.common.noData")}</p>;
  }

  return (
    <div className="space-y-3">
      {rows.map(([key, value]) => {
        const percentage = Math.round((value / total) * 100);
        const label = labelFor(key);
        return (
          <div key={key}>
            <div className="mb-1.5 flex items-center justify-between gap-4 text-xs">
              <span className="min-w-0 truncate font-medium text-text">{label}</span>
              <span className="flex-shrink-0 text-text-muted tabular-nums">
                {formatLocalizedNumber(value, locale)} · {percentage}%
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={`${label}: ${value} (${percentage}%)`}
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={value}
              className="h-1.5 overflow-hidden rounded-full bg-surface-2"
            >
              <div className="h-full rounded-full bg-accent" style={{ width: `${percentage}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function valueOrZero(value: number | undefined): number {
  return typeof value === "number" ? value : 0;
}

export function ReportAnalytics({
  metrics,
  audience,
}: {
  metrics: ReportMetrics;
  audience: "agency" | "brand";
}) {
  const { locale, t } = useLocale();
  const created = valueOrZero(metrics.created_briefs_count);
  const approved = valueOrZero(metrics.approved_briefs_count);
  const pending = valueOrZero(metrics.pending_approvals_count);
  const revisions = valueOrZero(metrics.revision_requested_count);
  const hasPeriodScopedContent = metrics.scope_version === 2;
  const published = hasPeriodScopedContent ? valueOrZero(metrics.published_calendar_items_count) : null;
  const planned = hasPeriodScopedContent ? valueOrZero(metrics.planned_calendar_items_count) : null;
  const approvalHours = metrics.scope_version === 2 ? metrics.average_approval_time_hours : null;
  const calendarStatuses = hasPeriodScopedContent ? metrics.calendar_status_distribution ?? {} : {};
  const platforms = hasPeriodScopedContent ? metrics.platform_distribution ?? {} : {};
  const revisedBriefs = metrics.most_revised_briefs ?? [];

  const kpis = audience === "agency"
    ? [
        ["reports.metrics.createdBriefs", created, "reports.metrics.createdBriefsHelp"],
        ["reports.metrics.approvedBriefs", approved, "reports.metrics.approvedBriefsHelp"],
        ["reports.metrics.revisions", revisions, "reports.metrics.revisionsHelp"],
        ["reports.metrics.published", published, "reports.metrics.publishedHelp"],
      ] as const
    : [
        ["reports.metrics.createdBriefs", created, "reports.metrics.createdBriefsHelp"],
        ["reports.metrics.pendingApprovals", pending, "reports.metrics.pendingApprovalsHelp"],
        ["reports.metrics.revisions", revisions, "reports.metrics.revisionsHelp"],
        ["reports.metrics.approvedBriefs", approved, "reports.metrics.approvedBriefsHelp"],
      ] as const;

  return (
    <div className="space-y-5">
      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
        <div className="grid grid-cols-2 divide-x divide-y divide-border sm:grid-cols-4 sm:divide-y-0">
          {kpis.map(([label, value, description]) => (
            <ReportKpi
              key={label}
              label={t(label)}
              value={typeof value === "number" ? formatLocalizedNumber(value, locale) : t("reports.common.notAvailable")}
              description={t(description)}
            />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <ReportSection
          title={t("reports.section.workflow")}
          description={t(audience === "agency" ? "reports.section.workflowAgencyDescription" : "reports.section.workflowBrandDescription")}
        >
          <dl className="divide-y divide-border">
            <div className="flex items-start justify-between gap-4 py-3 first:pt-0">
              <div>
                <dt className="text-sm text-text">{t("reports.metrics.pendingApprovals")}</dt>
                <dd className="mt-0.5 text-xs leading-5 text-text-muted">{t("reports.metrics.pendingApprovalsHelp")}</dd>
              </div>
              <dd className="text-sm font-semibold text-text tabular-nums">{formatLocalizedNumber(pending, locale)}</dd>
            </div>
            <div className="flex items-start justify-between gap-4 py-3 last:pb-0">
              <div>
                <dt className="text-sm text-text">{t("reports.metrics.averageApproval")}</dt>
                <dd className="mt-0.5 text-xs leading-5 text-text-muted">{t("reports.metrics.averageApprovalHelp")}</dd>
              </div>
              <dd className="flex-shrink-0 text-sm font-semibold text-text tabular-nums">
                {typeof approvalHours === "number"
                  ? t("reports.common.hours", { value: formatLocalizedNumber(approvalHours, locale, { maximumFractionDigits: 1 }) })
                  : t("reports.common.notAvailable")}
              </dd>
            </div>
          </dl>
        </ReportSection>

        <ReportSection
          title={t("reports.section.content")}
          description={t("reports.section.contentDescription")}
        >
          <div className="mb-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-surface-2 px-3 py-3">
              <p className="text-xs text-text-muted">{t("reports.metrics.planned")}</p>
              <p className="mt-1 text-lg font-semibold text-text tabular-nums">{typeof planned === "number" ? formatLocalizedNumber(planned, locale) : t("reports.common.notAvailable")}</p>
            </div>
            <div className="rounded-lg bg-surface-2 px-3 py-3">
              <p className="text-xs text-text-muted">{t("reports.metrics.published")}</p>
              <p className="mt-1 text-lg font-semibold text-text tabular-nums">{typeof published === "number" ? formatLocalizedNumber(published, locale) : t("reports.common.notAvailable")}</p>
            </div>
          </div>
          <DistributionList
            values={calendarStatuses}
            labelFor={(status) => CALENDAR_STATUS_KEYS[status] ? t(CALENDAR_STATUS_KEYS[status]) : status.replaceAll("_", " ")}
          />
        </ReportSection>

        <ReportSection
          title={t("reports.section.channels")}
          description={t("reports.section.channelsDescription")}
        >
          <DistributionList values={platforms} labelFor={(platform) => platform.replaceAll("_", " ")} />
        </ReportSection>

        <ReportSection
          title={t("reports.section.revisions")}
          description={t("reports.section.revisionsDescription")}
        >
          {revisedBriefs.length === 0 ? (
            <p className="py-5 text-center text-sm text-text-muted">{t("reports.section.noRevisions")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {revisedBriefs.slice(0, 5).map((brief) => (
                <li key={brief.brief_id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <Link
                    href={`${audience === "agency" ? "/dashboard" : "/brand"}/briefs/${brief.brief_id}`}
                    className="min-w-0 truncate text-sm font-medium text-text hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
                  >
                    {brief.brief_title ?? `#${brief.brief_id.slice(0, 8)}`}
                  </Link>
                  <span className="flex-shrink-0 text-xs font-medium text-text-muted tabular-nums">
                    {t("reports.revisions.count", { count: formatLocalizedNumber(brief.revision_count, locale) })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </ReportSection>
      </div>
    </div>
  );
}

export function ReportAnalyticsSkeleton() {
  const { t } = useLocale();
  return (
    <div aria-busy="true" aria-label={t("reports.common.loading")} className="space-y-5">
      <div aria-hidden="true" className="animate-pulse overflow-hidden rounded-xl border border-border bg-surface">
        <div className="grid grid-cols-2 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-32 border-b border-r border-border p-5 sm:border-b-0">
              <div className="h-3 w-24 rounded bg-surface-2" />
              <div className="mt-4 h-7 w-14 rounded bg-surface-2" />
              <div className="mt-3 h-3 w-full rounded bg-surface-2" />
            </div>
          ))}
        </div>
      </div>
      <div aria-hidden="true" className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-56 animate-pulse rounded-xl border border-border bg-surface p-5">
            <div className="h-4 w-36 rounded bg-surface-2" />
            <div className="mt-3 h-3 w-4/5 rounded bg-surface-2" />
            <div className="mt-8 h-24 rounded-lg bg-surface-2" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ReportListSkeleton({ rows = 5 }: { rows?: number }) {
  const { t } = useLocale();
  return (
    <Card aria-busy="true" aria-label={t("reports.common.loading")} className="overflow-hidden shadow-none">
      <div aria-hidden="true" className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="flex animate-pulse items-center gap-4 px-4 py-4 sm:px-5">
            <div className="h-9 w-9 flex-shrink-0 rounded-lg bg-surface-2" />
            <div className="min-w-0 flex-1">
              <div className="h-3.5 w-2/5 rounded bg-surface-2" />
              <div className="mt-2 h-3 w-3/5 rounded bg-surface-2" />
            </div>
            <div className="hidden h-5 w-20 rounded-full bg-surface-2 sm:block" />
          </div>
        ))}
      </div>
    </Card>
  );
}

export function ReportsSectionHeading({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
        <BarChart3 className="h-4 w-4" aria-hidden="true" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-text">{title}</h2>
        <p className="mt-0.5 text-xs leading-5 text-text-muted">{description}</p>
      </div>
    </div>
  );
}

export function formatReportGeneratedAt(value: string, locale: string): string {
  return formatLocalizedDate(value, locale, { dateStyle: "medium", timeStyle: "short" });
}
