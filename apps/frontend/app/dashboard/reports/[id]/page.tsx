"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  reportApi,
  type ReportWithSnapshot,
  type ReportShareTokenCreated,
  type ReportShareTokenRead,
} from "@/lib/api-client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";

const TYPE_LABELS: Record<string, string> = {
  monthly_brand: "Aylık Marka Raporu",
  agency_overview: "Ajans Genel Özeti",
  campaign_summary: "Kampanya Özeti",
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number | null | undefined;
  accent?: string;
}) {
  return (
    <div
      className={`bg-surface border rounded-xl p-5 ${accent ? `border-l-2 ${accent}` : "border-border"}`}
    >
      <div className="text-2xl font-bold text-text mb-1">
        {value === null || value === undefined ? "–" : String(value)}
      </div>
      <div className="text-xs text-text-muted">{label}</div>
    </div>
  );
}

function ShareModal({
  reportId,
  agencyId,
  accessToken,
  tokens,
  onClose,
  onTokenCreated,
  onTokenRevoked,
}: {
  reportId: string;
  agencyId: string;
  accessToken: string;
  tokens: ReportShareTokenRead[];
  onClose: () => void;
  onTokenCreated: (t: ReportShareTokenCreated) => void;
  onTokenRevoked: (id: string) => void;
}) {
  const [expiryDays, setExpiryDays] = useState(30);
  const [allowPdf, setAllowPdf] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    setCreating(true);
    setErr(null);
    try {
      const t = await reportApi.createShareToken(
        reportId,
        { expires_in_days: expiryDays, allow_pdf_download: allowPdf },
        agencyId,
        accessToken
      );
      setNewToken(t.token);
      onTokenCreated(t);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Oluşturulamadı");
    } finally {
      setCreating(false);
    }
  }

  async function revoke(tokenId: string) {
    setRevoking(tokenId);
    try {
      await reportApi.revokeShareToken(reportId, tokenId, agencyId, accessToken);
      onTokenRevoked(tokenId);
    } catch {
      // silent
    } finally {
      setRevoking(null);
    }
  }

  const shareUrl = newToken
    ? `${window.location.origin}/report/${newToken}`
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-md mx-4 shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="font-semibold text-text">Raporu Paylaş</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text transition-colors">
            ✕
          </button>
        </div>

        <div className="p-5 space-y-4">
          {shareUrl ? (
            <div className="space-y-3">
              <p className="text-sm text-emerald-400 font-medium">
                Bağlantı oluşturuldu! Bir kez gösterilir, lütfen kopyalayın.
              </p>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={shareUrl}
                  className="flex-1 px-3 py-2 bg-surface-2 border border-border rounded-lg text-xs text-text font-mono"
                />
                <button
                  onClick={() => navigator.clipboard.writeText(shareUrl)}
                  className="px-3 py-2 bg-accent text-white rounded-lg text-xs font-medium hover:bg-accent/90 transition-colors"
                >
                  Kopyala
                </button>
              </div>
              <button
                onClick={() => setNewToken(null)}
                className="text-sm text-text-muted hover:text-text transition-colors"
              >
                Yeni bağlantı oluştur
              </button>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1.5">
                  Geçerlilik Süresi (gün)
                </label>
                <select
                  value={expiryDays}
                  onChange={(e) => setExpiryDays(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-surface-2 border border-border rounded-lg text-sm text-text focus:outline-none focus:border-accent"
                >
                  <option value={7}>7 gün</option>
                  <option value={30}>30 gün</option>
                  <option value={90}>90 gün</option>
                  <option value={365}>1 yıl</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
                <input
                  type="checkbox"
                  checked={allowPdf}
                  onChange={(e) => setAllowPdf(e.target.checked)}
                  className="accent-indigo-500 w-4 h-4"
                />
                PDF indirme izni ver
              </label>
              {err && (
                <p className="text-xs text-danger">{err}</p>
              )}
              <button
                onClick={create}
                disabled={creating}
                className="w-full py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-60 transition-colors"
              >
                {creating ? "Oluşturuluyor…" : "Bağlantı Oluştur"}
              </button>
            </>
          )}

          {tokens.length > 0 && (
            <div className="pt-2">
              <p className="text-xs font-medium text-text-muted mb-2">Aktif bağlantılar</p>
              <div className="space-y-2">
                {tokens.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center justify-between bg-surface-2 rounded-lg px-3 py-2"
                  >
                    <div>
                      <p className="text-xs text-text">
                        {t.allow_pdf_download ? "PDF izinli" : "Görüntüleme"}
                      </p>
                      <p className="text-xs text-text-muted">
                        Bitiş: {fmtDate(t.expires_at)}
                      </p>
                    </div>
                    <button
                      onClick={() => revoke(t.id)}
                      disabled={revoking === t.id}
                      className="text-xs text-danger hover:text-danger/80 disabled:opacity-40 transition-colors"
                    >
                      {revoking === t.id ? "…" : "İptal"}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ReportDetailPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const params = useParams();
  const reportId = params.id as string;
  const router = useRouter();

  const [report, setReport] = useState<ReportWithSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [shareTokens, setShareTokens] = useState<ReportShareTokenRead[]>([]);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await reportApi.get(reportId, agencyId, accessToken);
      setReport(data);
      setShareTokens(data.active_share_tokens);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, reportId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRegenerate() {
    if (!accessToken || !agencyId) return;
    setRegenerating(true);
    try {
      const data = await reportApi.regenerate(reportId, agencyId, accessToken);
      setReport(data);
      setShareTokens(data.active_share_tokens);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yenilenemedi");
    } finally {
      setRegenerating(false);
    }
  }

  async function handleArchive() {
    if (!accessToken || !agencyId) return;
    setArchiving(true);
    try {
      const data = await reportApi.archive(reportId, agencyId, accessToken);
      setReport(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Arşivlenemedi");
    } finally {
      setArchiving(false);
    }
  }

  function handlePdfDownload() {
    if (!accessToken || !agencyId) return;
    const url = reportApi.pdfUrl(reportId);
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", `flobrief-report-${reportId}.pdf`);
    document.body.appendChild(a);
    fetch(url, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Agency-ID": agencyId,
      },
    })
      .then((r) => r.blob())
      .then((blob) => {
        const objUrl = URL.createObjectURL(blob);
        a.href = objUrl;
        a.click();
        URL.revokeObjectURL(objUrl);
        document.body.removeChild(a);
      });
  }

  if (loading) {
    return (
      <div className="p-8 max-w-4xl mx-auto animate-pulse">
        <div className="h-7 bg-surface-2 rounded w-1/2 mb-3" />
        <div className="h-4 bg-surface-2 rounded w-1/3 mb-8" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-surface rounded-xl border border-border" />
          ))}
        </div>
        <div className="h-48 bg-surface rounded-xl border border-border" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      </div>
    );
  }

  if (!report) return null;

  const m = report.snapshot?.metrics ?? {};

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <button
            onClick={() => router.push("/dashboard/reports")}
            className="text-sm text-text-muted hover:text-text transition-colors mb-2 flex items-center gap-1"
          >
            ← Raporlar
          </button>
          <h1 className="text-2xl font-semibold text-text">{report.title}</h1>
          <p className="text-sm text-text-muted mt-1">
            {TYPE_LABELS[report.report_type]} &middot;{" "}
            {fmtDate(report.period_start)} – {fmtDate(report.period_end)}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {report.status !== "archived" && (
            <>
              <button
                onClick={() => setShowShare(true)}
                className="px-3 py-2 text-sm text-text-muted border border-border rounded-lg hover:border-accent/40 hover:text-text transition-colors"
              >
                Paylaş
              </button>
              <button
                onClick={handlePdfDownload}
                className="px-3 py-2 text-sm text-text-muted border border-border rounded-lg hover:border-accent/40 hover:text-text transition-colors"
              >
                PDF
              </button>
              <button
                onClick={handleRegenerate}
                disabled={regenerating}
                className="px-3 py-2 text-sm bg-accent text-white rounded-lg hover:bg-accent/90 disabled:opacity-60 transition-colors"
              >
                {regenerating ? "Yenileniyor…" : "Yenile"}
              </button>
            </>
          )}
          {report.status !== "archived" && (
            <button
              onClick={handleArchive}
              disabled={archiving}
              className="px-3 py-2 text-sm text-text-muted border border-border rounded-lg hover:border-danger/40 hover:text-danger transition-colors"
            >
              {archiving ? "…" : "Arşivle"}
            </button>
          )}
        </div>
      </div>

      {report.status === "archived" && (
        <div className="mt-3 mb-6 px-3 py-2 bg-surface-2 border border-border rounded-lg text-sm text-text-muted inline-flex items-center gap-2">
          <span>◎</span> Bu rapor arşivlendi
        </div>
      )}

      {!report.snapshot ? (
        <div className="mt-8 flex flex-col items-center justify-center py-20 text-center bg-surface border border-border rounded-2xl">
          <p className="text-base font-medium text-text mb-1">Rapor verisi henüz yok</p>
          <p className="text-sm text-text-muted mb-4">
            Raporu oluşturmak için &quot;Yenile&quot; butonuna tıklayın.
          </p>
        </div>
      ) : (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 mb-8">
            <MetricCard
              label="Oluşturulan Brief"
              value={m.created_briefs_count as number}
              accent="border-l-indigo-500"
            />
            <MetricCard
              label="Onaylanan Brief"
              value={m.approved_briefs_count as number}
              accent="border-l-emerald-500"
            />
            <MetricCard
              label="Revizyon İstendi"
              value={m.revision_requested_count as number}
              accent="border-l-amber-500"
            />
            <MetricCard
              label="Yayınlanan İçerik"
              value={m.published_calendar_items_count as number}
              accent="border-l-cyan-500"
            />
          </div>

          {/* Two-column detail */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Brief performance */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text mb-4">Brief Performansı</h2>
              <div className="space-y-3">
                {(
                  [
                    ["Bekleyen Onay", m.pending_approvals_count],
                    [
                      "Ort. Onay Süresi",
                      m.average_approval_time_hours != null
                        ? `${(m.average_approval_time_hours as number).toFixed(1)} saat`
                        : "–",
                    ],
                  ] as [string, unknown][]
                ).map(([label, val]) => (
                  <div
                    key={label}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-text-muted">{label}</span>
                    <span className="font-medium text-text">
                      {val === null || val === undefined ? "–" : String(val)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Platform distribution */}
            <div className="bg-surface border border-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text mb-4">Platform Dağılımı</h2>
              {Object.keys(m.platform_distribution as Record<string, number> ?? {}).length === 0 ? (
                <p className="text-sm text-text-muted">Veri yok</p>
              ) : (
                <div className="space-y-2">
                  {Object.entries(m.platform_distribution as Record<string, number>)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 6)
                    .map(([plat, cnt]) => {
                      const total = Object.values(
                        m.platform_distribution as Record<string, number>
                      ).reduce((s, v) => s + v, 0);
                      const pct = total ? Math.round((cnt / total) * 100) : 0;
                      return (
                        <div key={plat}>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="text-text capitalize">{plat}</span>
                            <span className="text-text-muted">{cnt}</span>
                          </div>
                          <div className="h-1.5 bg-surface-2 rounded-full">
                            <div
                              className="h-1.5 bg-accent rounded-full"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>

            {/* Most revised */}
            {(m.most_revised_briefs as unknown[])?.length > 0 && (
              <div className="bg-surface border border-border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-text mb-4">
                  En Çok Revizyon İstenen
                </h2>
                <div className="space-y-2">
                  {(
                    m.most_revised_briefs as { brief_id: string; revision_count: number }[]
                  )
                    .slice(0, 5)
                    .map((entry) => (
                      <div
                        key={entry.brief_id}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-text-muted font-mono text-xs">
                          #{entry.brief_id.slice(0, 8)}
                        </span>
                        <span className="font-medium text-amber-400">
                          {entry.revision_count} revizyon
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Calendar status */}
            {Object.keys(m.calendar_status_distribution as Record<string, number> ?? {}).length > 0 && (
              <div className="bg-surface border border-border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-text mb-4">İçerik Durum Özeti</h2>
                <div className="space-y-2">
                  {Object.entries(
                    m.calendar_status_distribution as Record<string, number>
                  )
                    .sort(([, a], [, b]) => b - a)
                    .map(([status, cnt]) => (
                      <div
                        key={status}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-text-muted capitalize">{status}</span>
                        <span className="font-medium text-text">{cnt}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>

          <p className="text-xs text-text-muted mt-6">
            Son güncelleme: {fmtDate(report.snapshot.created_at)}
          </p>
        </>
      )}

      {showShare && agencyId && accessToken && (
        <ShareModal
          reportId={reportId}
          agencyId={agencyId}
          accessToken={accessToken}
          tokens={shareTokens}
          onClose={() => setShowShare(false)}
          onTokenCreated={(t) => {
            setShareTokens((prev) => [t, ...prev]);
          }}
          onTokenRevoked={(id) => {
            setShareTokens((prev) => prev.filter((t) => t.id !== id));
          }}
        />
      )}
    </div>
  );
}
