"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { reportApi, type ReportRead, type ReportStatus, type ReportType } from "@/lib/api-client";
import Link from "next/link";
import { useEffect, useState, useCallback } from "react";

const TYPE_LABELS: Record<ReportType, string> = {
  monthly_brand: "Aylık Marka",
  agency_overview: "Ajans Özeti",
  campaign_summary: "Kampanya",
};

const STATUS_STYLES: Record<ReportStatus, string> = {
  draft: "bg-surface-2 text-text-muted",
  generated: "bg-indigo-500/15 text-indigo-400",
  shared: "bg-emerald-500/15 text-emerald-400",
  archived: "bg-surface-2 text-text-muted",
};

const STATUS_LABELS: Record<ReportStatus, string> = {
  draft: "Taslak",
  generated: "Oluşturuldu",
  shared: "Paylaşıldı",
  archived: "Arşiv",
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function ReportSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="space-y-2 flex-1">
          <div className="h-4 bg-surface-2 rounded w-3/4" />
          <div className="h-3 bg-surface-2 rounded w-1/2" />
        </div>
        <div className="h-5 w-20 bg-surface-2 rounded-full" />
      </div>
      <div className="h-3 bg-surface-2 rounded w-1/3 mt-4" />
    </div>
  );
}

function ReportCard({ report }: { report: ReportRead }) {
  return (
    <Link href={`/dashboard/reports/${report.id}`}>
      <div className="bg-surface border border-border rounded-xl p-5 hover:border-accent/40 hover:shadow-card transition-all group cursor-pointer">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-text text-sm truncate group-hover:text-accent transition-colors">
              {report.title}
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              {TYPE_LABELS[report.report_type]} &middot;{" "}
              {fmtDate(report.period_start)} – {fmtDate(report.period_end)}
            </p>
          </div>
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${STATUS_STYLES[report.status]}`}
          >
            {STATUS_LABELS[report.status]}
          </span>
        </div>
        <p className="text-xs text-text-muted mt-3">
          Oluşturuldu: {fmtDate(report.created_at)}
        </p>
      </div>
    </Link>
  );
}

export default function ReportsPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [items, setItems] = useState<ReportRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const LIMIT = 20;

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await reportApi.list(agencyId, accessToken, { limit: LIMIT, offset });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, offset]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !agencyId) {
      setLoading(false);
    }
  }, [workspaceReady, workspaceLoading, agencyId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-text">Raporlar</h1>
          <p className="text-sm text-text-muted mt-1">
            Ajans performans ve marka raporları
          </p>
        </div>
        <Link
          href="/dashboard/reports/new"
          className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          <span className="text-base leading-none">+</span>
          Yeni Rapor
        </Link>
      </div>

      {!loading && !agencyId ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <span className="text-3xl">◒</span>
          </div>
          <p className="text-base font-medium text-text mb-1">Ajans seçilmedi</p>
          <p className="text-sm text-text-muted mb-6">Raporları görüntülemek için bir ajans seçin.</p>
          <a href="/onboarding/create-agency" className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors">Ajans Oluştur</a>
        </div>
      ) : error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <ReportSkeleton key={i} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <span className="text-3xl">◒</span>
          </div>
          <p className="text-base font-medium text-text mb-1">Henüz rapor yok</p>
          <p className="text-sm text-text-muted mb-6">
            İlk raporunuzu oluşturun ve ajans performansını analiz edin.
          </p>
          <Link
            href="/dashboard/reports/new"
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            Rapor Oluştur
          </Link>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {items.map((r) => (
              <ReportCard key={r.id} report={r} />
            ))}
          </div>

          {total > LIMIT && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
              <button
                onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
                disabled={offset === 0}
                className="text-sm text-text-muted hover:text-text disabled:opacity-40 transition-colors"
              >
                ← Önceki
              </button>
              <span className="text-sm text-text-muted">
                {offset + 1}–{Math.min(offset + LIMIT, total)} / {total}
              </span>
              <button
                onClick={() => setOffset((o) => o + LIMIT)}
                disabled={offset + LIMIT >= total}
                className="text-sm text-text-muted hover:text-text disabled:opacity-40 transition-colors"
              >
                Sonraki →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
