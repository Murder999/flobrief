"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  ownerApi, activityApi, briefApi, agencyApi, templateApi, dashboardApi,
  type OwnerDashboardStats, type ActivityLogRead, type BriefRead, type AgencyKPIStats,
} from "@/lib/api-client";
import { useEffect, useState, useCallback } from "react";
import { OnboardingChecklist, type OnboardingData } from "@/components/onboarding/onboarding-checklist";
import { cn } from "@/lib/utils";
import {
  Building2, Users, FileText, CheckCircle, Calendar,
  Plus, Mail, ChevronRight, Zap, AlertTriangle, TrendingUp,
  Package, RotateCcw, Clock, ListChecks,
} from "lucide-react";

// ── Skeleton ──────────────────────────────────────────────────────────────────

function StatSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 animate-pulse">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 bg-surface-2 rounded-xl flex-shrink-0" />
        <div className="flex-1">
          <div className="h-3 bg-surface-2 rounded w-24 mb-2.5" />
          <div className="h-7 bg-surface-2 rounded w-16 mb-1.5" />
          <div className="h-2.5 bg-surface-2 rounded w-20" />
        </div>
      </div>
    </div>
  );
}

function ActivitySkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 animate-pulse">
          <div className="w-7 h-7 rounded-full bg-surface-2 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="h-3 bg-surface-2 rounded w-3/4 mb-2" />
            <div className="h-2.5 bg-surface-2 rounded w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    brief_created: "brief oluşturdu",
    brief_updated: "brief güncelledi",
    brief_status_changed: "brief durumunu değiştirdi",
    brief_approved: "brief onayladı",
    brief_revision_requested: "revizyon istedi",
    member_invited: "üye davet etti",
    member_joined: "ajansa katıldı",
    brand_created: "marka oluşturdu",
    calendar_item_created: "takvim öğesi ekledi",
    calendar_item_updated: "takvim öğesini güncelledi",
  };
  return map[action] ?? action.replace(/_/g, " ");
}

function entityTypeLabel(entityType: string): string {
  const map: Record<string, string> = {
    brief: "Brief", brand: "Marka", calendar_item: "Takvim Öğesi",
    agency_member: "Ekip Üyesi", user: "Kullanıcı",
  };
  return map[entityType] ?? entityType;
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "az önce";
  if (minutes < 60) return `${minutes}dk önce`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}sa önce`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}g önce`;
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

function actorInitials(actor?: string | null): string {
  if (!actor) return "?";
  return actor.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

type LucideIcon = React.ComponentType<{ className?: string }>;

function StatCard({
  label, value, sub, icon: Icon, iconClass, href, alert,
}: {
  label: string;
  value: number | string;
  sub?: string;
  icon: LucideIcon;
  iconClass: string;
  href?: string;
  alert?: boolean;
}) {
  const content = (
    <div className={cn(
      "relative bg-surface border border-border rounded-xl p-5 overflow-hidden group transition-all duration-200",
      href && "hover:border-accent/30 hover:shadow-card-hover",
      alert && "border-red-500/30 bg-red-500/[0.03]",
    )}>
      <div className="absolute inset-0 bg-gradient-accent-subtle opacity-0 group-hover:opacity-100 transition-opacity" />
      <div className="relative flex items-start gap-3">
        <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-105", iconClass)}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-text-muted font-medium mb-1 tracking-wide">{label}</p>
          <p className={cn(
            "text-2xl font-bold leading-tight tracking-tight",
            alert && typeof value === "number" && value > 0 ? "text-red-400" : "text-text",
          )}>
            {typeof value === "number" ? value.toLocaleString("tr-TR") : value}
          </p>
          {sub && <p className="text-xs text-text-muted mt-0.5">{sub}</p>}
        </div>
        {href && (
          <ChevronRight className="w-4 h-4 text-text-muted/40 group-hover:text-accent group-hover:translate-x-0.5 transition-all flex-shrink-0 mt-1" />
        )}
      </div>
    </div>
  );

  return href ? <Link href={href}>{content}</Link> : content;
}

// ── KPI Card (compact) ────────────────────────────────────────────────────────

function KpiCard({ label, value, icon: Icon, color, href }: {
  label: string;
  value: number;
  icon: LucideIcon;
  color: string;
  href?: string;
}) {
  const inner = (
    <div className={cn(
      "flex items-center gap-3 p-4 bg-surface border border-border rounded-xl transition-all duration-200",
      href && "hover:border-accent/20 hover:shadow-sm cursor-pointer",
    )}>
      <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0", color)}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] text-text-muted leading-tight mb-0.5">{label}</p>
        <p className="text-lg font-bold text-text tracking-tight">{value.toLocaleString("tr-TR")}</p>
      </div>
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

// ── Quick Action ──────────────────────────────────────────────────────────────

function QuickAction({ label, href, icon: Icon, iconClass }: {
  label: string;
  href: string;
  icon: LucideIcon;
  iconClass: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-text-secondary hover:text-text hover:bg-hover transition-all group"
    >
      <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-105", iconClass)}>
        <Icon className="w-4 h-4" />
      </div>
      <span className="flex-1">{label}</span>
      <ChevronRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
    </Link>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user, accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();

  const [stats, setStats] = useState<OwnerDashboardStats | null>(null);
  const [kpis, setKpis] = useState<AgencyKPIStats | null>(null);
  const [activity, setActivity] = useState<ActivityLogRead[] | null>(null);
  const [pendingBriefs, setPendingBriefs] = useState<BriefRead[] | null>(null);
  const [statsError, setStatsError] = useState(false);
  const [onboardingData, setOnboardingData] = useState<OnboardingData | null>(null);

  const loadData = useCallback(async () => {
    if (!accessToken || !activeAgency?.id) return;
    const agencyId = activeAgency.id;

    ownerApi.dashboard(agencyId, accessToken).then(setStats).catch(() => setStatsError(true));
    dashboardApi.agencyKpis(agencyId, accessToken).then(setKpis).catch(() => null);
    activityApi.list(agencyId, accessToken, { limit: 6 }).then((res) => setActivity(res.items)).catch(() => setActivity([]));
    briefApi.list({ status: "in_review", limit: 5 }, agencyId, accessToken).then((res) => setPendingBriefs(res.items)).catch(() => setPendingBriefs([]));

    Promise.all([
      agencyApi.listBrands(agencyId, accessToken).catch(() => []),
      agencyApi.listMembers(agencyId, accessToken).catch(() => []),
      briefApi.list({ limit: 1 }, agencyId, accessToken).catch(() => ({ items: [] })),
      templateApi.list(agencyId, accessToken).catch(() => []),
    ]).then(([brands, members, briefsRes, templates]) => {
      setOnboardingData({
        hasAgencyName: Boolean(activeAgency.name),
        hasBrand: Array.isArray(brands) && brands.length > 0,
        hasMember: Array.isArray(members) && members.length > 1,
        hasTemplate: Array.isArray(templates) && templates.length > 0,
        hasBrief: Array.isArray((briefsRes as { items: unknown[] }).items) && (briefsRes as { items: unknown[] }).items.length > 0,
      });
    });
  }, [accessToken, activeAgency?.id, activeAgency?.name]);

  useEffect(() => {
    if (!isInitialized) return;
    loadData();
  }, [isInitialized, loadData]);

  const firstName = user?.full_name?.split(" ")[0] ?? "Merhaba";
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Günaydın" : hour < 18 ? "İyi günler" : "İyi akşamlar";

  if (isInitialized && !activeAgency) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-16 h-16 bg-accent/10 rounded-2xl flex items-center justify-center mb-4">
            <Building2 className="w-8 h-8 text-accent" />
          </div>
          <h2 className="text-xl font-semibold text-text mb-2">Ajans Bulunamadı</h2>
          <p className="text-sm text-text-muted max-w-sm">
            Henüz bir ajansa üye değilsiniz. Davet bekliyorsanız e-postanızı kontrol edin.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-background">
      {/* Page header */}
      <div className="border-b border-border bg-surface px-4 sm:px-8 py-6 mb-0">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-heading-lg text-text">
            {greeting}, {firstName}
          </h1>
          <p className="mt-0.5 text-sm text-text-secondary">
            {activeAgency?.name} ajansının güncel durumu.
          </p>
        </div>
      </div>
    <div className="p-4 sm:p-8 max-w-7xl mx-auto">

      {/* Onboarding */}
      {onboardingData && <OnboardingChecklist data={onboardingData} />}

      {/* Top stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {!stats || statsError ? (
          <>
            <StatSkeleton /><StatSkeleton /><StatSkeleton /><StatSkeleton />
          </>
        ) : (
          <>
            <StatCard label="Aktif Markalar" value={stats.active_brands} icon={Building2} iconClass="bg-accent-subtle text-accent" href="/dashboard/brands" />
            <StatCard label="Aktif Üyeler" value={stats.active_members} icon={Users} iconClass="bg-success-subtle text-success" href="/dashboard/settings/members" />
            <StatCard label="Açık Brief'ler" value={stats.open_briefs} sub="Taslak veya incelemede" icon={FileText} iconClass="bg-warning-subtle text-warning" href="/dashboard/briefs" />
            <StatCard label="Onay Bekleyen" value={pendingBriefs?.length ?? 0} sub="İncelemede" icon={CheckCircle} iconClass="bg-purple-subtle text-purple" href="/dashboard/briefs?status=in_review" />
          </>
        )}
      </div>

      {/* KPI section */}
      {kpis ? (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-text">Operasyon KPI&apos;ları</h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <KpiCard label="Brief Onay Bekliyor" value={kpis.pending_briefs} icon={Clock} color="bg-warning-subtle text-warning" href="/dashboard/briefs?status=submitted" />
            <KpiCard label="Kabul Edildi" value={kpis.accepted_briefs} icon={CheckCircle} color="bg-success-subtle text-success" href="/dashboard/briefs?status=accepted" />
            <KpiCard label="Üretimde" value={kpis.in_production_briefs} icon={Package} color="bg-purple-subtle text-purple" href="/dashboard/briefs?status=in_production" />
            <KpiCard label="Teslimat Bekliyor" value={kpis.pending_deliverables} icon={FileText} color="bg-info-subtle text-info" />
            <KpiCard label="Revizyon Bekleniyor" value={kpis.revision_requested_deliverables} icon={RotateCcw} color="bg-danger-subtle text-danger" />
            <KpiCard label="Geciken İş" value={kpis.overdue_briefs} icon={AlertTriangle} color={kpis.overdue_briefs > 0 ? "bg-danger-subtle text-danger" : "bg-surface-2 text-text-muted"} />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
            <KpiCard label="Bu Ay Tamamlanan" value={kpis.completed_this_month} icon={CheckCircle} color="bg-success-subtle text-success" />
            <KpiCard label="Bu Ay Onaylanan" value={kpis.approved_this_month} icon={TrendingUp} color="bg-accent-subtle text-accent" />
            <KpiCard label="Açık Görevler" value={kpis.open_tasks} icon={ListChecks} color="bg-purple-subtle text-purple" />
            <KpiCard label="Geciken Görevler" value={kpis.overdue_tasks} icon={AlertTriangle} color={kpis.overdue_tasks > 0 ? "bg-danger-subtle text-danger" : "bg-surface-2 text-text-muted"} />
          </div>
        </div>
      ) : (
        <div className="mb-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-[72px] bg-surface border border-border rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Main 2-col grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity */}
        <div className="lg:col-span-2 bg-surface border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-accent" />
              <h2 className="font-semibold text-text text-sm">Son Aktivite</h2>
            </div>
            <Link href="/dashboard/activity" className="text-xs text-text-muted hover:text-accent transition-colors">
              Tümünü gör →
            </Link>
          </div>

          {activity === null ? (
            <ActivitySkeleton />
          ) : activity.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="w-12 h-12 bg-surface-2 rounded-xl flex items-center justify-center mb-3">
                <Zap className="w-6 h-6 text-text-muted/40" />
              </div>
              <p className="text-sm font-medium text-text mb-1">Henüz aktivite yok</p>
              <p className="text-xs text-text-muted">İlk briefinizi oluşturun ve iş akışınızı başlatın.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {activity.map((log) => {
                const actorName = (log.meta as Record<string, unknown>)?.actor_name as string | undefined;
                return (
                  <div key={log.id} className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ring-1 ring-accent/20"
                      style={{ background: "var(--gradient-accent-subtle)" }}>
                      <span className="text-[10px] font-bold text-accent">
                        {actorInitials(actorName)}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text">
                        <span className="font-medium">{actorName ?? "Birisi"}</span>{" "}
                        {actionLabel(log.action)}{" "}
                        <span className="text-text-muted text-xs">({entityTypeLabel(log.entity_type)})</span>
                      </p>
                      <p className="text-xs text-text-muted mt-0.5">{formatRelativeTime(log.created_at)}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right col */}
        <div className="space-y-4">
          {/* Quick Actions */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <h2 className="font-semibold text-text text-sm mb-3">Hızlı İşlemler</h2>
            <div className="space-y-0.5">
              <QuickAction label="Yeni Brief Oluştur" href="/dashboard/briefs/new" icon={Plus} iconClass="bg-accent/12 text-accent" />
              <QuickAction label="Marka Ekle" href="/dashboard/brands" icon={Building2} iconClass="bg-emerald-500/12 text-emerald-400" />
              <QuickAction label="Takvimi Görüntüle" href="/dashboard/calendar" icon={Calendar} iconClass="bg-violet-500/12 text-violet-400" />
              <QuickAction label="Ekip Davet Et" href="/dashboard/settings/members" icon={Mail} iconClass="bg-amber-500/12 text-amber-400" />
            </div>
          </div>

          {/* Pending Approvals */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-text text-sm">Onay Bekleyen</h2>
              {pendingBriefs && pendingBriefs.length > 0 && (
                <span className="text-xs bg-accent/10 text-accent px-2 py-0.5 rounded-full font-medium ring-1 ring-accent/15">
                  {pendingBriefs.length}
                </span>
              )}
            </div>
            {pendingBriefs === null ? (
              <div className="space-y-2 animate-pulse">
                {[1, 2].map((i) => <div key={i} className="h-12 bg-surface-2 rounded-lg" />)}
              </div>
            ) : pendingBriefs.length === 0 ? (
              <p className="text-xs text-text-muted py-4 text-center">Onay bekleyen brief yok.</p>
            ) : (
              <div className="space-y-1">
                {pendingBriefs.map((brief) => (
                  <Link
                    key={brief.id}
                    href={`/dashboard/briefs/${brief.id}`}
                    className="flex items-center gap-2.5 p-2.5 rounded-lg hover:bg-hover transition-colors group"
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-text truncate">{brief.title}</p>
                      {brief.deadline && (
                        <p className="text-[10px] text-text-muted">
                          Son: {new Date(brief.deadline).toLocaleDateString("tr-TR")}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="w-3 h-3 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Calendar stat */}
          {stats && (
            <div className="relative bg-gradient-to-br from-accent/10 to-violet-500/5 border border-accent/15 rounded-xl p-5 overflow-hidden">
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
              <div className="flex items-center gap-2 mb-2">
                <Calendar className="w-4 h-4 text-accent" />
                <span className="text-sm font-medium text-accent">Bu Ay Takvim</span>
              </div>
              <p className="text-3xl font-bold text-text tracking-tight">
                {stats.calendar_items_this_month.toLocaleString("tr-TR")}
              </p>
              <p className="text-xs text-text-muted mt-0.5 mb-3">planlanan içerik</p>
              <Link href="/dashboard/calendar" className="text-xs text-accent hover:underline">
                Takvimi gör →
              </Link>
            </div>
          )}

          {/* Deliverable stats */}
          {kpis && (
            <div className="bg-surface border border-border rounded-xl p-5">
              <h2 className="font-semibold text-text text-sm mb-3">Teslimat Özeti</h2>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted text-xs">Sunulan Toplam</span>
                  <span className="font-semibold text-text">{kpis.total_deliverables_submitted.toLocaleString("tr-TR")}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted text-xs">Onaylanan</span>
                  <span className="font-semibold text-emerald-400">{kpis.total_deliverables_approved.toLocaleString("tr-TR")}</span>
                </div>
                {kpis.total_deliverables_submitted > 0 && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-text-muted">Onay oranı</span>
                      <span className="text-[10px] text-text-muted font-medium">
                        {Math.round((kpis.total_deliverables_approved / kpis.total_deliverables_submitted) * 100)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full transition-all"
                        style={{ width: `${Math.round((kpis.total_deliverables_approved / kpis.total_deliverables_submitted) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  );
}
