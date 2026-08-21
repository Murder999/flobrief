"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { brandingApi, type AgencyBrandingRead } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useToast } from "@/components/ui/toast";

function CheckItem({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${ok ? "bg-emerald-100 text-emerald-600" : "bg-surface-2 text-text-muted"}`}>
        {ok ? (
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        )}
      </div>
      <span className={`text-sm ${ok ? "text-text" : "text-text-muted"}`}>{label}</span>
      <span className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${ok ? "bg-emerald-50 text-emerald-700" : "bg-surface-2 text-text-muted"}`}>
        {ok ? "Tamam" : "Eksik"}
      </span>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6 animate-pulse">
      <div className="h-8 bg-surface-2 rounded w-56" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="h-64 bg-surface-2 rounded-xl" />
        <div className="h-64 bg-surface-2 rounded-xl" />
      </div>
    </div>
  );
}

export default function SeoPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const router = useRouter();
  const { toast } = useToast();

  const [settings, setSettings] = useState<AgencyBrandingRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [seoTitle, setSeoTitle] = useState("");
  const [seoDescription, setSeoDescription] = useState("");
  const [ogImageUrl, setOgImageUrl] = useState("");
  const [gaId, setGaId] = useState("");

  useEffect(() => {
    if (!isInitialized) return;
    if (activeAgency && activeAgency.member_role !== "owner") {
      router.replace("/dashboard");
      return;
    }
    if (!accessToken || !activeAgency?.id) return;

    brandingApi
      .get(activeAgency.id, accessToken)
      .then((data) => {
        setSettings(data);
        setSeoTitle(data.seo_title ?? "");
        setSeoDescription(data.seo_description ?? "");
        setOgImageUrl(data.og_image_url ?? "");
        setGaId(data.google_analytics_id ?? "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [accessToken, activeAgency, isInitialized, router]);

  const handleSave = async () => {
    if (!accessToken || !activeAgency?.id) return;
    setSaving(true);
    try {
      const updated = await brandingApi.update(
        {
          seo_title: seoTitle || null,
          seo_description: seoDescription || null,
          og_image_url: ogImageUrl || null,
          google_analytics_id: gaId || null,
        },
        activeAgency.id,
        accessToken
      );
      setSettings(updated);
      toast("SEO ayarları kaydedildi.", "success");
    } catch {
      toast("Kaydetme başarısız.", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <PageSkeleton />;

  const hasBrandName = !!(settings?.brand_name_override);
  const hasSeoTitle = !!seoTitle;
  const hasSeoDesc = !!seoDescription;
  const hasLogo = !!(settings?.logo_url);
  const hasOgImage = !!ogImageUrl;

  const score = [hasBrandName, hasSeoTitle, hasSeoDesc, hasLogo, hasOgImage].filter(Boolean).length;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text">SEO & Büyüme Merkezi</h1>
          <p className="text-sm text-text-muted mt-1">
            Arama motoru görünürlüğünüzü ve sosyal medya önizlemelerinizi optimize edin.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {saving ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Kaydediliyor...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Kaydet
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* SEO Health Checklist */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-text">SEO Sağlık Kontrolü</h3>
            <div className="flex items-center gap-2">
              <div className="w-16 h-1.5 bg-surface-2 rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full transition-all"
                  style={{ width: `${(score / 5) * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium text-text-muted">{score}/5</span>
            </div>
          </div>
          <div className="divide-y divide-border">
            <CheckItem label="Marka adı ayarlandı" ok={hasBrandName} />
            <CheckItem label="SEO başlığı ayarlandı (maks. 60 karakter)" ok={hasSeoTitle} />
            <CheckItem label="Meta açıklaması ayarlandı (maks. 160 karakter)" ok={hasSeoDesc} />
            <CheckItem label="Logo yüklendi" ok={hasLogo} />
            <CheckItem label="OG görseli ayarlandı" ok={hasOgImage} />
          </div>
        </div>

        {/* Open Graph Preview */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text mb-4">Sosyal Medya Önizlemesi</h3>
          <div className="border border-border rounded-xl overflow-hidden bg-surface-2">
            {hasOgImage && (
              <div className="h-36 bg-surface-2 flex items-center justify-center border-b border-border overflow-hidden">
                <img
                  src={ogImageUrl}
                  alt="OG Preview"
                  className="w-full h-full object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            )}
            {!hasOgImage && (
              <div className="h-36 bg-surface-2 flex items-center justify-center border-b border-border">
                <svg className="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            )}
            <div className="px-3 py-2.5">
              <p className="text-xs text-text-muted mb-0.5">{activeAgency?.slug ?? "postpiloter.com"}</p>
              <p className="text-sm font-semibold text-text line-clamp-1">
                {seoTitle || settings?.brand_name_override || "Sayfa Başlığı"}
              </p>
              <p className="text-xs text-text-muted mt-0.5 line-clamp-2">
                {seoDescription || "Meta açıklaması buraya gelecek…"}
              </p>
            </div>
          </div>
        </div>

        {/* SEO Meta Tags Form */}
        <div className="bg-surface border border-border rounded-xl p-5 space-y-4 lg:col-span-2">
          <h3 className="text-sm font-semibold text-text mb-2">SEO Meta Etiketleri</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                  SEO Sayfa Başlığı
                </label>
                <span className={`text-xs ${seoTitle.length > 55 ? "text-amber-500" : "text-text-muted"}`}>
                  {seoTitle.length}/60
                </span>
              </div>
              <input
                type="text"
                value={seoTitle}
                onChange={(e) => setSeoTitle(e.target.value.slice(0, 60))}
                placeholder="Ajans adı | Flobrief"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-surface text-text"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                  OG Görseli URL
                </label>
              </div>
              <input
                type="url"
                value={ogImageUrl}
                onChange={(e) => setOgImageUrl(e.target.value)}
                placeholder="https://example.com/og-image.png"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-surface text-text font-mono"
              />
            </div>

            <div className="space-y-1.5 md:col-span-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                  Meta Açıklaması
                </label>
                <span className={`text-xs ${seoDescription.length > 145 ? "text-amber-500" : "text-text-muted"}`}>
                  {seoDescription.length}/160
                </span>
              </div>
              <textarea
                value={seoDescription}
                onChange={(e) => setSeoDescription(e.target.value.slice(0, 160))}
                rows={3}
                placeholder="Ajansınız ve sunduğu hizmetler hakkında kısa bir açıklama yazın…"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-surface text-text resize-none"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                Google Analytics ID
              </label>
              <input
                type="text"
                value={gaId}
                onChange={(e) => setGaId(e.target.value)}
                placeholder="G-XXXXXXXXXX"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent bg-surface text-text font-mono"
              />
              <p className="text-xs text-text-muted">Google Analytics 4 ölçüm ID&apos;niz</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
