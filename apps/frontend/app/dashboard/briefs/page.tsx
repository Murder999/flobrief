"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  dashboardApi,
  type BriefCenterData, type AttentionItem, type BrandCardItem,
} from "@/lib/api-client";
import { BriefStatusBadge, BriefPriorityBadge } from "@/components/briefs/brief-status-badge";
import { cn } from "@/lib/utils";
import {
  Plus, AlertTriangle, RefreshCw, FileText, Building2, Calendar,
  Clock, ChevronRight, CheckCircle2, Inbox, Zap, Eye, ExternalLink,
  TrendingUp, ArrowRight, Layers,
} from "lucide-react";
import { useLocale } from "@/context/locale-context";
import { formatLocalizedDate, formatLocalizedDateTime } from "@/lib/i18n/format";
import type { TranslationKey } from "@/messages";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const ATTENTION_TABS = [
  { value: "",                   labelKey: "briefs.filter.all" as TranslationKey },
  { value: "urgent",             labelKey: "briefs.priority.urgent" as TranslationKey },
  { value: "overdue",            labelKey: "briefs.stats.overdue" as TranslationKey },
  { value: "revision_requested", labelKey: "briefs.center.filter.revision" as TranslationKey },
  { value: "new_request",        labelKey: "briefs.center.filter.new" as TranslationKey },
];

// ── Skeleton components ───────────────────────────────────────────────────────

function KPICardSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-2xl p-5 shadow-card">
      <div className="h-3 shimmer rounded-lg w-20 mb-4" />
      <div className="h-7 shimmer rounded-lg w-12 mb-1" />
      <div className="h-2.5 shimmer rounded-lg w-28" />
    </div>
  );
}

function AttentionItemSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 bg-surface border border-border rounded-xl">
      <div className="w-1 h-10 shimmer rounded-full flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3.5 shimmer rounded-lg w-1/2" />
        <div className="flex gap-2">
          <div className="h-5 shimmer rounded-full w-16" />
          <div className="h-5 shimmer rounded-full w-20" />
        </div>
      </div>
      <div className="h-8 shimmer rounded-lg w-20" />
    </div>
  );
}

function BrandCardSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-2xl p-6 shadow-card">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 shimmer rounded-xl" />
        <div className="flex-1 space-y-1.5">
          <div className="h-4 shimmer rounded-lg w-24" />
          <div className="h-3 shimmer rounded-lg w-16" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 mb-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-10 shimmer rounded-lg" />
        ))}
      </div>
      <div className="flex gap-2">
        <div className="h-8 shimmer rounded-lg flex-1" />
        <div className="h-8 shimmer rounded-lg w-20" />
      </div>
    </div>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────────────

interface KPICardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  variant?: "default" | "danger" | "warning" | "info" | "success";
  subtitle?: string;
}

function KPICard({ label, value, icon, variant = "default", subtitle }: KPICardProps) {
  const variantCls = {
    default: "bg-surface border-border",
    danger:  "bg-danger-subtle border-danger-border",
    warning: "bg-warning-subtle border-warning-border",
    info:    "bg-info-subtle border-info-border",
    success: "bg-success-subtle border-success-border",
  }[variant];

  const valueCls = {
    default: "text-text",
    danger:  "text-danger-text",
    warning: "text-warning-text",
    info:    "text-info-text",
    success: "text-success-text",
  }[variant];

  const iconCls = {
    default: "bg-surface-2 text-text-muted",
    danger:  "bg-danger-subtle text-danger-text",
    warning: "bg-warning-subtle text-warning-text",
    info:    "bg-info-subtle text-info-text",
    success: "bg-success-subtle text-success-text",
  }[variant];

  return (
    <div className={cn("rounded-2xl border p-5 shadow-card", variantCls)}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-medium text-text-muted uppercase tracking-wider">{label}</span>
        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", iconCls)}>
          {icon}
        </div>
      </div>
      <div className={cn("text-2xl font-bold tabular-nums mb-0.5", valueCls)}>{value}</div>
      {subtitle && <p className="text-xs text-text-muted">{subtitle}</p>}
    </div>
  );
}

// ── Attention Reason badge ────────────────────────────────────────────────────

function AttentionReasonBadge({ reason }: { reason: string }) {
  const { t } = useLocale();
  const map: Record<string, { labelKey: TranslationKey; cls: string }> = {
    overdue:            { labelKey: "briefs.center.reason.overdue", cls: "status-danger" },
    revision_requested: { labelKey: "briefs.status.revisionRequested", cls: "status-warning" },
    urgent:             { labelKey: "briefs.priority.urgent", cls: "status-danger" },
    new_request:        { labelKey: "briefs.center.reason.new", cls: "status-info" },
  };
  const cfg = map[reason];
  return <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium", cfg?.cls ?? "status-default")}>{cfg ? t(cfg.labelKey) : reason}</span>;
}

// ── Attention Item Row ────────────────────────────────────────────────────────

function AttentionItemRow({ item }: { item: AttentionItem }) {
  const { locale, t } = useLocale();
  const leftBorderCls = {
    overdue:            "bg-danger",
    revision_requested: "bg-warning",
    urgent:             "bg-danger",
    new_request:        "bg-info",
  }[item.attention_reason] ?? "bg-border";

  return (
    <Link
      href={`/dashboard/briefs/${item.id}`}
      className="group flex items-center gap-4 p-4 bg-surface border border-border rounded-xl hover:border-border-hover hover:shadow-card-hover transition-all"
    >
      <div className={cn("w-1 h-10 rounded-full flex-shrink-0", leftBorderCls)} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="font-medium text-sm text-text truncate group-hover:text-accent transition-colors">
            {item.title}
          </span>
          <AttentionReasonBadge reason={item.attention_reason} />
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {item.brand_name && (
            <span className="text-xs text-text-muted flex items-center gap-1">
              <Building2 className="w-3 h-3" />
              {item.brand_name}
            </span>
          )}
          <BriefStatusBadge status={item.status as never} />
          <BriefPriorityBadge priority={item.priority as never} />
          {item.deadline && (
            <span className={cn(
              "text-xs flex items-center gap-1",
              item.days_overdue ? "text-danger-text font-medium" : "text-text-muted"
            )}>
              <Clock className="w-3 h-3" />
              {item.days_overdue
                ? t("briefs.center.daysOverdue", { count: item.days_overdue })
                : formatLocalizedDate(item.deadline, locale, { day: "numeric", month: "short" })}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="hidden sm:inline-flex items-center gap-1 px-3 py-1.5 bg-surface-2 border border-border text-xs font-medium text-text-secondary rounded-lg group-hover:bg-accent group-hover:text-white group-hover:border-accent transition-all">
          {t("briefs.center.openWork")}
          <ChevronRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
        </span>
        <ExternalLink className="w-4 h-4 text-text-muted sm:hidden" />
      </div>
    </Link>
  );
}

// ── Brand Logo ────────────────────────────────────────────────────────────────

function BrandLogo({ brand }: { brand: BrandCardItem }) {
  if (brand.logo_url) {
    return (
      <img
        src={`${API_BASE}${brand.logo_url}`}
        alt={brand.name}
        className="w-10 h-10 rounded-xl object-contain bg-surface-2 border border-border p-0.5"
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
    );
  }
  return (
    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent/20 to-accent/10 border border-accent/20 flex items-center justify-center flex-shrink-0">
      <span className="text-sm font-bold text-accent">
        {brand.name.charAt(0).toUpperCase()}
      </span>
    </div>
  );
}

// ── Brand Card ────────────────────────────────────────────────────────────────

function BrandCard({ brand }: { brand: BrandCardItem }) {
  const { locale, t } = useLocale();
  const router = useRouter();
  const hasIssues = brand.overdue_count > 0 || brand.revision_requested_count > 0;

  return (
    <motion.div
      layout
      className={cn(
        "group bg-surface border rounded-2xl p-6 shadow-card transition-all duration-200 hover:shadow-card-hover hover:-translate-y-0.5 flex flex-col",
        hasIssues ? "border-warning-border" : "border-border hover:border-border-hover"
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-5">
        <BrandLogo brand={brand} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-text text-sm truncate">{brand.name}</h3>
            <span className={cn(
              "text-[10px] font-semibold px-1.5 py-0.5 rounded-full",
              brand.status === "active"
                ? "bg-success-subtle text-success-text"
                : "bg-surface-2 text-text-muted"
            )}>
              {brand.status === "active" ? t("briefs.center.active") : brand.status}
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            {brand.has_brand_dna ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-success-text bg-success-subtle px-1.5 py-0.5 rounded-full">
                <CheckCircle2 className="w-2.5 h-2.5" />
                {t("briefs.center.dnaReady")}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-text-muted bg-surface-2 px-1.5 py-0.5 rounded-full">
                {t("briefs.center.dnaMissing")}
              </span>
            )}
            {hasIssues && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-warning-text bg-warning-subtle px-1.5 py-0.5 rounded-full">
                <AlertTriangle className="w-2.5 h-2.5" />
                {t("briefs.center.attention")}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-2 mb-5">
        <div className="bg-surface-2 rounded-xl p-3 border border-border">
          <div className="text-lg font-bold text-text tabular-nums">{brand.active_brief_count}</div>
          <div className="text-[10px] text-text-muted mt-0.5">{t("briefs.center.activeBriefs")}</div>
        </div>
        <div className={cn(
          "rounded-xl p-3 border",
          brand.overdue_count > 0
            ? "bg-danger-subtle border-danger-border"
            : "bg-surface-2 border-border"
        )}>
          <div className={cn(
            "text-lg font-bold tabular-nums",
            brand.overdue_count > 0 ? "text-danger-text" : "text-text"
          )}>{brand.overdue_count}</div>
          <div className="text-[10px] text-text-muted mt-0.5">{t("briefs.stats.overdue")}</div>
        </div>
        <div className={cn(
          "rounded-xl p-3 border",
          brand.revision_requested_count > 0
            ? "bg-warning-subtle border-warning-border"
            : "bg-surface-2 border-border"
        )}>
          <div className={cn(
            "text-lg font-bold tabular-nums",
            brand.revision_requested_count > 0 ? "text-warning-text" : "text-text"
          )}>{brand.revision_requested_count}</div>
          <div className="text-[10px] text-text-muted mt-0.5">{t("briefs.stats.revision")}</div>
        </div>
        <div className="bg-surface-2 rounded-xl p-3 border border-border">
          <div className="text-lg font-bold text-text tabular-nums">{brand.this_week_calendar_count}</div>
          <div className="text-[10px] text-text-muted mt-0.5">{t("briefs.center.thisWeek")}</div>
        </div>
      </div>

      {/* Last activity */}
      {brand.last_activity_at && (
        <p className="text-xs text-text-muted mb-4">
          {t("briefs.center.lastActivity", { date: formatLocalizedDateTime(brand.last_activity_at, locale) })}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-auto">
        <button
          onClick={() => router.push(`/dashboard/briefs/brand/${brand.id}`)}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-gradient-accent text-white rounded-xl text-xs font-semibold hover:opacity-90 transition-all hover:shadow-glow-sm"
        >
          <Layers className="w-3.5 h-3.5" />
          {t("briefs.center.workflow")}
        </button>
        <Link
          href={`/dashboard/briefs/new?brand_id=${brand.id}`}
          className="flex items-center justify-center gap-1 px-3 py-2 bg-surface-2 border border-border rounded-xl text-xs font-medium text-text-secondary hover:bg-surface hover:border-border-hover transition-all"
          title={t("briefs.center.newBrief")}
        >
          <Plus className="w-3.5 h-3.5" />
        </Link>
        <Link
          href={`/dashboard/calendar?brand_id=${brand.id}`}
          className="flex items-center justify-center gap-1 px-3 py-2 bg-surface-2 border border-border rounded-xl text-xs font-medium text-text-secondary hover:bg-surface hover:border-border-hover transition-all"
          title={t("briefs.center.viewCalendar")}
        >
          <Calendar className="w-3.5 h-3.5" />
        </Link>
      </div>
    </motion.div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyBrands() {
  const { t } = useLocale();
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 bg-surface-2 border border-border rounded-2xl flex items-center justify-center mb-5 shadow-xs">
        <Building2 className="w-7 h-7 text-text-muted" />
      </div>
      <h3 className="text-sm font-semibold text-text mb-2">{t("briefs.center.noBrands")}</h3>
      <p className="text-sm text-text-secondary mb-6 max-w-xs leading-relaxed">
        {t("briefs.center.noBrandsHelp")}
      </p>
      <Link
        href="/dashboard/brands/new"
        className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-accent text-white rounded-xl text-sm font-semibold hover:opacity-90 transition-opacity shadow-sm"
      >
        <Plus className="w-4 h-4" />
        {t("briefs.center.addBrand")}
      </Link>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BriefCenterPage() {
  const { t } = useLocale();
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();
  const currentAgencyId = activeAgency?.id ?? null;

  const [data,            setData]            = useState<BriefCenterData | null>(null);
  const [loading,         setLoading]         = useState(true);
  const [error,           setError]           = useState<string | null>(null);
  const [attentionFilter, setAttentionFilter] = useState("");

  const fetchData = useCallback(async () => {
    if (!accessToken || !currentAgencyId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await dashboardApi.briefCenter(currentAgencyId, accessToken);
      setData(result);
    } catch {
      setError(t("briefs.center.loadError"));
    } finally {
      setLoading(false);
    }
  }, [accessToken, currentAgencyId, t]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !currentAgencyId) setLoading(false);
  }, [workspaceReady, workspaceLoading, currentAgencyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filteredAttention = data?.attention_items.filter(
    (i) => !attentionFilter || i.attention_reason === attentionFilter
  ) ?? [];

  // ── No agency ──────────────────────────────────────────────────────────────
  if (!loading && !currentAgencyId) {
    return (
      <div className="min-h-full bg-background flex flex-col items-center justify-center py-24 text-center px-4">
        <div className="w-16 h-16 bg-surface-2 border border-border rounded-2xl flex items-center justify-center mb-5 shadow-xs">
          <FileText className="w-7 h-7 text-text-muted" />
        </div>
        <h3 className="text-sm font-semibold text-text mb-2">{t("briefs.center.noAgency")}</h3>
        <p className="text-sm text-text-secondary mb-6 max-w-xs leading-relaxed">
          {t("briefs.center.noAgencyHelp")}
        </p>
        <Link
          href="/onboarding/create-agency"
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-accent text-white rounded-xl text-sm font-semibold hover:opacity-90 transition-opacity shadow-sm"
        >
          {t("briefs.center.createAgency")}
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-background">
      {/* Hero header */}
      <div className="border-b border-border bg-surface px-8 py-7">
        <div className="max-w-7xl mx-auto flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-7 h-7 bg-gradient-accent rounded-lg flex items-center justify-center shadow-sm">
                <Layers className="w-4 h-4 text-white" />
              </div>
              <h1 className="text-heading-lg text-text">{t("briefs.center.title")}</h1>
            </div>
            <p className="text-sm text-text-muted max-w-xl">
              {t("briefs.center.description")}
            </p>
          </div>
          <Link
            href="/dashboard/briefs/new"
            className="flex-shrink-0 inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-accent text-white rounded-xl text-sm font-semibold hover:opacity-90 transition-all shadow-sm hover:shadow-glow-sm hover:scale-[1.01] active:scale-[0.99]"
          >
            <Plus className="w-4 h-4" />
            {t("briefs.center.newBrief")}
          </Link>
        </div>
      </div>

      <div className="px-8 py-7 max-w-7xl mx-auto space-y-8">

        {/* Error state */}
        {error && (
          <div className="rounded-xl border border-danger-border bg-danger-subtle px-5 py-4 text-sm text-danger-text flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
            <button
              onClick={fetchData}
              className="underline text-danger-text/70 hover:text-danger-text transition-colors ml-auto flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              {t("common.actions.retry")}
            </button>
          </div>
        )}

        {/* KPI Cards */}
        <section>
          {loading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {Array.from({ length: 6 }).map((_, i) => <KPICardSkeleton key={i} />)}
            </div>
          ) : data ? (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4"
            >
              <KPICard
                label={t("briefs.center.activeBriefs")}
                value={data.kpis.total_active_briefs}
                icon={<FileText className="w-4 h-4" />}
              />
              <KPICard
                label={t("briefs.stats.overdue")}
                value={data.kpis.overdue_briefs}
                icon={<AlertTriangle className="w-4 h-4" />}
                variant={data.kpis.overdue_briefs > 0 ? "danger" : "default"}
              />
              <KPICard
                label={t("briefs.stats.revision")}
                value={data.kpis.revision_requested}
                icon={<RefreshCw className="w-4 h-4" />}
                variant={data.kpis.revision_requested > 0 ? "warning" : "default"}
              />
              <KPICard
                label={t("briefs.stats.pending")}
                value={data.kpis.pending_approvals}
                icon={<CheckCircle2 className="w-4 h-4" />}
                variant={data.kpis.pending_approvals > 0 ? "info" : "default"}
              />
              <KPICard
                label={t("briefs.center.newRequests")}
                value={data.kpis.new_brand_requests}
                icon={<Inbox className="w-4 h-4" />}
                variant={data.kpis.new_brand_requests > 0 ? "info" : "default"}
              />
              <KPICard
                label={t("briefs.center.dueToday")}
                value={data.kpis.due_today}
                icon={<Zap className="w-4 h-4" />}
                variant={data.kpis.due_today > 0 ? "warning" : "default"}
              />
            </motion.div>
          ) : null}
        </section>

        {/* Attention Section */}
        <section>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-1.5 h-5 bg-warning rounded-full" />
            <h2 className="text-sm font-semibold text-text">{t("briefs.center.needsAttention")}</h2>
            {data && data.attention_items.length > 0 && (
              <span className="ml-auto text-xs text-text-muted">{t("briefs.center.workCount", { count: data.attention_items.length })}</span>
            )}
          </div>

          {/* Filter chips */}
          <div className="flex items-center gap-1.5 mb-4 flex-wrap">
            {ATTENTION_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setAttentionFilter(tab.value)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                  attentionFilter === tab.value
                    ? "bg-accent text-white shadow-sm"
                    : "bg-surface-2 border border-border text-text-secondary hover:text-text hover:bg-surface hover:border-border-hover"
                )}
              >
                {t(tab.labelKey)}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => <AttentionItemSkeleton key={i} />)}
            </div>
          ) : filteredAttention.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center bg-surface border border-border rounded-2xl">
              <CheckCircle2 className="w-8 h-8 text-success mb-3" />
              <p className="text-sm font-medium text-text mb-0.5">{t("briefs.center.allGood")}</p>
              <p className="text-xs text-text-muted">
                {t(attentionFilter ? "briefs.center.noFilteredWork" : "briefs.center.noAttentionWork")}
              </p>
            </div>
          ) : (
            <AnimatePresence mode="popLayout">
              <motion.div
                key={attentionFilter}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-2"
              >
                {filteredAttention.map((item) => (
                  <motion.div
                    key={item.id}
                    layout
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                  >
                    <AttentionItemRow item={item} />
                  </motion.div>
                ))}
              </motion.div>
            </AnimatePresence>
          )}
        </section>

        {/* Brand Cards Section */}
        <section>
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-5 bg-accent rounded-full" />
              <h2 className="text-sm font-semibold text-text">{t("briefs.center.brands")}</h2>
              {data && (
                <span className="text-xs text-text-muted">{t("briefs.center.brandCount", { count: data.brand_cards.length })}</span>
              )}
            </div>
            <Link
              href="/dashboard/brands"
              className="text-xs text-text-muted hover:text-text flex items-center gap-1 transition-colors"
            >
              {t("briefs.center.viewAll")}
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {loading ? (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => <BrandCardSkeleton key={i} />)}
            </div>
          ) : !data || data.brand_cards.length === 0 ? (
            <EmptyBrands />
          ) : (
            <motion.div
              className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.07 } } }}
            >
              {data.brand_cards.map((brand) => (
                <motion.div
                  key={brand.id}
                  variants={{
                    hidden:  { opacity: 0, y: 16 },
                    visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] as const } },
                  }}
                >
                  <BrandCard brand={brand} />
                </motion.div>
              ))}
            </motion.div>
          )}
        </section>

      </div>
    </div>
  );
}
