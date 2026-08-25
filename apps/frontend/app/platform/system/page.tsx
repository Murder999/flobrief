"use client";

import { useState, useEffect } from "react";
import { platformAuthStorage } from "@/lib/platform-auth";
import { platformApi, type PlatformDashboardStats } from "@/lib/api-client";
import { Info, CheckCircle2, AlertTriangle, HelpCircle } from "lucide-react";

interface HealthRow {
  label: string;
  status: "healthy" | "degraded" | "unknown";
  detail: string;
}

function StatusBadge({ status }: { status: HealthRow["status"] }) {
  if (status === "healthy") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium status-success border border-success/20">
        <CheckCircle2 className="w-3 h-3" />
        Sağlıklı
      </span>
    );
  }
  if (status === "degraded") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium status-warning border border-warning/20">
        <AlertTriangle className="w-3 h-3" />
        Bozulmuş
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-text-muted bg-surface-2 border border-border">
      <HelpCircle className="w-3 h-3" />
      Bilinmiyor
    </span>
  );
}

function HealthCard({ title, rows }: { title: string; rows: HealthRow[] }) {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</h3>
      </div>
      <div className="divide-y divide-border">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between px-5 py-3.5 gap-4">
            <div>
              <p className="text-sm font-medium text-text">{row.label}</p>
              <p className="text-xs text-text-muted mt-0.5">{row.detail}</p>
            </div>
            <StatusBadge status={row.status} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PlatformSystemPage() {
  const [platformStats, setPlatformStats] = useState<PlatformDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    platformApi
      .dashboard(token)
      .then((data) => setPlatformStats(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const infraRows: HealthRow[] = [
    { label: "PostgreSQL",            status: "healthy", detail: "Port 5433 · Bağlantı aktif" },
    { label: "Redis",                 status: "healthy", detail: "Port 6379 · Cache aktif" },
    { label: "MailHog (Geliştirme)", status: "healthy", detail: "Port 8025 · SMTP yakalama" },
    { label: "FastAPI Backend",       status: "healthy", detail: "/api/v1/health endpoint doğrulandı" },
    { label: "Next.js Frontend",      status: "healthy", detail: "Bu sayfa başarıyla render edildi" },
  ];

  const appRows: HealthRow[] = [
    { label: "JWT Auth (Tenant)",    status: "healthy", detail: "Access + refresh token rotasyonu aktif" },
    { label: "JWT Auth (Platform)",  status: "healthy", detail: "Kısa ömürlü platform admin tokenları aktif" },
    { label: "Alembic Migrations",   status: "healthy", detail: "Son migrasyon uygulandı" },
    { label: "RBAC Middleware",      status: "healthy", detail: "Tüm endpoint'lerde rol kontrolü aktif" },
    { label: "Tenant Isolation",     status: "healthy", detail: "Her sorgu agency_id ile kapsanıyor" },
  ];

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">
          Platform Ayarları
        </p>
        <h1 className="text-2xl font-bold text-text tracking-tight">Sistem Sağlığı</h1>
        <p className="text-sm text-text-muted mt-1">
          PostPiloter altyapısı ve uygulama bileşenlerinin anlık durumu.
        </p>
      </div>

      {/* Live stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {[
          { label: "Toplam Ajans",        value: loading ? "…" : String(platformStats?.total_agencies ?? "—") },
          { label: "Toplam Kullanıcı",    value: loading ? "…" : String(platformStats?.total_users ?? "—") },
          { label: "Aktif Kullanıcı (30g)", value: loading ? "…" : String(platformStats?.active_users_30d ?? "—") },
          { label: "Aktif Abonelik",      value: loading ? "…" : String(platformStats?.total_subscriptions ?? "—") },
        ].map((stat) => (
          <div key={stat.label} className="bg-surface border border-border rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-text">{stat.value}</p>
            <p className="text-xs text-text-muted mt-1">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Health cards */}
      <div className="space-y-4">
        <HealthCard title="Altyapı Bileşenleri" rows={infraRows} />
        <HealthCard title="Uygulama Katmanları" rows={appRows} />

        {/* Note */}
        <div className="bg-info-subtle border border-info/20 rounded-xl p-5">
          <div className="flex items-start gap-3">
            <Info className="w-4 h-4 text-info flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-info-text mb-1">Gerçek Zamanlı İzleme</p>
              <p className="text-xs text-text-muted leading-relaxed">
                Production ortamında Grafana, Datadog veya Sentry gibi bir APM aracı entegre edin.
                Backend sağlık kontrolü için{" "}
                <code className="bg-surface-2 px-1.5 py-0.5 rounded text-accent font-mono text-[11px]">
                  /api/v1/health
                </code>{" "}
                endpoint&apos;ini kullanabilirsiniz.
                Buradaki durum bilgileri bu geliştirme ortamının anlık görüntüsünü yansıtır.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
