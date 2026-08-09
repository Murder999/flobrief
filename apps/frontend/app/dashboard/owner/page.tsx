"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { ownerApi, activityApi, type OwnerDashboardStats, type OwnerSubscriptionRead, type ActivityLogRead } from "@/lib/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "az önce";
  if (minutes < 60) return `${minutes}dk önce`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}sa önce`;
  const days = Math.floor(hours / 24);
  return days < 7
    ? `${days}g önce`
    : new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

function actorInitials(meta: Record<string, unknown> | null): string {
  const name = meta?.actor_name as string | undefined;
  if (!name) return "?";
  return name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
}

function actorName(meta: Record<string, unknown> | null): string {
  return (meta?.actor_name as string | undefined) ?? "Birisi";
}

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

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  icon,
  href,
}: {
  label: string;
  value: number;
  sub?: string;
  icon: React.ReactNode;
  href?: string;
}) {
  const inner = (
    <div className="bg-surface border border-border rounded-xl p-5 flex items-start gap-4 hover:border-border-hover transition-colors">
      <div className="w-11 h-11 bg-surface-2 rounded-xl flex items-center justify-center flex-shrink-0">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-text-muted font-medium mb-1">{label}</p>
        <p className="text-2xl font-bold text-text leading-none">{value.toLocaleString("tr-TR")}</p>
        {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
      </div>
    </div>
  );
  if (href) return <Link href={href}>{inner}</Link>;
  return inner;
}

function SkeletonStatCard() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex items-start gap-4 animate-pulse">
      <div className="w-11 h-11 bg-surface-2 rounded-xl flex-shrink-0" />
      <div className="flex-1">
        <div className="h-3 bg-surface-2 rounded w-24 mb-2" />
        <div className="h-7 bg-surface-2 rounded w-14" />
      </div>
    </div>
  );
}

// ── Quick Link Card ───────────────────────────────────────────────────────────

function QuickLinkCard({
  href,
  label,
  description,
  iconPath,
  iconColor,
}: {
  href: string;
  label: string;
  description: string;
  iconPath: string | string[];
  iconColor: string;
}) {
  return (
    <Link
      href={href}
      className="bg-surface border border-border rounded-xl p-5 hover:border-border-hover hover:shadow-card-hover transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconColor}`}>
          <svg className="w-4.5 h-4.5 w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            {Array.isArray(iconPath) ? (
              iconPath.map((d, i) => (
                <path key={i} strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={d} />
              ))
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={iconPath} />
            )}
          </svg>
        </div>
        <svg className="w-4 h-4 text-text-muted group-hover:text-accent transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
      <h3 className="text-sm font-semibold text-text mb-1">{label}</h3>
      <p className="text-xs text-text-muted">{description}</p>
    </Link>
  );
}

// ── Subscription Status Badge ─────────────────────────────────────────────────

const SUB_STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "Aktif", cls: "bg-success/10 text-success" },
  trial: { label: "Deneme", cls: "bg-warning/10 text-warning" },
  cancelled: { label: "İptal Edildi", cls: "bg-danger/10 text-danger" },
  past_due: { label: "Ödeme Gecikti", cls: "bg-danger/10 text-danger" },
  suspended: { label: "Askıda", cls: "bg-surface-2 text-text-muted" },
};

// ── Main Component ─────────────────────────────────────────────────────────────

export default function OwnerDashboardPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const router = useRouter();

  const [stats, setStats] = useState<OwnerDashboardStats | null>(null);
  const [subscription, setSubscription] = useState<OwnerSubscriptionRead | null>(null);
  const [activity, setActivity] = useState<ActivityLogRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isInitialized) return;
    if (activeAgency && activeAgency.member_role !== "owner") {
      router.replace("/dashboard");
      return;
    }
    if (!accessToken || !activeAgency?.id) return;

    const agencyId = activeAgency.id;

    ownerApi
      .dashboard(agencyId, accessToken)
      .then(setStats)
      .catch(() => setError("İstatistikler yüklenirken hata oluştu."));

    ownerApi
      .subscription(agencyId, accessToken)
      .then(setSubscription)
      .catch(() => {/* non-critical */});

    activityApi
      .list(agencyId, accessToken, { limit: 5 })
      .then((res) => setActivity(res.items))
      .catch(() => setActivity([]));
  }, [accessToken, activeAgency, isInitialized, router]);

  const sub = subscription;
  const subStatus = SUB_STATUS[sub?.status ?? ""] ?? { label: sub?.status ?? "—", cls: "bg-surface-2 text-text-muted" };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text">Sahip Paneli</h1>
        <p className="text-sm text-text-muted mt-1">
          {activeAgency?.name} ajansının yönetim merkezi.
        </p>
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 bg-danger/10 border border-danger/20 rounded-xl text-sm text-danger">
          {error}
        </div>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        {stats === null ? (
          <>
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
          </>
        ) : (
          <>
            <StatCard
              label="Aktif Markalar"
              value={stats.active_brands}
              icon={
                <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              }
              href="/dashboard/brands"
            />
            <StatCard
              label="Aktif Üyeler"
              value={stats.active_members}
              icon={
                <svg className="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              }
              href="/dashboard/owner/members"
            />
            <StatCard
              label="Açık Brief'ler"
              value={stats.open_briefs}
              sub="Taslak veya incelemede"
              icon={
                <svg className="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              }
              href="/dashboard/briefs"
            />
            <StatCard
              label="Onaylı Brief'ler"
              value={stats.approved_briefs_total}
              sub="Toplam onaylı"
              icon={
                <svg className="w-5 h-5 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
            />
            <StatCard
              label="Bu Ay Takvim"
              value={stats.calendar_items_this_month}
              sub="Planlanan içerikler"
              icon={
                <svg className="w-5 h-5 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              }
              href="/dashboard/calendar"
            />
          </>
        )}
      </div>

      {/* Middle grid: subscription + activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Subscription card */}
        <div className="bg-surface border border-border rounded-xl p-6">
          <h3 className="font-semibold text-text mb-4">Abonelik Durumu</h3>
          {sub ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-muted">Plan</span>
                <span className="text-sm font-semibold text-text">{sub.plan_name}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-muted">Durum</span>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${subStatus.cls}`}>
                  {subStatus.label}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-muted">Yenileme Tarihi</span>
                <span className="text-sm text-text">{formatDate(sub.current_period_end)}</span>
              </div>
              {sub.max_users !== null && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-text-muted">Kullanıcı Kullanımı</span>
                    <span className="text-xs text-text-muted">{sub.active_members} / {sub.max_users}</span>
                  </div>
                  <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full transition-all"
                      style={{ width: `${Math.min(100, (sub.active_members / sub.max_users) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
              {sub.max_brands !== null && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-text-muted">Marka Kullanımı</span>
                    <span className="text-xs text-text-muted">{sub.active_brands} / {sub.max_brands}</span>
                  </div>
                  <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (sub.active_brands / sub.max_brands) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
              <div className="pt-2">
                <Link
                  href="/dashboard/settings/billing"
                  className="text-xs text-accent hover:underline"
                >
                  Planı yönet &rarr;
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-3 animate-pulse">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="h-3 bg-surface-2 rounded w-24" />
                  <div className="h-3 bg-surface-2 rounded w-28" />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="bg-surface border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-text">Son Aktivite</h3>
            <Link href="/dashboard/activity" className="text-xs text-accent hover:underline">
              Tümünü gör
            </Link>
          </div>
          {activity === null ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-start gap-3 animate-pulse">
                  <div className="w-7 h-7 rounded-full bg-surface-2 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="h-3 bg-surface-2 rounded w-3/4 mb-1.5" />
                    <div className="h-2.5 bg-surface-2 rounded w-1/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : activity.length === 0 ? (
            <p className="text-sm text-text-muted text-center py-6">Henüz aktivite yok.</p>
          ) : (
            <div className="space-y-3">
              {activity.map((log) => (
                <div key={log.id} className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-[10px] font-bold text-accent">
                      {actorInitials(log.meta)}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text">
                      <span className="font-medium">{actorName(log.meta)}</span>{" "}
                      {actionLabel(log.action)}
                    </p>
                    <p className="text-xs text-text-muted mt-0.5">
                      {formatRelativeTime(log.created_at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Links Grid */}
      <div>
        <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Hızlı Bağlantılar</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <QuickLinkCard
            href="/dashboard/owner/members"
            label="Üye Yönetimi"
            description="Ekip üyelerini görüntüle ve yönet."
            iconPath="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
            iconColor="bg-accent/10 text-accent"
          />
          <QuickLinkCard
            href="/dashboard/settings/billing"
            label="Faturalama"
            description="Abonelik ve ödeme geçmişini görüntüle."
            iconPath="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
            iconColor="bg-emerald-500/10 text-emerald-500"
          />
          <QuickLinkCard
            href="/dashboard/settings/branding"
            label="Marka Ayarları"
            description="White-label ve görünüm ayarları."
            iconPath="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"
            iconColor="bg-purple-500/10 text-purple-500"
          />
          <QuickLinkCard
            href="/dashboard/brands"
            label="Markalar"
            description="Tüm markaları görüntüle ve yönet."
            iconPath="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
            iconColor="bg-amber-500/10 text-amber-500"
          />
          <QuickLinkCard
            href="/dashboard/reports"
            label="Raporlar"
            description="Performans raporlarını incele."
            iconPath="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            iconColor="bg-indigo-500/10 text-indigo-500"
          />
          <QuickLinkCard
            href="/dashboard/activity"
            label="Aktivite Günlüğü"
            description="Tüm ajans aktivitesini görüntüle."
            iconPath="M13 10V3L4 14h7v7l9-11h-7z"
            iconColor="bg-rose-500/10 text-rose-500"
          />
          <QuickLinkCard
            href="/dashboard/settings/members"
            label="Üye Davet Et"
            description="Yeni ekip üyesi davet et."
            iconPath="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            iconColor="bg-teal-500/10 text-teal-500"
          />
          <QuickLinkCard
            href="/dashboard/settings/agency"
            label="Ajans Ayarları"
            description="Ajans bilgilerini düzenle."
            iconPath="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            iconColor="bg-slate-500/10 text-slate-400"
          />
          <QuickLinkCard
            href="/dashboard/owner/appearance"
            label="Görünüm & Marka"
            description="White-label ve görsel özelleştirmeler."
            iconPath="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            iconColor="bg-pink-500/10 text-pink-500"
          />
          <QuickLinkCard
            href="/dashboard/owner/seo"
            label="SEO Yönetimi"
            description="Meta etiketler ve arama motoru görünürlüğü."
            iconPath="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            iconColor="bg-green-500/10 text-green-500"
          />
          <QuickLinkCard
            href="/dashboard/owner/notifications"
            label="Bildirim Kanalları"
            description="E-posta ve WhatsApp sağlayıcı durumu."
            iconPath="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            iconColor="bg-cyan-500/10 text-cyan-500"
          />
        </div>
      </div>
    </div>
  );
}
