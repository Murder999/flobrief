"use client";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { DateRangeFilter } from "@/components/time-tracking/DateRangeFilter";
import { useDateRangeFilter } from "@/hooks/useDateRangeFilter";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { timeReportApi, type TeamTimeReportResponse } from "@/lib/api-client";
import { Download } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export default function TeamTimesheetPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const { toast } = useToast();
  const agencyId = activeAgency?.id ?? null;
  const dateRange = useDateRangeFilter();

  const [data, setData] = useState<TeamTimeReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await timeReportApi.getTeam(agencyId, accessToken, dateRange.apiParams);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, dateRange.apiParams]);

  useEffect(() => {
    load();
  }, [load]);

  const handleExport = async () => {
    if (!accessToken || !agencyId) return;
    setExporting(true);
    try {
      const blob = await timeReportApi.exportCsv(agencyId, accessToken, dateRange.apiParams);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "postpiloter-zaman-kayitlari.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Dışa aktarılamadı", "error");
    } finally {
      setExporting(false);
    }
  };

  if (!agencyId) return null;

  return (
    <div>
      <DateRangeFilter
        value={dateRange}
        onPresetChange={dateRange.setPreset}
        onCustomChange={dateRange.setCustomDates}
        onClear={dateRange.clear}
      />

      <div className="flex items-center justify-between mb-5">
        {data && (
          <div className="flex items-center gap-4 text-sm text-text-muted">
            <span>
              Toplam: <span className="font-semibold text-text">{data.total_hours.toFixed(1)}s</span>
            </span>
            <span>
              Faturalandırılabilir:{" "}
              <span className="font-semibold text-text">{data.billable_hours.toFixed(1)}s</span>
            </span>
          </div>
        )}
        <Button onClick={handleExport} isLoading={exporting} variant="secondary" size="sm">
          <Download className="w-3.5 h-3.5" />
          CSV İndir
        </Button>
      </div>

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : loading || !data ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 bg-surface-2 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : data.users.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-sm font-medium text-text mb-1">
            {dateRange.start && dateRange.end
              ? `${dateRange.start} – ${dateRange.end} aralığında zaman kaydı yok`
              : "Bu hafta zaman kaydı yok"}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {data.users.map((u) => (
            <div
              key={u.user_id}
              className="bg-surface border border-border rounded-xl p-4 flex items-center justify-between"
            >
              <div>
                <p className="text-sm font-medium text-text">{u.user_name}</p>
                <p className="text-xs text-text-muted">{u.entry_count} kayıt</p>
              </div>
              <div className="flex items-center gap-4 text-right">
                <div>
                  <p className="text-sm font-semibold text-text tabular-nums">
                    {u.total_hours.toFixed(1)}s
                  </p>
                  <p className="text-[11px] text-text-muted">toplam</p>
                </div>
                <div>
                  <p className="text-sm font-semibold text-text tabular-nums">
                    {u.billable_hours.toFixed(1)}s
                  </p>
                  <p className="text-[11px] text-text-muted">faturalı</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
