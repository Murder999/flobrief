"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, platformApi, type PlatformSubscriptionRead } from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import { AlertTriangle, RefreshCw, TrendingUp } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  active:    "Aktif",
  cancelled: "İptal Edildi",
  trialing:  "Deneme",
  past_due:  "Ödeme Gecikti",
};

const STATUS_CLASSES: Record<string, string> = {
  active:    "status-success",
  cancelled: "status-danger",
  trialing:  "status-warning",
  past_due:  "status-warning",
};

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
}

export default function PlatformSubscriptionsPage() {
  const router = useRouter();
  const [subscriptions, setSubscriptions] = useState<PlatformSubscriptionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  async function load() {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await platformApi.listSubscriptions(token, { limit: 100 });
      setSubscriptions(data);
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

  const activeMrr = subscriptions
    .filter((s) => s.status === "active")
    .reduce((sum, s) => sum + s.monthly_price_cents, 0);

  const mrrFormatted = (activeMrr / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  });

  const activeCount  = subscriptions.filter((s) => s.status === "active").length;
  const trialCount   = subscriptions.filter((s) => s.status === "trialing").length;
  const pastDueCount = subscriptions.filter((s) => s.status === "past_due").length;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">
            Kiracılar
          </p>
          <h1 className="text-2xl font-bold text-text tracking-tight">Abonelikler</h1>
          <p className="text-sm text-text-muted mt-1">
            {loading ? "Yükleniyor…" : `${subscriptions.length} abonelik`}
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

      {/* KPI row */}
      {!loading && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-surface border border-border rounded-xl p-5">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-2">Aylık Gelir</p>
            <p className="text-2xl font-bold text-accent">{mrrFormatted}</p>
            <p className="text-xs text-text-muted mt-1">Aktif abonelikler</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-5">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-2">Aktif</p>
            <p className="text-2xl font-bold text-success">{activeCount}</p>
            <p className="text-xs text-text-muted mt-1">Ödeme alınıyor</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-5">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-2">Deneme</p>
            <p className="text-2xl font-bold text-warning">{trialCount}</p>
            <p className="text-xs text-text-muted mt-1">Trial süresi</p>
          </div>
          <div className="bg-surface border border-border rounded-xl p-5">
            <p className="text-xs text-text-muted uppercase tracking-wide mb-2 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              Ödeme Gecikti
            </p>
            <p className={`text-2xl font-bold ${pastDueCount > 0 ? "text-danger" : "text-text"}`}>
              {pastDueCount}
            </p>
            <p className="text-xs text-text-muted mt-1">Müdahale gerekiyor</p>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6 flex items-start gap-2.5 bg-danger/8 border border-danger/20 rounded-xl px-4 py-3">
          <AlertTriangle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-2">
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Ajans</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Plan</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Durum</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Aylık</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Dönem Sonu</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Oluşturulma</th>
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 8 }).map((_, i) => (
              <tr key={i} className="border-b border-border/50">
                {Array.from({ length: 6 }).map((__, j) => (
                  <td key={j} className="px-5 py-4">
                    <div className="h-4 bg-surface-2 rounded animate-pulse" />
                  </td>
                ))}
              </tr>
            ))}
            {!loading && subscriptions.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-16 text-center text-text-muted opacity-60">
                  Abonelik bulunamadı
                </td>
              </tr>
            )}
            {!loading && subscriptions.map((sub) => (
              <tr key={sub.id} className="border-b border-border/50 hover:bg-surface-2 transition-colors">
                <td className="px-5 py-4">
                  <p className="font-medium text-text">{sub.agency_name ?? "—"}</p>
                  <p className="text-xs text-text-muted mt-0.5 font-mono opacity-60">
                    {sub.agency_id?.slice(0, 8)}…
                  </p>
                </td>
                <td className="px-5 py-4">
                  <p className="text-text">{sub.plan_name}</p>
                  <p className="text-xs text-text-muted font-mono">{sub.plan_code}</p>
                </td>
                <td className="px-5 py-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${STATUS_CLASSES[sub.status] ?? "status-neutral"}`}>
                    {STATUS_LABELS[sub.status] ?? sub.status}
                  </span>
                </td>
                <td className="px-5 py-4 font-medium text-text">
                  ${(sub.monthly_price_cents / 100).toFixed(0)}
                </td>
                <td className="px-5 py-4 text-xs text-text-muted">
                  {fmtDate(sub.current_period_end ?? null)}
                </td>
                <td className="px-5 py-4 text-xs text-text-muted">
                  {fmtDate(sub.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
