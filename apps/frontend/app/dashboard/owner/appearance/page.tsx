"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { brandingApi, type AgencyBrandingRead } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function publicAssetUrl(url: string | null): string | null {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

function ColorSwatch({ color, label }: { color: string | null; label: string }) {
  if (!color) return null;
  return (
    <div className="flex items-center gap-2">
      <div
        className="w-6 h-6 rounded-md border border-border flex-shrink-0"
        style={{ backgroundColor: color }}
      />
      <span className="text-xs text-text-muted font-mono">{color}</span>
      <span className="text-xs text-text-muted">— {label}</span>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6 animate-pulse">
      <div className="h-8 bg-surface-2 rounded w-64" />
      <div className="grid grid-cols-3 gap-5">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-48 bg-surface-2 rounded-xl" />
        ))}
      </div>
      <div className="h-32 bg-surface-2 rounded-xl" />
    </div>
  );
}

export default function AppearanceHubPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const router = useRouter();

  const [settings, setSettings] = useState<AgencyBrandingRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isInitialized) return;
    if (activeAgency && activeAgency.member_role !== "owner") {
      router.replace("/dashboard");
      return;
    }
    if (!accessToken || !activeAgency?.id) return;

    brandingApi
      .get(activeAgency.id, accessToken)
      .then(setSettings)
      .catch(() => setError("Marka ayarları yüklenemedi."))
      .finally(() => setLoading(false));
  }, [accessToken, activeAgency, isInitialized, router]);

  if (loading) return <PageSkeleton />;

  const logoUrl = publicAssetUrl(settings?.logo_url ?? null);
  const faviconUrl = publicAssetUrl(settings?.favicon_url ?? null);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text">Görünüm & Marka Ayarları</h1>
          <p className="text-sm text-text-muted mt-1">
            Ajans markanızın müşteriye görünen yüzünü yönetin.
          </p>
        </div>
        <Link
          href="/dashboard/settings/branding"
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-semibold hover:bg-accent/90 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Detaylı Düzenle
        </Link>
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 bg-danger/10 border border-danger/20 rounded-xl text-sm text-danger">
          {error}
        </div>
      )}

      {/* 3-column card grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
        {/* Logo & Favicon */}
        <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 bg-indigo-500/10 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-text">Logo & Favicon</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-text-muted mb-2">Ana Logo</p>
              {logoUrl ? (
                <img src={logoUrl} alt="Logo" className="h-10 w-auto max-w-[140px] object-contain rounded border border-border" />
              ) : (
                <div className="h-10 w-32 bg-surface-2 rounded border border-dashed border-border flex items-center justify-center">
                  <span className="text-xs text-text-muted">Yüklenmedi</span>
                </div>
              )}
            </div>
            <div>
              <p className="text-xs text-text-muted mb-2">Favicon</p>
              {faviconUrl ? (
                <img src={faviconUrl} alt="Favicon" className="h-8 w-8 object-contain rounded border border-border" />
              ) : (
                <div className="h-8 w-8 bg-surface-2 rounded border border-dashed border-border flex items-center justify-center">
                  <span className="text-[10px] text-text-muted">—</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Marka Renkleri */}
        <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 bg-purple-500/10 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-text">Marka Renkleri</h3>
          </div>
          <div className="space-y-2.5">
            {settings?.primary_color ? (
              <ColorSwatch color={settings.primary_color} label="Birincil" />
            ) : (
              <p className="text-xs text-text-muted italic">Henüz ayarlanmadı</p>
            )}
            <ColorSwatch color={settings?.secondary_color ?? null} label="İkincil" />
            <ColorSwatch color={settings?.accent_color ?? null} label="Vurgu" />
          </div>
        </div>

        {/* İsim & Footer */}
        <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-8 h-8 bg-amber-500/10 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-text">İsim & Footer</h3>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-text-muted mb-1">Marka Adı</p>
              <p className="text-sm text-text font-medium">
                {settings?.brand_name_override ?? <span className="italic text-text-muted">Ajans adı</span>}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted mb-1">Footer Metni</p>
              <p className="text-xs text-text">
                {settings?.custom_footer_text ?? <span className="italic text-text-muted">Ayarlanmadı</span>}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* White-label toggle status */}
      <div className="bg-surface border border-border rounded-xl p-5 mb-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-surface-2 rounded-lg flex items-center justify-center">
              <svg className="w-4.5 h-4.5 w-[18px] h-[18px] text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-text">White-label Modu</p>
              <p className="text-xs text-text-muted">Flobrief markasını müşteri sayfalarından gizler</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border ${
              settings?.is_white_label_enabled
                ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                : "bg-surface-2 border-border text-text-muted"
            }`}>
              {settings?.is_white_label_enabled ? "Etkin" : "Devre Dışı"}
            </span>
            {!settings?.white_label_entitlement && (
              <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                Plan yükseltmesi gerekli
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Quick action */}
      <div className="flex justify-end">
        <Link
          href="/dashboard/settings/branding"
          className="inline-flex items-center gap-2 px-5 py-2.5 border border-border text-sm font-medium text-text-muted rounded-lg hover:border-accent hover:text-accent transition-colors"
        >
          Tüm Ayarları Düzenle
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Link>
      </div>
    </div>
  );
}
