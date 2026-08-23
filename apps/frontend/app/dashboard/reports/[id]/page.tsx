"use client";

import {
  ReportAnalytics,
  ReportAnalyticsSkeleton,
  ReportEmptyState,
  ReportErrorState,
  ReportPeriod,
  ReportStatusBadge,
  ReportTypeLabel,
  formatReportGeneratedAt,
} from "@/components/reports/reporting";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { useLocale } from "@/context/locale-context";
import { useWorkspace } from "@/context/workspace-context";
import { useAuth } from "@/hooks/useAuth";
import {
  reportApi,
  type ReportShareTokenCreated,
  type ReportShareTokenRead,
  type ReportWithSnapshot,
} from "@/lib/api-client";
import { formatLocalizedDate } from "@/lib/i18n/format";
import { AlertCircle, Archive, ArrowLeft, Check, Copy, Download, Link2, RefreshCw } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function ShareModal({
  isOpen,
  reportId,
  agencyId,
  accessToken,
  tokens,
  onClose,
  onTokenCreated,
  onTokenRevoked,
}: {
  isOpen: boolean;
  reportId: string;
  agencyId: string;
  accessToken: string;
  tokens: ReportShareTokenRead[];
  onClose: () => void;
  onTokenCreated: (token: ReportShareTokenCreated) => void;
  onTokenRevoked: (id: string) => void;
}) {
  const { locale, t } = useLocale();
  const [expiryDays, setExpiryDays] = useState(30);
  const [allowPdf, setAllowPdf] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const shareUrl = newToken && typeof window !== "undefined"
    ? `${window.location.origin}/report/${newToken}`
    : null;

  async function createLink() {
    setCreating(true);
    setError(null);
    try {
      const token = await reportApi.createShareToken(
        reportId,
        { expires_in_days: expiryDays, allow_pdf_download: allowPdf },
        agencyId,
        accessToken
      );
      setNewToken(token.token);
      onTokenCreated(token);
    } catch {
      setError(t("reports.share.error"));
    } finally {
      setCreating(false);
    }
  }

  async function revokeLink(tokenId: string) {
    setRevoking(tokenId);
    setError(null);
    try {
      await reportApi.revokeShareToken(reportId, tokenId, agencyId, accessToken);
      onTokenRevoked(tokenId);
    } catch {
      setError(t("reports.share.revokeError"));
    } finally {
      setRevoking(null);
    }
  }

  async function copyLink() {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={t("reports.share.title")} maxWidth="md">
      <div className="space-y-5">
        <p className="text-sm leading-6 text-text-muted">{t("reports.share.description")}</p>

        {shareUrl ? (
          <div className="space-y-3">
            <div role="status" className="flex items-start gap-2 rounded-lg border border-success/20 bg-success/10 px-3 py-2.5 text-sm text-text">
              <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-success" aria-hidden="true" />
              <span>{t("reports.share.created")}</span>
            </div>
            <label htmlFor="report-share-url" className="sr-only">{t("reports.share.copy")}</label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                id="report-share-url"
                readOnly
                value={shareUrl}
                className="h-9 min-w-0 flex-1 rounded-lg border border-border bg-surface-2 px-3 text-xs text-text outline-none focus:ring-2 focus:ring-accent/30"
              />
              <Button type="button" variant="outline" size="sm" onClick={copyLink}>
                {copied ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}
                {copied ? t("reports.share.copied") : t("reports.share.copy")}
              </Button>
            </div>
            <button
              type="button"
              onClick={() => {
                setNewToken(null);
                setCopied(false);
              }}
              className="text-xs font-medium text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
            >
              {t("reports.share.createAnother")}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <Select
              id="report-link-expiry"
              label={t("reports.share.expiry")}
              aria-label={t("reports.share.expiry")}
              value={String(expiryDays)}
              onChange={(event) => setExpiryDays(Number(event.target.value))}
              options={[
                { value: "7", label: t("reports.share.days7") },
                { value: "30", label: t("reports.share.days30") },
                { value: "90", label: t("reports.share.days90") },
                { value: "365", label: t("reports.share.days365") },
              ]}
            />
            <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text">
              <input
                type="checkbox"
                checked={allowPdf}
                onChange={(event) => setAllowPdf(event.target.checked)}
                className="h-4 w-4 accent-indigo-500"
              />
              {t("reports.share.allowPdf")}
            </label>
            <Button type="button" className="w-full" isLoading={creating} onClick={createLink}>
              <Link2 className="h-4 w-4" aria-hidden="true" />
              {creating ? t("reports.share.creating") : t("reports.share.create")}
            </Button>
          </div>
        )}

        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

        {tokens.length > 0 ? (
          <div className="border-t border-border pt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">{t("reports.share.active")}</h3>
            <div className="mt-2 divide-y divide-border rounded-lg border border-border">
              {tokens.map((token) => (
                <div key={token.id} className="flex items-center justify-between gap-4 px-3 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-text">{t(token.allow_pdf_download ? "reports.share.pdfAllowed" : "reports.share.viewOnly")}</p>
                    <p className="mt-0.5 text-xs text-text-muted">
                      {t("reports.share.expires", { date: formatLocalizedDate(token.expires_at, locale) })}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={revoking === token.id}
                    onClick={() => revokeLink(token.id)}
                    className="text-danger hover:text-danger"
                  >
                    {revoking === token.id ? t("reports.share.revoking") : t("reports.share.revoke")}
                  </Button>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}

export default function ReportDetailPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const { locale, t } = useLocale();
  const agencyId = activeAgency?.id ?? null;
  const reportId = useParams().id as string;
  const router = useRouter();

  const [report, setReport] = useState<ReportWithSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [shareTokens, setShareTokens] = useState<ReportShareTokenRead[]>([]);

  const loadReport = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setLoadError(false);
    try {
      const data = await reportApi.get(reportId, agencyId, accessToken);
      setReport(data);
      setShareTokens(data.active_share_tokens);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, reportId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  async function regenerate() {
    if (!accessToken || !agencyId) return;
    setRegenerating(true);
    setActionError(null);
    try {
      const data = await reportApi.regenerate(reportId, agencyId, accessToken);
      setReport(data);
      setShareTokens(data.active_share_tokens);
    } catch {
      setActionError(t("reports.detail.actionError"));
    } finally {
      setRegenerating(false);
    }
  }

  async function archiveReport() {
    if (!accessToken || !agencyId) return;
    setArchiving(true);
    setActionError(null);
    try {
      setReport(await reportApi.archive(reportId, agencyId, accessToken));
    } catch {
      setActionError(t("reports.detail.actionError"));
    } finally {
      setArchiving(false);
    }
  }

  async function downloadPdf() {
    if (!accessToken || !agencyId) return;
    setDownloading(true);
    setActionError(null);
    try {
      const blob = await reportApi.downloadPdf(reportId, agencyId, accessToken);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `postpiloter-report-${reportId}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      setActionError(t("reports.detail.pdfError"));
    } finally {
      setDownloading(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
        <div aria-hidden="true" className="mb-6 animate-pulse">
          <div className="h-4 w-24 rounded bg-surface-2" />
          <div className="mt-4 h-7 w-2/5 rounded bg-surface-2" />
          <div className="mt-3 h-4 w-3/5 rounded bg-surface-2" />
        </div>
        <ReportAnalyticsSkeleton />
      </main>
    );
  }

  if (loadError || !report) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
        <ReportErrorState
          title={t("reports.detail.loadErrorTitle")}
          description={t("reports.detail.loadErrorDescription")}
          onRetry={loadReport}
        />
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
      <header className="mb-6">
        <button
          type="button"
          onClick={() => router.push("/dashboard/reports")}
          className="mb-4 inline-flex min-h-9 items-center gap-2 rounded-lg text-sm text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {t("reports.detail.back")}
        </button>

        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <ReportStatusBadge status={report.status} />
              <span className="text-xs font-medium text-text-muted"><ReportTypeLabel type={report.report_type} /></span>
            </div>
            <h1 className="mt-3 break-words text-2xl font-semibold tracking-tight text-text">{report.title}</h1>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted">
              <span>{t("reports.common.period")}: <ReportPeriod start={report.period_start} end={report.period_end} /></span>
              {report.snapshot ? (
                <span>{t("reports.common.updated")}: {formatReportGeneratedAt(report.snapshot.created_at, locale)}</span>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {report.status !== "archived" ? (
              <Button type="button" variant="outline" onClick={() => setShowShare(true)}>
                <Link2 className="h-4 w-4" aria-hidden="true" />
                {t("reports.detail.share")}
              </Button>
            ) : null}
            <Button type="button" variant="outline" isLoading={downloading} onClick={downloadPdf}>
              <Download className="h-4 w-4" aria-hidden="true" />
              {downloading ? t("reports.detail.downloadingPdf") : t("reports.detail.downloadPdf")}
            </Button>
            {report.status !== "archived" ? (
              <>
                <Button type="button" isLoading={regenerating} onClick={regenerate}>
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  {regenerating ? t("reports.detail.regenerating") : t("reports.detail.regenerate")}
                </Button>
                <Button type="button" variant="ghost" isLoading={archiving} onClick={archiveReport} className="text-text-muted">
                  <Archive className="h-4 w-4" aria-hidden="true" />
                  {archiving ? t("reports.detail.archiving") : t("reports.detail.archive")}
                </Button>
              </>
            ) : null}
          </div>
        </div>
      </header>

      {actionError ? (
        <div role="alert" className="mb-5 flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          <AlertCircle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          {actionError}
        </div>
      ) : null}

      {report.status === "archived" ? (
        <div className="mb-5 rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-text-muted">
          {t("reports.detail.archivedNotice")}
        </div>
      ) : null}

      {report.snapshot ? (
        <ReportAnalytics metrics={report.snapshot.metrics} audience="agency" />
      ) : (
        <ReportEmptyState
          title={t("reports.detail.emptyTitle")}
          description={t("reports.detail.emptyDescription")}
          action={report.status !== "archived" ? (
            <Button type="button" size="sm" isLoading={regenerating} onClick={regenerate}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              {t("reports.detail.regenerate")}
            </Button>
          ) : undefined}
        />
      )}

      {agencyId && accessToken ? (
        <ShareModal
          isOpen={showShare}
          reportId={reportId}
          agencyId={agencyId}
          accessToken={accessToken}
          tokens={shareTokens}
          onClose={() => setShowShare(false)}
          onTokenCreated={(token) => setShareTokens((current) => [token, ...current])}
          onTokenRevoked={(id) => setShareTokens((current) => current.filter((token) => token.id !== id))}
        />
      ) : null}
    </main>
  );
}
