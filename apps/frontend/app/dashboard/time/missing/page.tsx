"use client";

import { DateRangeFilter } from "@/components/time-tracking/DateRangeFilter";
import { useDateRangeFilter } from "@/hooks/useDateRangeFilter";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { timeReportApi, type MissingTimesheetResponse } from "@/lib/api-client";
import { AlertTriangle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" });
}

export default function MissingTimesheetPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const dateRange = useDateRangeFilter();

  const [data, setData] = useState<MissingTimesheetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await timeReportApi.getMissing(agencyId, accessToken, dateRange.apiParams);
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

  if (!agencyId) return null;

  return (
    <div>
      <DateRangeFilter
        value={dateRange}
        onPresetChange={dateRange.setPreset}
        onCustomChange={dateRange.setCustomDates}
        onClear={dateRange.clear}
      />

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : loading || !data ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 bg-surface-2 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : data.missing.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-sm font-medium text-text mb-1">Eksik zaman kaydı yok</p>
          <p className="text-xs text-text-muted">
            {dateRange.start && dateRange.end
              ? `${dateRange.start} – ${dateRange.end} aralığında herkes zaman kaydını girmiş.`
              : "Bu dönemde herkes zaman kaydını girmiş."}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {data.missing.map((m, i) => (
            <div
              key={`${m.user_id}-${m.missing_date}-${i}`}
              className="bg-surface border border-border rounded-xl p-4 flex items-center gap-3"
            >
              <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-text">{m.user_name}</p>
                <p className="text-xs text-text-muted">{fmtDate(m.missing_date)} için kayıt yok</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
