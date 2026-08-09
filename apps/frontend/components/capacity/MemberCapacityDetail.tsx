"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/ui/stat-card";
import { TimeCategoryBadge } from "@/components/time-tracking/TimeCategoryBadge";
import {
  ApiError,
  briefApi,
  capacityApi,
  type TimeOffRead,
  type UserCapacityReport,
  type WorkAllocationRead,
  type WorkScheduleRead,
} from "@/lib/api-client";
import { formatMinutesAsHours, TIME_OFF_TYPE_LABEL, WEEKDAY_LABELS } from "@/lib/capacity";
import { CalendarClock, Clock, Gauge, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CapacityStatusBadge } from "./CapacityStatusBadge";

interface MemberCapacityDetailProps {
  userId: string;
  userName: string;
  agencyId: string;
  accessToken: string;
  startDate: string;
  endDate: string;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" });
}

function timeOffStatusBadgeClass(status: string): string {
  if (status === "approved") return "status-success";
  if (status === "rejected") return "status-danger";
  return "status-warning";
}

function timeOffStatusLabel(status: string): string {
  if (status === "approved") return "Onaylandı";
  if (status === "rejected") return "Reddedildi";
  return "Bekliyor";
}

/** Member drill-down body: schedule, time-off, and brief-level allocation
 * breakdown for one user over one date range. Self-fetches so it can be
 * dropped into the `[userId]` page or reused inside a drawer later. */
export function MemberCapacityDetail({
  userId,
  userName,
  agencyId,
  accessToken,
  startDate,
  endDate,
}: MemberCapacityDetailProps) {
  const [report, setReport] = useState<UserCapacityReport | null>(null);
  const [schedule, setSchedule] = useState<WorkScheduleRead | null>(null);
  const [timeOff, setTimeOff] = useState<TimeOffRead[] | null>(null);
  const [allocations, setAllocations] = useState<WorkAllocationRead[] | null>(null);
  const [briefTitles, setBriefTitles] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [reportRes, timeOffRes, allocationsRes] = await Promise.all([
        capacityApi.getUserReport(userId, agencyId, accessToken, {
          start_date: startDate,
          end_date: endDate,
        }),
        capacityApi.listTimeOff(userId, agencyId, accessToken, { start: startDate, end: endDate }),
        capacityApi.listAllocations(userId, agencyId, accessToken, { start: startDate, end: endDate }),
      ]);
      setReport(reportRes);
      setTimeOff(timeOffRes);
      setAllocations(allocationsRes);

      try {
        const scheduleRes = await capacityApi.getSchedule(userId, agencyId, accessToken);
        setSchedule(scheduleRes);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setSchedule(null);
        } else {
          throw e;
        }
      }

      const briefIds = Array.from(
        new Set(allocationsRes.map((a) => a.brief_id).filter((v): v is string => !!v))
      );
      const titles = await Promise.all(
        briefIds.map((id) =>
          briefApi
            .get(id, agencyId, accessToken)
            .then((b) => [id, b.title] as const)
            .catch(() => [id, null] as const)
        )
      );
      setBriefTitles(
        Object.fromEntries(titles.filter((t): t is [string, string] => t[1] !== null))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [userId, agencyId, accessToken, startDate, endDate]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatCard key={i} label="" value="" loading />
          ))}
        </div>
        <div className="h-40 bg-surface-2 rounded-xl animate-pulse" />
        <div className="h-40 bg-surface-2 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
        {error ?? "Kapasite verileri yüklenemedi."}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Net Kapasite"
          value={report.capacity_status_reason === "ok" ? formatMinutesAsHours(report.net_capacity_minutes) : "—"}
          icon={<Gauge className="w-4 h-4" />}
        />
        <StatCard
          label="Planlanan"
          value={`${formatMinutesAsHours(report.planned_minutes)} · %${report.planned_utilization_pct}`}
          icon={<CalendarClock className="w-4 h-4" />}
        />
        <StatCard
          label="Gerçekleşen"
          value={`${formatMinutesAsHours(report.actual_minutes)} · %${report.actual_utilization_pct}`}
          icon={<Clock className="w-4 h-4" />}
        />
        <StatCard
          label="Durum"
          value={<CapacityStatusBadge status={report.planned_status} reason={report.capacity_status_reason} />}
          icon={<TrendingUp className="w-4 h-4" />}
        />
      </div>

      {report.open_timer_minutes > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success">
          <Clock className="w-4 h-4 flex-shrink-0" />
          Şu anda açık bir zamanlayıcı var — bu dönem için {formatMinutesAsHours(report.open_timer_minutes)} henüz
          kapatılmadı.
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Çalışma Programı</CardTitle>
        </CardHeader>
        <CardContent>
          {!schedule ? (
            <p className="text-sm text-text-muted">{userName} için henüz bir çalışma programı tanımlanmamış.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
              {WEEKDAY_LABELS.map((label, weekday) => {
                const day = schedule.days.find((d) => d.weekday === weekday);
                return (
                  <div key={weekday} className="bg-surface-2 rounded-lg p-2.5 text-center">
                    <p className="text-[10px] text-text-muted mb-1">{label.slice(0, 3)}</p>
                    <p className="text-sm font-semibold text-text tabular-nums">
                      {day && day.is_working_day ? formatMinutesAsHours(day.capacity_minutes) : "—"}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>İzinler</CardTitle>
        </CardHeader>
        <CardContent>
          {!timeOff || timeOff.length === 0 ? (
            <p className="text-sm text-text-muted">Bu dönemde izin kaydı yok.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {timeOff.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center justify-between gap-3 bg-surface-2 rounded-lg px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-text">{TIME_OFF_TYPE_LABEL[t.type] ?? t.type}</p>
                    <p className="text-xs text-text-muted">
                      {fmtDate(t.start_at)} – {fmtDate(t.end_at)}
                    </p>
                  </div>
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${timeOffStatusBadgeClass(t.status)}`}
                  >
                    {timeOffStatusLabel(t.status)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Brief Bazlı Atamalar</CardTitle>
        </CardHeader>
        <CardContent>
          {!allocations || allocations.length === 0 ? (
            <p className="text-sm text-text-muted">Bu dönemde manuel atama yok.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {allocations.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between gap-3 bg-surface-2 rounded-lg px-3 py-2.5"
                >
                  <div className="min-w-0">
                    {a.brief_id ? (
                      <Link
                        href={`/dashboard/briefs/${a.brief_id}`}
                        className="text-sm text-text hover:text-accent hover:underline truncate"
                      >
                        {briefTitles[a.brief_id] ?? "Brief"}
                      </Link>
                    ) : (
                      <p className="text-sm text-text">Genel kapasite bloğu</p>
                    )}
                    <p className="text-xs text-text-muted">
                      {fmtDate(a.start_date)} – {fmtDate(a.end_date)}
                      {a.locked && " · Kilitli"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {a.category && <TimeCategoryBadge category={a.category} />}
                    <span className="text-sm font-semibold text-text tabular-nums">
                      {formatMinutesAsHours(a.allocated_minutes)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
