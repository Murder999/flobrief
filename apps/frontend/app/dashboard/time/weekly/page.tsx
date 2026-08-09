"use client";

import { WeeklyTimesheetGrid } from "@/components/time-tracking/WeeklyTimesheetGrid";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { timeReportApi, type WeeklyTimesheetResponse } from "@/lib/api-client";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

function mondayOf(d: Date): Date {
  const copy = new Date(d);
  const day = copy.getDay(); // 0 = Sunday
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function toIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function WeeklyTimesheetPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [data, setData] = useState<WeeklyTimesheetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekStart.getDate() + 6);
      const result = await timeReportApi.getWeekly(agencyId, accessToken, {
        start_date: toIso(weekStart),
        end_date: toIso(weekEnd),
      });
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, weekStart]);

  useEffect(() => {
    load();
  }, [load]);

  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);

  if (!agencyId) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setWeekStart((w) => new Date(w.getFullYear(), w.getMonth(), w.getDate() - 7))}
            className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-hover transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm font-medium text-text">
            {weekStart.toLocaleDateString("tr-TR", { day: "numeric", month: "short" })} –{" "}
            {weekEnd.toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" })}
          </span>
          <button
            onClick={() => setWeekStart((w) => new Date(w.getFullYear(), w.getMonth(), w.getDate() + 7))}
            className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-hover transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
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
      </div>

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : loading || !data ? (
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-40 bg-surface-2 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <WeeklyTimesheetGrid weekStart={weekStart} byDay={data.by_day} entries={data.entries} />
      )}
    </div>
  );
}
