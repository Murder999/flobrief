"use client";

import { useAuth } from "@/hooks/useAuth";
import {
  brandPortalApi,
  type BriefRead,
  type BrandCalendarEntry,
  type BrandKPIStats,
  type BrandTeamUsage,
  type NotificationRead,
} from "@/lib/api-client";
import { useEffect, useState, useCallback, useRef } from "react";
import { KpiCards } from "@/components/brand-dashboard/KpiCards";
import { ActionQueueCard } from "@/components/brand-dashboard/ActionQueueCard";
import { WeekCalendarCard } from "@/components/brand-dashboard/WeekCalendarCard";
import { RecentBriefsCard } from "@/components/brand-dashboard/RecentBriefsCard";
import { RecentActivityCard } from "@/components/brand-dashboard/RecentActivityCard";
import { OperationsPanel } from "@/components/brand-dashboard/OperationsPanel";
import { greetingFor, startOfWeekISO, endOfWeekISO, countPendingApproval, countOverdue } from "@/components/brand-dashboard/shared";

export default function BrandDashboardPage() {
  const { user, accessToken } = useAuth();
  const [briefs, setBriefs] = useState<BriefRead[] | null>(null);
  const [kpis, setKpis] = useState<BrandKPIStats | null>(null);
  const [error, setError] = useState(false);
  const [teamUsage, setTeamUsage] = useState<BrandTeamUsage | null>(null);
  const [weekCalendar, setWeekCalendar] = useState<BrandCalendarEntry[] | null>(null);
  const [recentActivity, setRecentActivity] = useState<NotificationRead[] | null>(null);
  const actionQueueRef = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async () => {
    if (!accessToken) return;
    try {
      const res = await brandPortalApi.listBriefs(accessToken, { limit: 100 });
      setBriefs(res.items);
      setError(false);
    } catch {
      setError(true);
      setBriefs([]);
    }
    brandPortalApi.kpis(accessToken).then(setKpis).catch(() => null);
    brandPortalApi.getTeamUsage(accessToken).then(setTeamUsage).catch(() => setTeamUsage(null));
    brandPortalApi
      .listCalendar(accessToken, { from: startOfWeekISO(), to: endOfWeekISO() })
      .then(setWeekCalendar)
      .catch(() => setWeekCalendar([]));
    brandPortalApi
      .listNotifications(accessToken, { limit: 5 })
      .then((r) => setRecentActivity(r.items))
      .catch(() => setRecentActivity([]));
  }, [accessToken]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleMarkRead = useCallback(
    async (id: string) => {
      if (!accessToken) return;
      const updated = await brandPortalApi.markNotificationRead(id, accessToken);
      setRecentActivity((prev) => prev?.map((n) => (n.id === id ? updated : n)) ?? prev);
    },
    [accessToken]
  );

  const firstName = user?.full_name?.split(" ")[0] ?? "";
  const greeting = greetingFor(new Date());

  const pendingApprovalCount = kpis && briefs ? countPendingApproval(kpis, briefs) : 0;
  const overdueCount = briefs ? countOverdue(briefs) : 0;
  const hasFocusItems = pendingApprovalCount > 0 || overdueCount > 0;

  const scrollToActions = () => actionQueueRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="mx-auto max-w-[1560px] px-6 py-6">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-text">
          {greeting}{firstName ? `, ${firstName}` : ""}
        </h1>
        {kpis && briefs ? (
          hasFocusItems ? (
            <button
              onClick={scrollToActions}
              className="mt-1 text-[13px] text-text-secondary hover:text-accent transition-colors"
            >
              Bugün{" "}
              <span className="font-semibold text-text">
                {pendingApprovalCount + overdueCount} aksiyonunuz
              </span>{" "}
              var
              {pendingApprovalCount > 0 && <> · <span className="text-amber-500 font-medium">{pendingApprovalCount} onay</span></>}
              {overdueCount > 0 && <> · <span className="text-danger font-medium">{overdueCount} gecikme</span></>}
            </button>
          ) : (
            <p className="mt-1 text-[13px] text-text-secondary">Bekleyen aksiyonunuz yok, tüm süreçler güncel.</p>
          )
        ) : (
          <p className="mt-1 text-[13px] text-text-secondary">Brief durumlarınız ve bekleyen aksiyonlar aşağıda.</p>
        )}
      </div>

      {/* KPI row */}
      <div className="mb-5">
        <KpiCards kpis={kpis} briefs={briefs} />
      </div>

      {/* Main grid: 9 col content + 3 col operations panel */}
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 lg:col-span-9 space-y-5">
          <div ref={actionQueueRef} className="grid grid-cols-1 md:grid-cols-2 gap-5 scroll-mt-6">
            <ActionQueueCard briefs={briefs} />
            <WeekCalendarCard entries={weekCalendar} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <RecentBriefsCard briefs={briefs} error={error} onRetry={loadData} />
            <RecentActivityCard notifications={recentActivity} onMarkRead={handleMarkRead} />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-3">
          <OperationsPanel
            teamUsage={teamUsage}
            pendingApprovalCount={pendingApprovalCount}
            overdueCount={overdueCount}
            approvedDeliverables={kpis?.approved_deliverables ?? 0}
            pendingDeliverables={kpis?.pending_deliverables ?? 0}
          />
        </div>
      </div>
    </div>
  );
}
