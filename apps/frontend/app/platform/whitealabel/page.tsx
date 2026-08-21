"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  platformBrandingApi,
  type PlatformBrandingDefaults,
  type PlatformBrandingDefaultsUpdate,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function assetUrl(url: string | null): string | null {
  if (!url) return null;
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}

// ── WCAG contrast check ─────────────────────────────────────────────────────

function hexToRgb(hex: string): [number, number, number] | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return null;
  const int = parseInt(m[1], 16);
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const srgb = [r, g, b].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2];
}

function contrastRatio(hexA: string, hexB: string): number | null {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  if (!a || !b) return null;
  const lA = relativeLuminance(a);
  const lB = relativeLuminance(b);
  const lighter = Math.max(lA, lB);
  const darker = Math.min(lA, lB);
  return (lighter + 0.05) / (darker + 0.05);
}

// ── Small building blocks ────────────────────────────────────────────────────

function Card({ title, description, children, action }: { title: string; description?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-start justify-between gap-3">
        <div>
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</h3>
          {description && <p className="text-xs text-text-muted opacity-70 mt-1">{description}</p>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-text-muted mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-text-muted opacity-60 mt-1">{hint}</p>}
    </div>
  );
}

function TextInput({ value, onChange, placeholder, type = "text" }: { value: string; onChange: (v: string) => void; placeholder?: string; type?: string }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent transition-colors"
    />
  );
}

function ColorField({ label, value, onChange, contrastAgainst }: { label: string; value: string; onChange: (v: string) => void; contrastAgainst?: string }) {
  const ratio = contrastAgainst && value ? contrastRatio(value, contrastAgainst) : null;
  const critical = ratio !== null && ratio < 3;
  const warn = ratio !== null && ratio >= 3 && ratio < 4.5;
  return (
    <div>
      <label className="block text-xs font-medium text-text-muted mb-1.5">{label}</label>
      <div className="flex items-center gap-2.5">
        <input
          type="color"
          value={/^#[0-9A-Fa-f]{6}$/.test(value) ? value : "#6366F1"}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          className="w-9 h-9 rounded-lg border border-border cursor-pointer p-0.5 bg-surface"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => {
            const v = e.target.value.toUpperCase();
            if (v === "" || /^#[0-9A-F]{0,6}$/.test(v)) onChange(v);
          }}
          placeholder="#6366F1"
          className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs font-mono text-text focus:outline-none focus:border-accent transition-colors"
        />
      </div>
      {ratio !== null && (
        <p className={`text-xs mt-1 ${critical ? "text-danger" : warn ? "text-warning" : "text-success"}`}>
          Kontrast oranı: {ratio.toFixed(2)}:1 {critical ? "— kritik, okunabilirlik riski" : warn ? "— AA eşiğinin altında" : "— WCAG AA uyumlu"}
        </p>
      )}
    </div>
  );
}

function UploadField({ label, hint, currentUrl, uploading, onFile }: { label: string; hint: string; currentUrl: string | null; uploading: boolean; onFile: (f: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const resolved = assetUrl(currentUrl);
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-text">{label}</p>
          <p className="text-xs text-text-muted opacity-70">{hint}</p>
        </div>
        {resolved && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={resolved} alt={label} className="h-9 w-auto max-w-[100px] object-contain rounded border border-border bg-surface-2 p-1" />
        )}
      </div>
      <button
        type="button"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
        className="w-full flex items-center justify-center gap-2 px-4 py-2 border-2 border-dashed border-border rounded-lg text-xs text-text-muted hover:border-accent hover:text-accent transition-colors disabled:opacity-40"
      >
        {uploading ? "Yükleniyor…" : resolved ? "Değiştir" : "Dosya Seç"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}

// ── Live preview ──────────────────────────────────────────────────────────────

type PreviewTarget = "login" | "sidebar" | "header" | "buttons";

function LivePreview({ form, defaults, target, onTargetChange }: { form: PlatformBrandingDefaultsUpdate; defaults: PlatformBrandingDefaults; target: PreviewTarget; onTargetChange: (t: PreviewTarget) => void }) {
  const primary = form.primary_color || defaults.primary_color || "#6366F1";
  const accent = form.accent_color || defaults.accent_color || "#4F46E5";
  const bg = form.background_color || defaults.background_color || "#0B0B12";
  const surface = form.surface_color || defaults.surface_color || "#15151F";
  const text = form.text_color || defaults.text_color || "#F4F4F6";
  const portalName = form.portal_name ?? defaults.portal_name ?? "Flobrief";
  const logoUrl = assetUrl(defaults.logo_url);
  const targets: { id: PreviewTarget; label: string }[] = [
    { id: "login", label: "Giriş Ekranı" },
    { id: "sidebar", label: "Sidebar" },
    { id: "header", label: "Header" },
    { id: "buttons", label: "Kontroller" },
  ];

  return (
    <div className="bg-surface-2 border border-border rounded-2xl p-5 space-y-4 sticky top-6">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Canlı Önizleme</span>
        <div className="flex items-center gap-1 bg-surface border border-border rounded-lg p-0.5">
          {targets.map((t) => (
            <button
              key={t.id}
              onClick={() => onTargetChange(t.id)}
              className={`px-2 py-1 rounded-md text-[10px] font-medium transition-colors ${target === t.id ? "bg-accent text-white" : "text-text-muted hover:text-text"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-border overflow-hidden" style={{ background: bg, color: text }}>
        {target === "login" && (
          <div className="p-8 flex flex-col items-center text-center gap-4">
            {logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logoUrl} alt="Logo" className="h-8 w-auto max-w-[140px] object-contain" />
            ) : (
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold" style={{ background: primary }}>
                {portalName[0]?.toUpperCase() ?? "F"}
              </div>
            )}
            <div>
              <p className="text-sm font-semibold">{form.login_title || "Panele Giriş Yap"}</p>
              <p className="text-xs opacity-60 mt-1 max-w-[220px]">{form.login_description || "Hesabınıza erişmek için giriş yapın."}</p>
            </div>
            <div className="w-full max-w-[200px] space-y-2 mt-2">
              <div className="h-8 rounded-lg" style={{ background: surface }} />
              <div className="h-8 rounded-lg" style={{ background: surface }} />
              <div className="h-8 rounded-lg text-white text-xs font-medium flex items-center justify-center" style={{ background: primary }}>Giriş Yap</div>
            </div>
          </div>
        )}
        {target === "sidebar" && (
          <div className="flex h-40">
            <div className="w-28 p-3 space-y-2" style={{ background: surface }}>
              <div className="flex items-center gap-1.5 mb-3">
                {logoUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={logoUrl} alt="Logo" className="h-4 w-auto max-w-[60px] object-contain" />
                ) : (
                  <div className="w-4 h-4 rounded" style={{ background: primary }} />
                )}
                <span className="text-[9px] font-semibold truncate">{portalName}</span>
              </div>
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-2 rounded" style={{ background: i === 1 ? primary : "rgba(255,255,255,0.08)", width: `${90 - i * 10}%` }} />
              ))}
            </div>
            <div className="flex-1 p-3">
              <div className="h-3 w-2/3 rounded mb-2" style={{ background: surface }} />
              <div className="h-2 w-1/2 rounded" style={{ background: surface }} />
            </div>
          </div>
        )}
        {target === "header" && (
          <div className="p-4 flex items-center justify-between" style={{ background: surface, borderBottom: `2px solid ${primary}40` }}>
            <div className="flex items-center gap-2">
              {logoUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logoUrl} alt="Logo" className="h-5 w-auto max-w-[80px] object-contain" />
              ) : (
                <div className="w-5 h-5 rounded" style={{ background: primary }} />
              )}
              <span className="text-xs font-semibold">{portalName}</span>
            </div>
            <div className="w-6 h-6 rounded-full" style={{ background: accent }} />
          </div>
        )}
        {target === "buttons" && (
          <div className="p-6 flex flex-col items-center gap-3">
            <button className="px-5 py-2 rounded-lg text-white text-xs font-medium" style={{ background: primary }}>Birincil Buton</button>
            <button className="px-5 py-2 rounded-lg text-xs font-medium border" style={{ borderColor: accent, color: accent }}>İkincil Buton</button>
            <a className="text-xs underline" style={{ color: form.link_color || defaults.link_color || accent }}>Bağlantı örneği</a>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 text-[10px]">
        {[{ l: "Birincil", c: primary }, { l: "Vurgu", c: accent }, { l: "Zemin", c: bg }].map(({ l, c }) => (
          <div key={l} className="text-center space-y-1">
            <div className="w-full h-5 rounded border border-border" style={{ background: c }} />
            <span className="text-text-muted font-mono">{c}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlatformWhitelabelPage() {
  const router = useRouter();
  const [defaults, setDefaults] = useState<PlatformBrandingDefaults | null>(null);
  const [form, setForm] = useState<PlatformBrandingDefaultsUpdate>({});
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [previewTarget, setPreviewTarget] = useState<PreviewTarget>("login");
  const [socialInputs, setSocialInputs] = useState<{ key: string; value: string }[]>([]);

  function toForm(d: PlatformBrandingDefaults): PlatformBrandingDefaultsUpdate {
    return {
      portal_name: d.portal_name,
      login_title: d.login_title,
      login_description: d.login_description,
      primary_color: d.primary_color ?? "",
      accent_color: d.accent_color ?? "",
      background_color: d.background_color ?? "",
      surface_color: d.surface_color ?? "",
      text_color: d.text_color ?? "",
      link_color: d.link_color ?? "",
      email_from_name: d.email_from_name,
      support_email: d.support_email,
      footer_text: d.footer_text,
      terms_url: d.terms_url,
      privacy_url: d.privacy_url,
      social_links: d.social_links,
    };
  }

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    platformBrandingApi.get(token).then((d) => {
      setDefaults(d);
      setForm(toForm(d));
      setSocialInputs(Object.entries(d.social_links ?? {}).map(([key, value]) => ({ key, value })));
    }).catch(() => {}).finally(() => setLoading(false));
  }, [router]);

  const isDirty = defaults ? JSON.stringify(form) !== JSON.stringify(toForm(defaults)) : false;

  function setF<K extends keyof PlatformBrandingDefaultsUpdate>(key: K, value: PlatformBrandingDefaultsUpdate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaveState("saving");
    setSaveError(null);
    try {
      const payload: PlatformBrandingDefaultsUpdate = {
        ...form,
        social_links: socialInputs.filter((s) => s.key.trim() && s.value.trim())
          .reduce((acc, s) => ({ ...acc, [s.key.trim()]: s.value.trim() }), {} as Record<string, string>),
      };
      const updated = await platformBrandingApi.update(payload, token);
      setDefaults(updated);
      setForm(toForm(updated));
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2500);
    } catch (e) {
      setSaveState("error");
      setSaveError(e instanceof ApiError ? e.message : "Kaydetme başarısız.");
    }
  }

  function handleDiscard() {
    if (defaults) {
      setForm(toForm(defaults));
      setSocialInputs(Object.entries(defaults.social_links ?? {}).map(([key, value]) => ({ key, value })));
    }
  }

  async function handleReset() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    if (!window.confirm("Tüm platform white-label ayarları varsayılana (boş) sıfırlanacak. Emin misiniz?")) return;
    setSaveState("saving");
    try {
      const reset = await platformBrandingApi.reset(token);
      setDefaults(reset);
      setForm(toForm(reset));
      setSocialInputs([]);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2500);
    } catch (e) {
      setSaveState("error");
      setSaveError(e instanceof ApiError ? e.message : "Sıfırlama başarısız.");
    }
  }

  async function handleUpload(assetType: "logo" | "logo_dark" | "favicon", file: File) {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setUploading(assetType);
    try {
      const updated = await platformBrandingApi.uploadAsset(file, assetType, token);
      setDefaults(updated);
    } catch (e) {
      setSaveState("error");
      setSaveError(e instanceof ApiError ? e.message : "Yükleme başarısız.");
    } finally {
      setUploading(null);
    }
  }

  if (loading || !defaults) {
    return (
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        <div className="h-8 w-64 bg-surface-2 rounded animate-pulse" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-40 bg-surface-2 rounded-xl animate-pulse" />)}
          </div>
          <div className="h-96 bg-surface-2 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">Platform Ayarları</p>
          <h1 className="text-2xl font-bold text-text">White Label Yönetimi</h1>
          <p className="mt-1 text-sm text-text-muted max-w-xl">
            Ajansların kullanacağı varsayılan Flobrief kimliği. Bu ayarlar, kendi white-label
            yapılandırmasını yapmamış ajans portallarında ve giriş ekranında otomatik uygulanır.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isDirty && (
            <span className="text-xs text-warning bg-warning/10 px-2.5 py-1 rounded-full font-medium">Kaydedilmemiş değişiklikler</span>
          )}
          <button
            onClick={handleDiscard}
            disabled={!isDirty || saveState === "saving"}
            className="px-4 py-2 text-sm text-text-muted hover:text-text disabled:opacity-40 transition-colors"
          >
            Vazgeç
          </button>
          <button
            onClick={handleReset}
            disabled={saveState === "saving"}
            className="px-4 py-2 text-sm text-danger hover:bg-danger/10 rounded-lg disabled:opacity-40 transition-colors"
          >
            Varsayılana Dön
          </button>
          <button
            onClick={handleSave}
            disabled={!isDirty || saveState === "saving"}
            className="px-5 py-2 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            {saveState === "saving" ? "Kaydediliyor…" : saveState === "saved" ? "Kaydedildi ✓" : "Kaydet"}
          </button>
        </div>
      </div>

      {saveState === "error" && saveError && (
        <div className="mb-6 status-danger rounded-xl p-4 text-sm">{saveError}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-5">
          <Card title="Portal Kimliği" description="Ajans portallarında ve giriş ekranında görünen ad ve mesajlar.">
            <div className="space-y-4">
              <Field label="Portal adı">
                <TextInput value={form.portal_name ?? ""} onChange={(v) => setF("portal_name", v || null)} placeholder="Flobrief" />
              </Field>
              <Field label="Giriş ekranı başlığı">
                <TextInput value={form.login_title ?? ""} onChange={(v) => setF("login_title", v || null)} placeholder="Panele Giriş Yap" />
              </Field>
              <Field label="Giriş ekranı açıklaması">
                <TextInput value={form.login_description ?? ""} onChange={(v) => setF("login_description", v || null)} placeholder="Hesabınıza erişmek için giriş yapın." />
              </Field>
            </div>
          </Card>

          <Card title="Renkler" description="Kritik kontrast sorunlarında uyarı gösterilir; kaydetmeyi engellemez.">
            <div className="grid grid-cols-2 gap-4">
              <ColorField label="Birincil renk" value={form.primary_color ?? ""} onChange={(v) => setF("primary_color", v)} contrastAgainst={form.background_color || defaults.background_color || "#0B0B12"} />
              <ColorField label="Vurgu rengi" value={form.accent_color ?? ""} onChange={(v) => setF("accent_color", v)} contrastAgainst={form.background_color || defaults.background_color || "#0B0B12"} />
              <ColorField label="Arka plan rengi" value={form.background_color ?? ""} onChange={(v) => setF("background_color", v)} />
              <ColorField label="Yüzey/kart rengi" value={form.surface_color ?? ""} onChange={(v) => setF("surface_color", v)} />
              <ColorField label="Metin rengi" value={form.text_color ?? ""} onChange={(v) => setF("text_color", v)} contrastAgainst={form.background_color || defaults.background_color || "#0B0B12"} />
              <ColorField label="Link/buton rengi" value={form.link_color ?? ""} onChange={(v) => setF("link_color", v)} contrastAgainst={form.background_color || defaults.background_color || "#0B0B12"} />
            </div>
          </Card>

          <Card title="Görseller" description="PNG, JPEG, WebP veya GIF. Maksimum 5 MB.">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              <UploadField label="Logo (açık tema)" hint="Giriş ve header'da kullanılır." currentUrl={defaults.logo_url} uploading={uploading === "logo"} onFile={(f) => handleUpload("logo", f)} />
              <UploadField label="Logo (koyu tema)" hint="Koyu arka planlarda kullanılır." currentUrl={defaults.logo_dark_url} uploading={uploading === "logo_dark"} onFile={(f) => handleUpload("logo_dark", f)} />
              <UploadField label="Favicon" hint="Tarayıcı sekmesinde görünür." currentUrl={defaults.favicon_url} uploading={uploading === "favicon"} onFile={(f) => handleUpload("favicon", f)} />
            </div>
          </Card>

          <Card title="İletişim & Footer">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="E-posta gönderen adı">
                <TextInput value={form.email_from_name ?? ""} onChange={(v) => setF("email_from_name", v || null)} placeholder="Flobrief Bildirimleri" />
              </Field>
              <Field label="Destek e-postası">
                <TextInput value={form.support_email ?? ""} onChange={(v) => setF("support_email", v || null)} placeholder="destek@postpiloter.com" type="email" />
              </Field>
              <Field label="Kullanım koşulları bağlantısı">
                <TextInput value={form.terms_url ?? ""} onChange={(v) => setF("terms_url", v || null)} placeholder="https://postpiloter.com/terms" />
              </Field>
              <Field label="Gizlilik politikası bağlantısı">
                <TextInput value={form.privacy_url ?? ""} onChange={(v) => setF("privacy_url", v || null)} placeholder="https://postpiloter.com/privacy" />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Footer metni">
                  <TextInput value={form.footer_text ?? ""} onChange={(v) => setF("footer_text", v || null)} placeholder="© 2026 Flobrief. Tüm hakları saklıdır." />
                </Field>
              </div>
            </div>
          </Card>

          <Card
            title="Sosyal Bağlantılar"
            action={
              <button
                onClick={() => setSocialInputs((prev) => [...prev, { key: "", value: "" }])}
                className="text-xs text-accent hover:text-accent-hover transition-colors"
              >
                + Ekle
              </button>
            }
          >
            {socialInputs.length === 0 ? (
              <p className="text-xs text-text-muted opacity-60">Henüz sosyal bağlantı eklenmedi.</p>
            ) : (
              <div className="space-y-2">
                {socialInputs.map((s, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      value={s.key}
                      onChange={(e) => setSocialInputs((prev) => prev.map((p, j) => (j === i ? { ...p, key: e.target.value } : p)))}
                      placeholder="linkedin"
                      className="w-32 bg-surface-2 border border-border rounded-lg px-2.5 py-1.5 text-xs text-text focus:outline-none focus:border-accent"
                    />
                    <input
                      value={s.value}
                      onChange={(e) => setSocialInputs((prev) => prev.map((p, j) => (j === i ? { ...p, value: e.target.value } : p)))}
                      placeholder="https://linkedin.com/company/flobrief"
                      className="flex-1 bg-surface-2 border border-border rounded-lg px-2.5 py-1.5 text-xs font-mono text-text focus:outline-none focus:border-accent"
                    />
                    <button onClick={() => setSocialInputs((prev) => prev.filter((_, j) => j !== i))} className="text-text-muted hover:text-danger transition-colors px-1">
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <div className="bg-surface-2 border border-border rounded-xl p-4">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Özel Domain</p>
            <p className="text-xs text-text-muted leading-relaxed">
              Özel alan adları ajans bazında yönetilir. Bir ajansın domain durumunu görüntülemek için
              Ajanslar → ilgili ajans → <span className="text-accent">White Label</span> sekmesine bakın.
            </p>
          </div>
        </div>

        <div>
          <LivePreview form={form} defaults={defaults} target={previewTarget} onTargetChange={setPreviewTarget} />
        </div>
      </div>
    </div>
  );
}
