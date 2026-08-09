"use client";

import { CapacityNavTabs } from "@/components/capacity/CapacityNavTabs";
import { TeamCapacityGrid, type TeamMemberCapacityView } from "@/components/capacity/TeamCapacityGrid";
import { Select } from "@/components/ui/select";
import { StatCard } from "@/components/ui/stat-card";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  agencyApi,
  capacityApi,
  type AgencyMemberRead,
  type BrandRead,
  type TeamCapacityMember,
} from "@/lib/api-client";
import { canViewTeamCapacity, formatMinutesAsHours, getRangeForScale, type CapacityScale } from "@/lib/capacity";
import { cn } from "@/lib/utils";
import { ROLE_LABELS } from "@/lib/workspace";
import { AlertTriangle, CalendarClock, Clock, ListTodo, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const SCALE_OPTIONS: { value: CapacityScale; label: string }[] = [
  { value: "daily", label: "Günlük" },
  { value: "weekly", label: "Haftalık" },
  { value: "monthly", label: "Aylık" },
];

const STATUS_FILTER_OPTIONS = [
  { value: "all", label: "Tüm Durumlar" },
  { value: "available", label: "Müsait" },
  { value: "balanced", label: "Dengeli" },
  { value: "near_capacity", label: "Kapasiteye Yakın" },
  { value: "overloaded", label: "Aşırı Yüklenmiş" },
];

// Agencies in this niche SaaS are small — enriching the team grid with
// per-brand breakdowns is worth an N+1 (N = brand count) here, same trade-off
// the previous workload page made per-member. Capped for safety.
const MAX_BRANDS_FOR_ENRICHMENT = 30;

export default function CapacityTeamPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const role = activeAgency?.member_role ?? null;

  const [scale, setScale] = useState<CapacityScale>("weekly");
  const range = useMemo(() => getRangeForScale(scale), [scale]);

  const [members, setMembers] = useState<AgencyMemberRead[]>([]);
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [report, setReport] = useState<TeamCapacityMember[]>([]);
  const [brandsByUser, setBrandsByUser] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [roleFilter, setRoleFilter] = useState("all");
  const [brandFilter, setBrandFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const canViewTeam = canViewTeamCapacity(role);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const [mems, brandList, teamReport] = await Promise.all([
        agencyApi.listMembers(agencyId, accessToken),
        agencyApi.listBrands(agencyId, accessToken),
        capacityApi.getTeamReport(agencyId, accessToken, { start_date: range.start, end_date: range.end }),
      ]);
      setMembers(mems.filter((m) => m.status === "active"));
      setBrands(brandList);
      setReport(teamReport.members);

      if (brandList.length > 0 && brandList.length <= MAX_BRANDS_FOR_ENRICHMENT) {
        const brandReports = await Promise.all(
          brandList.map((b) =>
            capacityApi
              .getBrandReport(b.id, agencyId, accessToken, { start_date: range.start, end_date: range.end })
              .catch(() => null)
          )
        );
        const map: Record<string, string[]> = {};
        brandReports.forEach((br, idx) => {
          if (!br) return;
          const brandName = brandList[idx].name;
          br.by_user.forEach((u) => {
            if (u.planned_minutes <= 0) return;
            map[u.user_id] = [...(map[u.user_id] ?? []), brandName];
          });
        });
        setBrandsByUser(map);
      } else {
        setBrandsByUser({});
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, range.start, range.end]);

  useEffect(() => {
    if (!isInitialized || !canViewTeam) return;
    load();
  }, [isInitialized, canViewTeam, load]);

  const viewRows: TeamMemberCapacityView[] = useMemo(() => {
    if (members.length === 0 || report.length === 0) return [];
    const reportByUser = new Map(report.map((r) => [r.user_id, r]));
    return members
      .map((m) => {
        const r = reportByUser.get(m.user_id);
        if (!r) return null;
        return {
          ...r,
          name: m.user_full_name ?? m.user_email ?? "—",
          role: m.role,
          brandNames: brandsByUser[m.user_id] ?? [],
        };
      })
      .filter((v): v is TeamMemberCapacityView => v !== null);
  }, [members, report, brandsByUser]);

  const filteredRows = useMemo(() => {
    return viewRows.filter((r) => {
      if (roleFilter !== "all" && r.role !== roleFilter) return false;
      if (brandFilter !== "all" && !r.brandNames.includes(brandFilter)) return false;
      if (statusFilter !== "all" && r.planned_status !== statusFilter) return false;
      return true;
    });
  }, [viewRows, roleFilter, brandFilter, statusFilter]);

  const summary = useMemo(() => {
    const totalPlanned = viewRows.reduce((s, r) => s + r.planned_minutes, 0);
    const totalActual = viewRows.reduce((s, r) => s + r.actual_minutes, 0);
    const overloaded = viewRows.filter((r) => r.planned_status === "overloaded").length;
    return { totalPlanned, totalActual, overloaded };
  }, [viewRows]);

  if (isInitialized && !activeAgency) {
    return (
      <div className="p-8 max-w-5xl mx-auto flex flex-col items-center justify-center py-24 text-center">
        <p className="text-sm text-text-muted">Ajans bulunamadı.</p>
      </div>
    );
  }

  if (isInitialized && agencyId && !canViewTeam) {
    return (
      <div className="p-8 max-w-3xl mx-auto flex flex-col items-center justify-center py-24 text-center">
        <p className="text-sm font-medium text-text mb-1">Bu sayfayı görüntüleme yetkiniz yok</p>
        <p className="text-xs text-text-muted mb-4">Ekip kapasitesini görmek için yetkili bir rol gereklidir.</p>
        <Link href="/dashboard/capacity/schedule" className="text-sm text-accent hover:underline">
          Kendi kapasitenizi görüntüleyin →
        </Link>
      </div>
    );
  }

  if (!agencyId || !accessToken) return null;

  const roleOptions = [
    { value: "all", label: "Tüm Roller" },
    ...Array.from(new Set(viewRows.map((r) => r.role))).map((r) => ({ value: r, label: ROLE_LABELS[r] ?? r })),
  ];
  const brandOptions = [
    { value: "all", label: "Tüm Markalar" },
    ...brands.map((b) => ({ value: b.name, label: b.name })),
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <CapacityNavTabs />

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-text">Ekip Kapasitesi</h1>
          <p className="text-sm text-text-muted mt-1">
            {range.start === range.end
              ? `${range.start} tarihi için planlanan ve gerçekleşen iş yükü`
              : `${range.start} – ${range.end} aralığı için planlanan ve gerçekleşen iş yükü`}
          </p>
        </div>
        <div className="flex items-center gap-1 bg-surface-2 border border-border rounded-lg p-1">
          {SCALE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setScale(opt.value)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                scale === opt.value ? "bg-accent text-white" : "text-text-muted hover:text-text"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Ekip Üyesi" value={viewRows.length} icon={<Users className="w-4 h-4" />} loading={loading} />
        <StatCard
          label="Planlanan Süre"
          value={formatMinutesAsHours(summary.totalPlanned)}
          icon={<CalendarClock className="w-4 h-4" />}
          loading={loading}
        />
        <StatCard
          label="Gerçekleşen Süre"
          value={formatMinutesAsHours(summary.totalActual)}
          icon={<Clock className="w-4 h-4" />}
          loading={loading}
        />
        <StatCard
          label="Aşırı Yüklenmiş"
          value={summary.overloaded}
          icon={<AlertTriangle className="w-4 h-4" />}
          loading={loading}
        />
      </div>

      <div className="sticky top-0 z-10 bg-background/95 backdrop-blur border-b border-border py-3 mb-6 flex flex-wrap items-center gap-3">
        <Select options={roleOptions} value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="w-auto min-w-[140px]" />
        <Select options={brandOptions} value={brandFilter} onChange={(e) => setBrandFilter(e.target.value)} className="w-auto min-w-[140px]" />
        <Select
          options={STATUS_FILTER_OPTIONS}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="w-auto min-w-[160px]"
        />
        <Link
          href="/dashboard/capacity/unassigned"
          className="ml-auto inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline"
        >
          <ListTodo className="w-3.5 h-3.5" />
          Atanmamış İşler
        </Link>
      </div>

      {error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">{error}</div>
      ) : (
        <TeamCapacityGrid rows={filteredRows} loading={loading} />
      )}
    </div>
  );
}
