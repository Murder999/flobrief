"use client";

import { publicReportApi, publicBrandingApi, type PublicReportView, type PublicBrandingView } from "@/lib/api-client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function _assetUrl(url: string | null): string | null {
  if (!url) return null;
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}

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

function KpiCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number | null | undefined;
  accent: string;
}) {
  return (
    <div className={`rounded-xl p-5 border-l-2 bg-white/5 backdrop-blur-sm border border-white/10 ${accent}`}>
      <div className="text-3xl font-bold text-white mb-1">
        {value === null || value === undefined ? "–" : String(value)}
      </div>
      <div className="text-xs text-white/60">{label}</div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f0f1a] via-[#111127] to-[#0a0a14] p-8">
      <div className="max-w-3xl mx-auto animate-pulse">
        <div className="h-8 bg-white/10 rounded w-1/2 mb-3" />
        <div className="h-4 bg-white/10 rounded w-1/3 mb-8" />
        <div className="grid grid-cols-4 gap-4 mb-8">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-white/5 rounded-xl border border-white/10" />
          ))}
        </div>
        <div className="h-48 bg-white/5 rounded-xl border border-white/10" />
      </div>
    </div>
  );
}

export default function PublicReportPage() {
  const params = useParams();
  const token = params.token as string;
  const [branding, setBranding] = useState<PublicBrandingView | null>(null);

  const [report, setReport] = useState<PublicReportView | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorCode, setErrorCode] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      publicReportApi.getByToken(token),
      publicBrandingApi.getByReportToken(token).catch(() => null),
    ])
      .then(([data, brandingData]) => {
        setReport(data);
        // Always apply branding: the API resolves to the agency's own
        // override when is_branded=true, or the platform default identity
        // as a fallback when it's false.
        if (brandingData) setBranding(brandingData);
      })
      .catch((e) => {
        setErrorCode(e?.status ?? 0);
        setErrorMsg(
          e?.status === 410
            ? "Bu rapor bağlantısının süresi dolmuş veya iptal edilmiş."
            : e?.status === 404
            ? "Rapor bulunamadı."
            : "Rapor yüklenemedi."
        );
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <LoadingSkeleton />;

  if (errorMsg) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#0f0f1a] via-[#111127] to-[#0a0a14] flex items-center justify-center p-8">
        <div className="text-center max-w-sm">
          <div className="w-16 h-16 bg-white/5 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">{errorCode === 410 ? "⏱" : "◎"}</span>
          </div>
          <h1 className="text-xl font-semibold text-white mb-2">
            {errorCode === 410 ? "Bağlantı Geçersiz" : "Rapor Bulunamadı"}
          </h1>
          <p className="text-sm text-white/50">{errorMsg}</p>
        </div>
      </div>
    );
  }

  if (!report) return null;

  const m = report.metrics;
  const primaryColor = branding?.primary_color ?? "#6366F1";
  const logoUrl = _assetUrl(branding?.logo_url ?? null);
  const brandDisplayName = branding?.brand_name ?? branding?.agency_name ?? "Flobrief";

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f0f1a] via-[#111127] to-[#0a0a14]">
      {/* Header bar */}
      <div className="border-b border-white/10 backdrop-blur-sm" style={{ background: branding ? `${primaryColor}20` : "rgba(99,102,241,0.2)" }}>
        <div className="max-w-3xl mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {logoUrl ? (
              <img src={logoUrl} alt={brandDisplayName} className="h-6 w-auto max-w-[90px] object-contain" />
            ) : (
              <div
                className="w-6 h-6 rounded flex items-center justify-center"
                style={{ background: primaryColor }}
              >
                <span className="text-white font-bold text-xs">
                  {(brandDisplayName[0] ?? "F").toUpperCase()}
                </span>
              </div>
            )}
            <span className="text-white font-semibold text-sm">{brandDisplayName}</span>
          </div>
          {report.allow_pdf_download && (
            <a
              href={publicReportApi.pdfUrl(token)}
              download={`flobrief-report.pdf`}
              className="px-3 py-1.5 text-xs font-medium text-white bg-white/10 border border-white/20 rounded-lg hover:bg-white/20 transition-colors"
            >
              PDF İndir
            </a>
          )}
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-8 py-10">
        {/* Title block */}
        <div className="mb-8">
          <p className="text-xs font-medium text-indigo-400 uppercase tracking-wider mb-2">
            {TYPE_LABELS[report.report_type] ?? report.report_type}
          </p>
          <h1 className="text-3xl font-bold text-white mb-2">{report.title}</h1>
          <p className="text-sm text-white/50">
            {fmtDate(report.period_start)} – {fmtDate(report.period_end)}
          </p>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <KpiCard
            label="Oluşturulan Brief"
            value={m.created_briefs_count as number}
            accent="border-l-indigo-500"
          />
          <KpiCard
            label="Onaylanan Brief"
            value={m.approved_briefs_count as number}
            accent="border-l-emerald-500"
          />
          <KpiCard
            label="Revizyon İstendi"
            value={m.revision_requested_count as number}
            accent="border-l-amber-500"
          />
          <KpiCard
            label="Yayınlanan İçerik"
            value={m.published_calendar_items_count as number}
            accent="border-l-cyan-500"
          />
        </div>

        {/* Detail grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Brief performance */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Brief Performansı</h2>
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
                <div key={label} className="flex items-center justify-between text-sm">
                  <span className="text-white/50">{label}</span>
                  <span className="font-medium text-white">
                    {val === null || val === undefined ? "–" : String(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Platform distribution */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Platform Dağılımı</h2>
            {Object.keys(m.platform_distribution as Record<string, number> ?? {}).length === 0 ? (
              <p className="text-sm text-white/40">Veri yok</p>
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
                          <span className="text-white capitalize">{plat}</span>
                          <span className="text-white/50">{cnt}</span>
                        </div>
                        <div className="h-1.5 bg-white/10 rounded-full">
                          <div
                            className="h-1.5 rounded-full"
                            style={{ width: `${pct}%`, background: primaryColor }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <p className="text-xs text-white/30 mt-10 text-center">
          {branding?.custom_footer_text
            ? branding.custom_footer_text
            : `Bu rapor ${brandDisplayName} tarafından ${fmtDate(report.generated_at)} tarihinde oluşturuldu.`}
        </p>
      </div>
    </div>
  );
}
