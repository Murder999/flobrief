"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  brandPortalIdentityApi,
  type BrandIdentityOverview,
  type BrandIdentityProfileRead,
  type BrandIdentityDocumentRead,
  type BrandIdentityProfileUpdate,
  type ColorEntry,
  type FontEntry,
  ApiError,
} from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";

const PROFILE_STATUS_CONFIG: Record<string, { label: string; cls: string; dot: string }> = {
  draft:        { label: "Taslak",              cls: "text-text-muted bg-surface-2",   dot: "bg-text-muted" },
  ai_generated: { label: "Analiz Edildi",       cls: "text-info bg-info/10",           dot: "bg-info" },
  reviewed:     { label: "İncelendi",           cls: "text-warning bg-warning/10",     dot: "bg-warning" },
  approved:     { label: "Onaylandı",           cls: "text-success bg-success/10",     dot: "bg-success" },
};

const DOC_STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  uploaded:     { label: "Yüklendi",            cls: "text-text-muted bg-surface-2" },
  processing:   { label: "İşleniyor",           cls: "text-info bg-info/10" },
  analyzed:     { label: "Analiz Tamamlandı",   cls: "text-success bg-success/10" },
  needs_review: { label: "İnceleme Gerekli",    cls: "text-warning bg-warning/10" },
  approved:     { label: "Onaylandı",           cls: "text-success bg-success/10" },
  failed:       { label: "Hata",                cls: "text-danger bg-danger/10" },
};

function ColorSwatchSmall({ color }: { color: ColorEntry }) {
  const [copied, setCopied] = useState(false);
  return (
    <div
      className="w-12 h-12 rounded-lg border border-border cursor-pointer flex-shrink-0 relative group"
      style={{ backgroundColor: color.hex ?? "#e5e7eb" }}
      onClick={() => {
        if (!color.hex) return;
        navigator.clipboard.writeText(color.hex);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      title={color.hex ?? ""}
    >
      {copied && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-lg">
          <span className="text-white text-[9px]">✓</span>
        </div>
      )}
    </div>
  );
}

function DNACard({ profile }: { profile: BrandIdentityProfileRead }) {
  const ps = PROFILE_STATUS_CONFIG[profile.status];

  return (
    <div className="space-y-5">
      {/* Status header */}
      <div className="flex items-center gap-2 flex-wrap">
        {ps && (
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${ps.cls}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${ps.dot}`} />
            {ps.label}
          </span>
        )}
        {profile.confidence_score != null && (
          <span className="text-xs text-text-muted">Güven skoru: {profile.confidence_score}/95</span>
        )}
        {profile.approved_by_name && (
          <span className="text-xs text-text-muted">
            Onaylayan: {profile.approved_by_name}
            {profile.approved_at && ` · ${new Date(profile.approved_at).toLocaleDateString("tr-TR")}`}
          </span>
        )}
      </div>

      <p className="text-xs text-text-muted bg-info/5 border border-info/20 rounded-lg px-4 py-2.5">
        Ajansınız bu Marka DNA&apos;yı brief ve üretim süreçlerinde referans alır. Analiz sonucu düzenlenebilir ve onaylanabilir.
      </p>

      {/* Summary */}
      {profile.summary && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Marka Özeti</p>
          <p className="text-sm text-text leading-relaxed">{profile.summary}</p>
        </div>
      )}

      {/* Colors */}
      {(profile.primary_colors || profile.secondary_colors) && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Renk Paleti</p>
          {profile.primary_colors && profile.primary_colors.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-text-muted/70 mb-2">Ana Renkler</p>
              <div className="flex gap-2 flex-wrap">
                {profile.primary_colors.map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <ColorSwatchSmall color={c} />
                    <div>
                      {c.name && <p className="text-xs font-medium text-text">{c.name}</p>}
                      {c.hex && <p className="text-xs font-mono text-text-muted">{c.hex}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {profile.secondary_colors && profile.secondary_colors.length > 0 && (
            <div>
              <p className="text-xs text-text-muted/70 mb-2">Yardımcı Renkler</p>
              <div className="flex gap-2 flex-wrap">
                {profile.secondary_colors.map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <ColorSwatchSmall color={c} />
                    <div>
                      {c.hex && <p className="text-xs font-mono text-text-muted">{c.hex}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Typography */}
      {profile.typography && profile.typography.length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Tipografi</p>
          <div className="space-y-3">
            {profile.typography.map((f: FontEntry, i: number) => (
              <div key={i} className="flex items-center gap-3">
                {f.role && (
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted px-2 py-0.5 bg-surface-2 rounded-full w-20 text-center flex-shrink-0">
                    {f.role}
                  </span>
                )}
                {f.family && (
                  <p className="text-sm font-medium text-text" style={{ fontFamily: `'${f.family}', sans-serif` }}>
                    {f.family}
                  </p>
                )}
                {f.usage && <p className="text-xs text-text-muted">{f.usage}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Do/Don't */}
      {(profile.do_rules || profile.dont_rules) && (
        <div className="grid sm:grid-cols-2 gap-4">
          {profile.do_rules && profile.do_rules.length > 0 && (
            <div className="bg-surface border border-success/20 rounded-xl p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-success mb-3">Yapılacaklar</p>
              <ul className="space-y-2">
                {profile.do_rules.map((r: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-success flex-shrink-0" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {profile.dont_rules && profile.dont_rules.length > 0 && (
            <div className="bg-surface border border-danger/20 rounded-xl p-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-danger mb-3">Yapılmayacaklar</p>
              <ul className="space-y-2">
                {profile.dont_rules.map((r: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-danger flex-shrink-0" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Key Takeaways */}
      {profile.key_takeaways && profile.key_takeaways.length > 0 && (
        <div className="bg-gradient-to-r from-accent/5 to-transparent border border-accent/20 rounded-xl p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent mb-3">5 Kritik Kural</p>
          <div className="space-y-2">
            {profile.key_takeaways.map((rule: string, i: number) => (
              <div key={i} className="flex items-start gap-3">
                <span className="w-5 h-5 bg-accent/10 rounded-full flex items-center justify-center text-accent text-[10px] font-bold flex-shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <p className="text-sm text-text">{rule}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Logo rules */}
      {profile.logo_rules && profile.logo_rules.length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Logo Kuralları</p>
          <ul className="space-y-2">
            {profile.logo_rules.map((r: string, i: number) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Social media notes */}
      {profile.social_media_notes && profile.social_media_notes.length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Sosyal Medya Notları</p>
          <ul className="space-y-2">
            {profile.social_media_notes.map((n: string, i: number) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-info flex-shrink-0" />
                {n}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function BrandIdentityPage() {
  const { accessToken } = useAuth();
  const { toast } = useToast();
  const [overview, setOverview] = useState<BrandIdentityOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const ov = await brandPortalIdentityApi.getOverview(accessToken);
      setOverview(ov);
    } catch {
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => { fetchData(); }, [fetchData]);

  async function handleUpload(file: File) {
    if (!accessToken) return;
    setUploading(true);
    try {
      await brandPortalIdentityApi.uploadDocument(file, accessToken);
      toast("PDF yüklendi ve analiz başlatıldı.", "success");
      fetchData();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Yükleme hatası.", "error");
    } finally {
      setUploading(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8 max-w-3xl mx-auto animate-pulse space-y-4">
        <div className="h-6 bg-surface-2 rounded w-36" />
        <div className="h-4 bg-surface-2 rounded w-64" />
        <div className="h-48 bg-surface-2 rounded-xl" />
        <div className="h-32 bg-surface-2 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-text">Marka DNA</h1>
        <p className="text-sm text-text-muted mt-1">
          Kurumsal kimlikten çıkarılan uygulanabilir marka özeti
        </p>
      </div>

      {(!overview?.profile && (overview?.documents.length ?? 0) === 0) ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-accent/20 to-accent/5 rounded-2xl flex items-center justify-center mb-4 ring-1 ring-accent/20">
            <svg className="w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-text mb-2">Henüz Marka DNA oluşturulmadı</h3>
          <p className="text-sm text-text-muted mb-6 max-w-sm">
            Kurumsal kimlik PDF&apos;ini yükleyin. Sistem otomatik analiz ederek renk, font, ton ve kuralları çıkarır.
          </p>
          {uploading ? (
            <p className="text-sm text-text-muted animate-pulse">Yükleniyor…</p>
          ) : (
            <label className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium cursor-pointer hover:bg-accent/90 transition-colors shadow-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              Kurumsal Kimlik PDF&apos;i Yükle
              <input
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
              />
            </label>
          )}
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {overview?.documents[0] && (
                <p className="text-xs text-text-muted">
                  <span className="font-medium text-text">{overview.documents[0].file_name}</span>
                  {" "} · {new Date(overview.documents[0].created_at).toLocaleDateString("tr-TR")}
                </p>
              )}
            </div>
            {!uploading ? (
              <label className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-border text-text-muted hover:text-text rounded-lg cursor-pointer transition-colors">
                Yeni PDF Yükle
                <input
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
                />
              </label>
            ) : (
              <span className="text-xs text-text-muted animate-pulse">Yükleniyor…</span>
            )}
          </div>

          {overview?.profile ? (
            <DNACard profile={overview.profile} />
          ) : (
            <div className="py-8 text-center text-text-muted text-sm">
              PDF yüklendi, analiz sonucu henüz hazır değil. Ajansınız inceleme yapıyor.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
