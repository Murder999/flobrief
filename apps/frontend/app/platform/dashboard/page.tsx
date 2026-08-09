"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { platformApi, type PlatformDashboardStats, type PlatformAnalytics, ApiError } from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import {
  Building2,
  Users,
  CreditCard,
  TrendingUp,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";

/* ── KPI card ──────────────────────────────────────────────────────────────── */

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  accent = false,
  warn = false,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  accent?: boolean;
  warn?: boolean;
}) {
  const valueColor = accent ? "text-accent" : warn ? "text-warning" : "text-text";
  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex items-start gap-4">
      <div
        className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
          accent ? "bg-accent/15" : warn ? "bg-warning/10" : "bg-surface-2"
        }`}
      >
        <Icon
          className={`w-4.5 h-4.5 ${accent ? "text-accent" : warn ? "text-warning" : "text-text-muted"}`}
        />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-1.5">
          {label}
        </p>
        <p className={`text-2xl font-bold leading-none ${valueColor}`}>{value}</p>
        {sub && <p className="text-xs text-text-muted mt-1.5">{sub}</p>}
      </div>
    </div>
  );
}

/* ── Distribution bar row ──────────────────────────────────────────────────── */

function DistRow({
  label,
  value,
  total,
  color = "bg-accent",
}: {
  label: string;
  value: number;
  total: number;
  color?: string;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-text-muted w-36 flex-shrink-0 capitalize truncate">
        {label.replace(/_/g, " ")}
      </span>
      <div className="flex-1 bg-surface-3 rounded-full h-1.5 overflow-hidden">
        <div
          className={`${color} h-1.5 rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-medium text-text w-10 text-right flex-shrink-0">{value}</span>
      <span className="text-xs text-text-muted w-8 text-right flex-shrink-0">{pct}%</span>
    </div>
  );
}

/* ── Section card ──────────────────────────────────────────────────────────── */

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────────────────── */

export default function PlatformDashboardPage() {
  const router = useRouter();
  const [stats,     setStats]     = useState<PlatformDashboardStats | null>(null);
  const [analytics, setAnalytics] = useState<PlatformAnalytics | null>(null);
  const [error,     setError]     = useState<string | null>(null);
  const [loading,   setLoading]   = useState(true);

  async function load() {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    setLoading(true);
    setError(null);
    try {
      const [s, a] = await Promise.all([
        platformApi.dashboard(token),
        platformApi.analytics(token),
      ]);
      setStats(s);
      setAnalytics(a);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        platformAuthStorage.clearAll();
        router.replace("/platform/login");
      } else {
        setError(err instanceof ApiError ? err.message : "Veriler yüklenemedi");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Loading ─────────────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="p-8">
        <div className="mb-8">
          <div className="h-6 w-40 bg-surface-2 rounded-lg animate-pulse mb-2" />
          <div className="h-4 w-56 bg-surface-2 rounded-lg animate-pulse" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-xl p-5 h-28 animate-pulse" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-xl h-52 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  /* ── Error ────────────────────────────────────────────────────────────────── */
  if (error) {
    return (
      <div className="p-8">
        <div className="bg-danger/8 border border-danger/20 rounded-xl p-6 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-danger flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-danger mb-1">Veri yüklenemedi</p>
            <p className="text-xs text-text-muted mb-3">{error}</p>
            <button
              onClick={load}
              className="inline-flex items-center gap-2 text-xs text-accent hover:text-accent-hover transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Tekrar dene
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!stats || !analytics) return null;

  const mrr = (stats.mrr_cents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  });

  const totalByStatus = Object.values(analytics.agencies_by_status).reduce((a, b) => a + b, 0);
  const totalByType   = Object.values(analytics.users_by_type).reduce((a, b) => a + b, 0);
  const totalByPlan   = Object.values(analytics.plan_distribution).reduce((a, b) => a + b, 0);

  const DIST_COLORS: Record<string, string> = {
    active:   "bg-success",
    suspended: "bg-danger",
    pending:  "bg-warning",
    inactive: "bg-surface-3",
  };

  return (
    <div className="p-8">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">
            Platform Yönetimi
          </p>
          <h1 className="text-2xl font-bold text-text tracking-tight">Genel Bakış</h1>
          <p className="text-sm text-text-muted mt-1">
            Tüm kiracılardaki gerçek zamanlı metrikler
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-2 bg-surface border border-border rounded-lg text-xs text-text-muted hover:text-text hover:border-border-hover transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Yenile
        </button>
      </div>

      {/* ── KPI grid ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <KpiCard
          label="Toplam Ajans"
          value={stats.total_agencies}
          sub={`${stats.active_agencies} aktif`}
          icon={Building2}
        />
        <KpiCard
          label="Aktif Ajans"
          value={stats.active_agencies}
          sub={stats.suspended_agencies > 0 ? `${stats.suspended_agencies} askıda` : "Hepsi aktif"}
          icon={Building2}
          accent
        />
        <KpiCard
          label="Toplam Kullanıcı"
          value={stats.total_users}
          sub="Kayıtlı hesaplar"
          icon={Users}
        />
        <KpiCard
          label="Aktif Kullanıcı (30g)"
          value={stats.active_users_30d}
          sub="Son 30 gün"
          icon={TrendingUp}
          accent
        />
        <KpiCard
          label="Abonelikler"
          value={stats.total_subscriptions}
          sub="Aktif planlar"
          icon={CreditCard}
        />
        <KpiCard
          label="Aylık Gelir"
          value={mrr}
          sub="Aktif abonelikler"
          icon={TrendingUp}
          accent
        />
      </div>

      {/* ── Analytics grid ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agencies by status */}
        <SectionCard title="Ajans Durumu">
          {Object.keys(analytics.agencies_by_status).length === 0 ? (
            <p className="text-sm text-text-muted opacity-60 py-2">Henüz veri yok</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(analytics.agencies_by_status).map(([status, count]) => (
                <DistRow
                  key={status}
                  label={status}
                  value={count}
                  total={totalByStatus}
                  color={DIST_COLORS[status] ?? "bg-accent"}
                />
              ))}
            </div>
          )}
        </SectionCard>

        {/* Users by type */}
        <SectionCard title="Kullanıcı Tipi">
          {Object.keys(analytics.users_by_type).length === 0 ? (
            <p className="text-sm text-text-muted opacity-60 py-2">Henüz veri yok</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(analytics.users_by_type).map(([type, count]) => (
                <DistRow
                  key={type}
                  label={type}
                  value={count}
                  total={totalByType}
                />
              ))}
            </div>
          )}
        </SectionCard>

        {/* Plan distribution */}
        <SectionCard title="Plan Dağılımı">
          {Object.keys(analytics.plan_distribution).length === 0 ? (
            <p className="text-sm text-text-muted opacity-60 py-2">Henüz veri yok</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(analytics.plan_distribution).map(([plan, count]) => (
                <DistRow
                  key={plan}
                  label={plan}
                  value={count}
                  total={totalByPlan}
                  color="bg-purple"
                />
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
