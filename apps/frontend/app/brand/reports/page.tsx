"use client";

import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, type ReportRead, type ReportType } from "@/lib/api-client";
import { useEffect, useState, useCallback } from "react";

const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  monthly_brand: "Aylık Marka Raporu",
  agency_overview: "Ajans Genel Bakış",
  campaign_summary: "Kampanya Özeti",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatPeriod(start: string, end: string): string {
  const s = new Date(start).toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
  const e = new Date(end).toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
  return s === e ? s : `${s} – ${e}`;
}

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-5 py-5 border-b border-border last:border-0 animate-pulse">
      <div className="w-10 h-10 bg-surface-2 rounded-xl flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3.5 bg-surface-2 rounded w-56" />
        <div className="h-3 bg-surface-2 rounded w-36" />
      </div>
      <div className="h-5 bg-surface-2 rounded-md w-20" />
    </div>
  );
}

export default function BrandReportsPage() {
  const { accessToken } = useAuth();
  const [reports, setReports] = useState<ReportRead[] | null>(null);
  const [error, setError] = useState(false);

  const loadData = useCallback(async () => {
    if (!accessToken) return;
    try {
      const res = await brandPortalApi.listReports(accessToken);
      setReports(Array.isArray(res) ? res : []);
    } catch {
      setError(true);
      setReports([]);
    }
  }, [accessToken]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text">Raporlar</h1>
        <p className="mt-1 text-text-muted">
          Ajansınızın paylaştığı brief ve kampanya raporları.
        </p>
      </div>

      {error ? (
        <div className="bg-surface border border-border rounded-xl p-10 text-center">
          <p className="text-sm text-danger mb-3">Raporlar yüklenemedi.</p>
          <button onClick={loadData} className="text-xs text-accent hover:underline">
            Tekrar dene
          </button>
        </div>
      ) : reports === null ? (
        <div className="bg-surface border border-border rounded-xl">
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
        </div>
      ) : reports.length === 0 ? (
        <div className="bg-surface border border-border rounded-xl p-16 flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-text mb-1">Henüz rapor yok</p>
          <p className="text-xs text-text-muted max-w-sm">
            Ajansınız sizinle rapor paylaştığında burada görüntülenecek.
          </p>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-xl">
          {reports.map((report) => (
            <div
              key={report.id}
              className="flex items-center gap-4 px-5 py-5 border-b border-border last:border-0"
            >
              <div className="w-10 h-10 bg-accent/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-text truncate">{report.title}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-text-muted">
                    {REPORT_TYPE_LABELS[report.report_type] ?? report.report_type}
                  </span>
                  <span className="text-text-muted">·</span>
                  <span className="text-xs text-text-muted">
                    {formatPeriod(report.period_start, report.period_end)}
                  </span>
                </div>
              </div>
              <span className="text-xs text-text-muted flex-shrink-0">{formatDate(report.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
