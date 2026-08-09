"use client";

import { Select } from "@/components/ui/select";
import { TimeBarChart } from "@/components/time-tracking/TimeBarChart";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { briefApi, timeReportApi, type BriefRead, type BriefTimeSummary } from "@/lib/api-client";
import { useCallback, useEffect, useState } from "react";

export default function ByBriefTimeReportPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [briefs, setBriefs] = useState<BriefRead[]>([]);
  const [briefId, setBriefId] = useState<string>("");
  const [summary, setSummary] = useState<BriefTimeSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    briefApi
      .list({ limit: 100 }, agencyId, accessToken)
      .then((res) => {
        setBriefs(res.items);
        if (res.items.length > 0) setBriefId(res.items[0].id);
      })
      .catch(() => {});
  }, [accessToken, agencyId]);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId || !briefId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await timeReportApi.getByBrief(briefId, agencyId, accessToken);
      setSummary(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, briefId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!agencyId) return null;

  return (
    <div>
      <div className="mb-5 max-w-sm">
        <Select
          label="Brief"
          value={briefId}
          onChange={(e) => setBriefId(e.target.value)}
          options={briefs.map((b) => ({ value: b.id, label: b.title }))}
        />
      </div>

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : loading || !summary ? (
        <div className="h-48 bg-surface-2 rounded-xl animate-pulse" />
      ) : (
        <div className="bg-surface border border-border rounded-xl p-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <div>
              <p
                data-testid="brief-actual-hours"
                className="text-2xl font-semibold text-text tabular-nums"
              >
                {summary.actual_hours.toFixed(1)}s
              </p>
              <p className="text-xs text-text-muted mt-0.5">Harcanan</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-text tabular-nums">
                {summary.estimated_hours !== null ? `${summary.estimated_hours}s` : "—"}
              </p>
              <p className="text-xs text-text-muted mt-0.5">Tahmini</p>
            </div>
            <div>
              <p
                className={`text-2xl font-semibold tabular-nums ${
                  summary.is_over_estimate ? "text-danger" : "text-text"
                }`}
              >
                {summary.remaining_hours !== null ? `${summary.remaining_hours}s` : "—"}
              </p>
              <p className="text-xs text-text-muted mt-0.5">Kalan</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-text tabular-nums">
                {summary.entry_count}
              </p>
              <p className="text-xs text-text-muted mt-0.5">Kayıt Sayısı</p>
            </div>
          </div>
          {summary.is_over_estimate && (
            <div className="bg-danger/10 border border-danger/25 rounded-lg px-3 py-2 mb-4 text-xs text-danger">
              Bu brief tahmini süreyi aştı.
            </div>
          )}
          <TimeBarChart data={summary.category_breakdown} />
        </div>
      )}
    </div>
  );
}
