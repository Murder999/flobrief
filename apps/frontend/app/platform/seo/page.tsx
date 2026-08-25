"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  platformApi,
  type PlatformSeoPageRead,
  type PlatformGrowthSettingsRead,
  type PlatformGrowthMetrics,
  type PlatformSeoAuditIssue,
  type PlatformSeoPageInventoryItem,
  type PlatformSeoHealthSummary,
  type PlatformPageSpeedResult,
  type PlatformIntegrationStatus,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";

// ── Helpers ───────────────────────────────────────────────────────────────────

type TabId = "genel" | "envanter" | "denetim" | "seo" | "takip" | "pagespeed" | "entegrasyonlar" | "robots" | "utm" | "metrikler";

const SEVERITY_LABELS: Record<string, { label: string; cls: string }> = {
  critical: { label: "Kritik", cls: "status-danger" },
  high: { label: "Yüksek", cls: "status-danger" },
  medium: { label: "Orta", cls: "status-warning" },
  low: { label: "Düşük", cls: "status-neutral" },
};

// ── Health overview ───────────────────────────────────────────────────────────

function HealthOverview({ health, issues }: { health: PlatformSeoHealthSummary | null; issues: PlatformSeoAuditIssue[] }) {
  if (!health) return <div className="text-center py-12 text-text-muted opacity-60">Yüklenemedi.</div>;
  const scoreColor = health.health_score >= 80 ? "text-success" : health.health_score >= 50 ? "text-warning" : "text-danger";
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-surface border border-border rounded-xl p-5 text-center">
          <p className={`text-4xl font-bold ${scoreColor}`}>{health.health_score}</p>
          <p className="text-xs text-text-muted mt-1">SEO Sağlık Skoru</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-5 text-center">
          <p className="text-4xl font-bold text-danger">{health.critical_count}</p>
          <p className="text-xs text-text-muted mt-1">Kritik / Yüksek Sorun</p>
        </div>
        <div className="bg-surface border border-border rounded-xl p-5 text-center">
          <p className="text-4xl font-bold text-warning">{health.warning_count}</p>
          <p className="text-xs text-text-muted mt-1">Orta / Düşük Sorun</p>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="bg-surface-2 border border-border rounded-lg p-3">
          <p className="text-text-muted">İndexlenebilir sayfa</p>
          <p className="text-text font-semibold mt-1">{health.indexable_page_count}</p>
        </div>
        <div className="bg-surface-2 border border-border rounded-lg p-3">
          <p className="text-text-muted">Eksik title</p>
          <p className="text-text font-semibold mt-1">{health.missing_title_count}</p>
        </div>
        <div className="bg-surface-2 border border-border rounded-lg p-3">
          <p className="text-text-muted">Sitemap</p>
          <p className={`font-semibold mt-1 ${health.sitemap_configured ? "text-success" : "text-danger"}`}>{health.sitemap_configured ? "Hazır" : "Eksik"}</p>
        </div>
        <div className="bg-surface-2 border border-border rounded-lg p-3">
          <p className="text-text-muted">robots.txt</p>
          <p className={`font-semibold mt-1 ${health.robots_configured ? "text-success" : "text-danger"}`}>{health.robots_configured ? "Hazır" : "Eksik"}</p>
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">En Öncelikli Sorunlar</p>
        <div className="space-y-2">
          {issues.slice(0, 5).map((issue, i) => {
            const sev = SEVERITY_LABELS[issue.severity] ?? SEVERITY_LABELS.low;
            return (
              <div key={i} className="bg-surface border border-border rounded-xl px-4 py-3 flex items-start gap-3">
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${sev.cls} flex-shrink-0 mt-0.5`}>{sev.label}</span>
                <div>
                  <p className="text-sm text-text">{issue.problem}</p>
                  <p className="text-xs text-text-muted mt-0.5">{issue.suggestion}</p>
                </div>
              </div>
            );
          })}
          {issues.length === 0 && <p className="text-sm text-text-muted opacity-60">Sorun bulunamadı.</p>}
        </div>
      </div>
    </div>
  );
}

// ── Page inventory ────────────────────────────────────────────────────────────

function PageInventory({ items }: { items: PlatformSeoPageInventoryItem[] }) {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2">
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-muted uppercase">Sayfa</th>
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-muted uppercase">Durum</th>
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-muted uppercase">Title</th>
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-muted uppercase">Index</th>
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-text-muted uppercase">Sorun</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.page_key} className="border-b border-border/50">
              <td className="px-4 py-3">
                <p className="font-medium text-text">{item.label}</p>
                <p className="text-xs text-text-muted opacity-60 font-mono">{item.path ?? "—"}</p>
              </td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-0.5 rounded-md ${item.status === "published" ? "status-success" : "status-neutral"}`}>
                  {item.status === "published" ? "Yayında" : "Henüz Yok"}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-text-muted max-w-[200px] truncate">{item.title ?? "—"}</td>
              <td className="px-4 py-3 text-xs">{item.indexable ? "Evet" : "Hayır"}</td>
              <td className="px-4 py-3">
                {item.status === "not_built" ? (
                  <span className="text-xs text-text-muted opacity-60">—</span>
                ) : (
                  <span className={`text-xs px-2 py-0.5 rounded-md ${item.severity === "critical" ? "status-danger" : item.severity === "warning" ? "status-warning" : "status-success"}`}>
                    {item.issue_count} sorun
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Audit list ────────────────────────────────────────────────────────────────

function AuditIssueList({ issues }: { issues: PlatformSeoAuditIssue[] }) {
  if (issues.length === 0) {
    return <div className="text-center py-12 text-success">Tüm kontroller temiz.</div>;
  }
  return (
    <div className="space-y-2">
      {issues.map((issue, i) => {
        const sev = SEVERITY_LABELS[issue.severity] ?? SEVERITY_LABELS.low;
        return (
          <div key={i} className="bg-surface border border-border rounded-xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${sev.cls}`}>{sev.label}</span>
                  <span className="text-xs text-text-muted uppercase tracking-wide">{issue.area}</span>
                </div>
                <p className="text-sm text-text font-medium">{issue.problem}</p>
                <p className="text-xs text-text-muted mt-1">{issue.reason}</p>
                <p className="text-xs text-accent mt-1.5">→ {issue.suggestion}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── PageSpeed panel ───────────────────────────────────────────────────────────

function PageSpeedPanel({ configured, requiredEnv }: { configured: boolean; requiredEnv: string | undefined }) {
  const [url, setUrl] = useState("https://postpiloter.com");
  const [strategy, setStrategy] = useState<"mobile" | "desktop">("mobile");
  const [result, setResult] = useState<PlatformPageSpeedResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runScan() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const r = await platformApi.getPageSpeedResult(url, strategy, token);
      setResult(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Tarama başarısız.");
    } finally {
      setLoading(false);
    }
  }

  if (!configured) {
    return (
      <div className="bg-surface border border-border rounded-xl p-6 text-center">
        <p className="text-sm font-medium text-text mb-1">PageSpeed Insights bağlı değil</p>
        <p className="text-xs text-text-muted max-w-md mx-auto mb-3">
          Gerçek performans verisi göstermek için Google PageSpeed Insights API anahtarı gerekir.
        </p>
        <code className="text-xs bg-surface-2 border border-border rounded-lg px-3 py-1.5 inline-block font-mono text-text-secondary">
          {requiredEnv ?? "PAGESPEED_API_KEY"}
        </code>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card title="PageSpeed Taraması">
        <div className="flex items-center gap-2 flex-wrap">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="flex-1 min-w-[220px] bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-mono text-text focus:outline-none focus:border-accent"
          />
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as "mobile" | "desktop")}
            className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            <option value="mobile">Mobil</option>
            <option value="desktop">Masaüstü</option>
          </select>
          <button
            onClick={runScan}
            disabled={loading || !url.trim()}
            className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition-colors"
          >
            {loading ? "Taranıyor…" : "Tara"}
          </button>
        </div>
        {error && <p className="text-xs text-danger mt-2">{error}</p>}
      </Card>

      {result && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Performans", value: result.performance_score },
            { label: "Erişilebilirlik", value: result.accessibility_score },
            { label: "Best Practices", value: result.best_practices_score },
            { label: "SEO", value: result.seo_score },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface border border-border rounded-xl p-4 text-center">
              <p className={`text-2xl font-bold ${value === null ? "text-text-muted" : value >= 90 ? "text-success" : value >= 50 ? "text-warning" : "text-danger"}`}>
                {value ?? "—"}
              </p>
              <p className="text-xs text-text-muted mt-1">{label}</p>
            </div>
          ))}
          {[
            { label: "LCP", value: result.lcp },
            { label: "CLS", value: result.cls },
            { label: "FCP", value: result.fcp },
            { label: "TBT", value: result.tbt },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface-2 border border-border rounded-xl p-3 text-center">
              <p className="text-sm font-semibold text-text">{value ?? "—"}</p>
              <p className="text-xs text-text-muted mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Integrations panel ────────────────────────────────────────────────────────

function IntegrationCard({ title, description, status }: { title: string; description: string; status: PlatformIntegrationStatus | null }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        {status && (
          <span className={`text-xs px-2 py-0.5 rounded-md ${status.configured ? "status-success" : "status-neutral"}`}>
            {status.configured ? "Bağlı" : "Kurulum Gerekli"}
          </span>
        )}
      </div>
      <p className="text-xs text-text-muted mb-3">{description}</p>
      {status && !status.configured && (
        <div className="bg-surface-2 border border-border rounded-lg p-3 space-y-1.5">
          {status.detail.required_env && (
            <p className="text-xs text-text-secondary">
              Gerekli ortam değişkenleri: <code className="font-mono text-accent">{status.detail.required_env}</code>
            </p>
          )}
          {status.detail.instructions && (
            <p className="text-xs text-text-muted leading-relaxed">{status.detail.instructions}</p>
          )}
        </div>
      )}
      {status?.configured && (
        <div className="bg-success/10 border border-success/20 rounded-lg p-3">
          <p className="text-xs text-success">Kimlik bilgileri tanımlı. Veri senkronizasyonu için servis hesabı erişiminin doğru mülke tanımlandığından emin olun.</p>
        </div>
      )}
    </div>
  );
}

function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">{title}</h3>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-text-muted mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  mono,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent transition-colors ${mono ? "font-mono text-xs" : ""}`}
    />
  );
}

function SaveButton({ onClick, saving, disabled }: { onClick: () => void; saving: boolean; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={saving || disabled}
      className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition-colors"
    >
      {saving ? "Kaydediliyor…" : "Kaydet"}
    </button>
  );
}

function Toast({ toast }: { toast: { type: "ok" | "err"; msg: string } | null }) {
  if (!toast) return null;
  return (
    <div className={`fixed bottom-6 right-6 z-50 rounded-xl px-5 py-3 text-sm font-medium shadow-xl ${toast.type === "ok" ? "bg-success text-white" : "bg-danger text-white"}`}>
      {toast.msg}
    </div>
  );
}

// ── SEO pages editor ──────────────────────────────────────────────────────────

const PAGE_KEY_LABELS: Record<string, string> = {
  home: "Ana Sayfa",
  pricing: "Fiyatlandırma",
  about: "Hakkımızda",
  contact: "İletişim",
  features: "Özellikler",
  blog: "Blog",
};

interface SeoEditorProps {
  pages: PlatformSeoPageRead[];
  onSaved: (p: PlatformSeoPageRead) => void;
  onToast: (type: "ok" | "err", msg: string) => void;
}

function SeoEditor({ pages, onSaved, onToast }: SeoEditorProps) {
  const defaultPage = pages[0] ?? null;
  const [selectedKey, setSelectedKey] = useState(defaultPage?.page_key ?? "home");
  const currentPage = pages.find((p) => p.page_key === selectedKey);
  const [form, setForm] = useState<Partial<PlatformSeoPageRead>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (currentPage) {
      setForm({
        title: currentPage.title ?? "",
        description: currentPage.description ?? "",
        canonical_url: currentPage.canonical_url ?? "",
        og_title: currentPage.og_title ?? "",
        og_description: currentPage.og_description ?? "",
        og_image_url: currentPage.og_image_url ?? "",
        twitter_title: currentPage.twitter_title ?? "",
        twitter_description: currentPage.twitter_description ?? "",
        indexable: currentPage.indexable,
        follow_links: currentPage.follow_links,
      });
    } else {
      setForm({ title: "", description: "", canonical_url: "", og_title: "", og_description: "", og_image_url: "", twitter_title: "", twitter_description: "", indexable: true, follow_links: true });
    }
  }, [selectedKey, currentPage?.page_key]); // eslint-disable-line react-hooks/exhaustive-deps

  function setF(key: string, value: string | boolean) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true);
    try {
      const updated = await platformApi.updateSeoPage(selectedKey, {
        title: form.title || null,
        description: form.description || null,
        canonical_url: form.canonical_url || null,
        og_title: form.og_title || null,
        og_description: form.og_description || null,
        og_image_url: form.og_image_url || null,
        twitter_title: form.twitter_title || null,
        twitter_description: form.twitter_description || null,
        indexable: form.indexable,
        follow_links: form.follow_links,
      }, token);
      onSaved(updated);
      onToast("ok", `"${PAGE_KEY_LABELS[selectedKey] ?? selectedKey}" SEO ayarları kaydedildi.`);
    } catch {
      onToast("err", "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  }

  const knownKeys = ["home", "pricing", "about", "contact", "features", "blog"];
  const allKeys = Array.from(new Set([...knownKeys, ...pages.map((p) => p.page_key)]));

  return (
    <div className="space-y-5">
      {/* Page selector */}
      <div className="flex items-center gap-2 flex-wrap">
        {allKeys.map((k) => (
          <button
            key={k}
            onClick={() => setSelectedKey(k)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${selectedKey === k ? "bg-accent text-white" : "bg-surface-2 border border-border text-text-muted hover:text-text"}`}
          >
            {PAGE_KEY_LABELS[k] ?? k}
          </button>
        ))}
      </div>

      <Card title="Temel Meta Etiketleri" action={<SaveButton onClick={handleSave} saving={saving} />}>
        <div className="grid grid-cols-1 gap-4">
          <Field label="Sayfa başlığı (title)">
            <TextInput value={String(form.title ?? "")} onChange={(v) => setF("title", v)} placeholder="PostPiloter — Brief Yönetim Platformu" />
          </Field>
          <Field label="Açıklama (meta description, maks 160 karakter)">
            <textarea
              value={String(form.description ?? "")}
              onChange={(e) => setF("description", e.target.value)}
              rows={3}
              maxLength={160}
              placeholder="Ajanslar ve markalar için premium brief yönetim platformu."
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent resize-none transition-colors"
            />
            <p className="text-xs text-text-muted opacity-60 mt-1">{String(form.description ?? "").length}/160</p>
          </Field>
          <Field label="Canonical URL">
            <TextInput value={String(form.canonical_url ?? "")} onChange={(v) => setF("canonical_url", v)} placeholder="https://postpiloter.com/" mono />
          </Field>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(form.indexable)}
                onChange={(e) => setF("indexable", e.target.checked)}
                className="w-4 h-4 rounded accent-accent"
              />
              <span className="text-sm text-text-secondary">Arama motorlarına indexle</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(form.follow_links)}
                onChange={(e) => setF("follow_links", e.target.checked)}
                className="w-4 h-4 rounded accent-accent"
              />
              <span className="text-sm text-text-secondary">Linkleri takip et (follow)</span>
            </label>
          </div>
        </div>
      </Card>

      <Card title="Open Graph (OG) Etiketleri">
        <div className="grid grid-cols-1 gap-4">
          <Field label="OG Başlık"><TextInput value={String(form.og_title ?? "")} onChange={(v) => setF("og_title", v)} placeholder="PostPiloter — Brief Yönetim Platformu" /></Field>
          <Field label="OG Açıklama">
            <textarea
              value={String(form.og_description ?? "")}
              onChange={(e) => setF("og_description", e.target.value)}
              rows={2}
              placeholder="Ajanslar ve markalar için premium brief yönetim platformu."
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent resize-none transition-colors"
            />
          </Field>
          <Field label="OG Görsel URL"><TextInput value={String(form.og_image_url ?? "")} onChange={(v) => setF("og_image_url", v)} placeholder="https://postpiloter.com/og-image.png" mono /></Field>
        </div>
      </Card>

      <Card title="Twitter / X Kartı">
        <div className="grid grid-cols-1 gap-4">
          <Field label="Twitter Başlık"><TextInput value={String(form.twitter_title ?? "")} onChange={(v) => setF("twitter_title", v)} placeholder="PostPiloter — Brief Yönetim Platformu" /></Field>
          <Field label="Twitter Açıklama">
            <textarea
              value={String(form.twitter_description ?? "")}
              onChange={(e) => setF("twitter_description", e.target.value)}
              rows={2}
              placeholder="Ajanslar ve markalar için premium brief yönetim platformu."
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent resize-none transition-colors"
            />
          </Field>
        </div>
      </Card>

      {currentPage && (
        <p className="text-xs text-text-muted opacity-60">Son güncelleme: {new Date(currentPage.updated_at).toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
      )}
    </div>
  );
}

// ── Tracking editor ───────────────────────────────────────────────────────────

interface TrackingEditorProps {
  settings: PlatformGrowthSettingsRead | null;
  onToast: (type: "ok" | "err", msg: string) => void;
}

function TrackingEditor({ settings, onToast }: TrackingEditorProps) {
  const [form, setForm] = useState({
    google_analytics_id: settings?.google_analytics_id ?? "",
    google_tag_manager_id: settings?.google_tag_manager_id ?? "",
    search_console_verification: settings?.search_console_verification ?? "",
    meta_pixel_id: settings?.meta_pixel_id ?? "",
    linkedin_partner_id: settings?.linkedin_partner_id ?? "",
    public_app_url: settings?.public_app_url ?? "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings) {
      setForm({
        google_analytics_id: settings.google_analytics_id ?? "",
        google_tag_manager_id: settings.google_tag_manager_id ?? "",
        search_console_verification: settings.search_console_verification ?? "",
        meta_pixel_id: settings.meta_pixel_id ?? "",
        linkedin_partner_id: settings.linkedin_partner_id ?? "",
        public_app_url: settings.public_app_url ?? "",
      });
    }
  }, [settings]);

  async function handleSave() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true);
    try {
      await platformApi.updateTracking({
        google_analytics_id: form.google_analytics_id || null,
        google_tag_manager_id: form.google_tag_manager_id || null,
        search_console_verification: form.search_console_verification || null,
        meta_pixel_id: form.meta_pixel_id || null,
        linkedin_partner_id: form.linkedin_partner_id || null,
        public_app_url: form.public_app_url || null,
      }, token);
      onToast("ok", "Takip ayarları kaydedildi.");
    } catch {
      onToast("err", "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  }

  function setF(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <Card title="Analitik & İzleme Kodları" action={<SaveButton onClick={handleSave} saving={saving} />}>
      <div className="grid grid-cols-1 gap-4">
        <Field label="Google Analytics ID (G-XXXXXXXX veya UA-XXXXXXXX)">
          <TextInput value={form.google_analytics_id} onChange={(v) => setF("google_analytics_id", v)} placeholder="G-XXXXXXXXXX" mono />
        </Field>
        <Field label="Google Tag Manager ID (GTM-XXXXXXX)">
          <TextInput value={form.google_tag_manager_id} onChange={(v) => setF("google_tag_manager_id", v)} placeholder="GTM-XXXXXXX" mono />
        </Field>
        <Field label="Search Console Doğrulama Kodu">
          <TextInput value={form.search_console_verification} onChange={(v) => setF("search_console_verification", v)} placeholder="google1234567890abcdef.html" mono />
        </Field>
        <Field label="Meta (Facebook) Pixel ID">
          <TextInput value={form.meta_pixel_id} onChange={(v) => setF("meta_pixel_id", v)} placeholder="123456789012345" mono />
        </Field>
        <Field label="LinkedIn Partner ID">
          <TextInput value={form.linkedin_partner_id} onChange={(v) => setF("linkedin_partner_id", v)} placeholder="1234567" mono />
        </Field>
        <Field label="Public App URL (sitemap & canonical için)">
          <TextInput value={form.public_app_url} onChange={(v) => setF("public_app_url", v)} placeholder="https://postpiloter.com" mono />
        </Field>
      </div>
    </Card>
  );
}

// ── Robots editor ─────────────────────────────────────────────────────────────

interface RobotsEditorProps {
  robotsTxt: string | null;
  onToast: (type: "ok" | "err", msg: string) => void;
}

const DEFAULT_ROBOTS = `User-agent: *
Allow: /
Disallow: /platform/
Disallow: /dashboard/
Disallow: /api/

Sitemap: https://postpiloter.com/sitemap.xml`;

function RobotsEditor({ robotsTxt, onToast }: RobotsEditorProps) {
  const [content, setContent] = useState(robotsTxt ?? DEFAULT_ROBOTS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (robotsTxt) setContent(robotsTxt);
  }, [robotsTxt]);

  async function handleSave() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setSaving(true);
    try {
      await platformApi.updateRobots(content, token);
      onToast("ok", "robots.txt güncellendi.");
    } catch {
      onToast("err", "Kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="robots.txt Editörü" action={<SaveButton onClick={handleSave} saving={saving} />}>
      <p className="text-xs text-text-muted mb-3">
        Arama motorlarının hangi sayfaları tarayabileceğini kontrol edin. Hatalı yapılandırma SEO puanınızı olumsuz etkileyebilir.
      </p>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={12}
        spellCheck={false}
        className="w-full bg-surface-2 border border-border rounded-lg px-4 py-3 text-xs font-mono text-text placeholder:text-text-placeholder focus:outline-none focus:border-accent resize-none transition-colors"
      />
      <p className="text-xs text-text-muted opacity-60 mt-2">{content.split("\n").length} satır · {content.length} karakter</p>
    </Card>
  );
}

// ── Sitemap ───────────────────────────────────────────────────────────────────

interface SitemapCardProps {
  lastGenerated: string | null;
  onToast: (type: "ok" | "err", msg: string) => void;
  onRegenerated: (at: string) => void;
}

function SitemapCard({ lastGenerated, onToast, onRegenerated }: SitemapCardProps) {
  const [regenerating, setRegenerating] = useState(false);

  async function handleRegenerate() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setRegenerating(true);
    try {
      const result = await platformApi.regenerateSitemap(token);
      onRegenerated(result.generated_at);
      onToast("ok", "sitemap.xml yeniden oluşturuldu.");
    } catch {
      onToast("err", "Sitemap oluşturulamadı.");
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <Card title="sitemap.xml Yönetimi">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-secondary">Son oluşturma:</p>
          <p className="text-xs text-text-muted mt-0.5">
            {lastGenerated
              ? new Date(lastGenerated).toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })
              : "Henüz oluşturulmamış"}
          </p>
        </div>
        <button
          onClick={handleRegenerate}
          disabled={regenerating}
          className="flex items-center gap-2 px-4 py-2 bg-surface-2 border border-border hover:border-accent text-sm text-text-secondary hover:text-text rounded-lg transition-all disabled:opacity-50"
        >
          <svg className={`w-4 h-4 ${regenerating ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {regenerating ? "Oluşturuluyor…" : "Yeniden Oluştur"}
        </button>
      </div>
    </Card>
  );
}

// ── UTM Builder ───────────────────────────────────────────────────────────────

function UtmBuilder() {
  const [baseUrl, setBaseUrl] = useState("");
  const [source, setSource] = useState("");
  const [medium, setMedium] = useState("");
  const [campaign, setCampaign] = useState("");
  const [term, setTerm] = useState("");
  const [content, setContent] = useState("");
  const [copied, setCopied] = useState(false);

  const utmParams = new URLSearchParams();
  if (source) utmParams.set("utm_source", source);
  if (medium) utmParams.set("utm_medium", medium);
  if (campaign) utmParams.set("utm_campaign", campaign);
  if (term) utmParams.set("utm_term", term);
  if (content) utmParams.set("utm_content", content);

  const utmString = utmParams.toString();
  const generatedUrl = baseUrl
    ? `${baseUrl.replace(/\/$/, "")}${utmString ? `?${utmString}` : ""}`
    : "";

  function handleCopy() {
    if (!generatedUrl) return;
    navigator.clipboard.writeText(generatedUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Card title="UTM Link Oluşturucu">
      <div className="grid grid-cols-1 gap-4">
        <Field label="Hedef URL">
          <TextInput value={baseUrl} onChange={setBaseUrl} placeholder="https://postpiloter.com/pricing" mono />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Kaynak (utm_source)">
            <TextInput value={source} onChange={setSource} placeholder="newsletter, google, linkedin" />
          </Field>
          <Field label="Mecra (utm_medium)">
            <TextInput value={medium} onChange={setMedium} placeholder="email, cpc, social" />
          </Field>
          <Field label="Kampanya (utm_campaign)">
            <TextInput value={campaign} onChange={setCampaign} placeholder="q1_launch, black_friday" />
          </Field>
          <Field label="Anahtar kelime (utm_term)">
            <TextInput value={term} onChange={setTerm} placeholder="brief yönetimi" />
          </Field>
          <Field label="İçerik (utm_content)">
            <TextInput value={content} onChange={setContent} placeholder="banner_a, link_1" />
          </Field>
        </div>

        {generatedUrl && (
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Oluşturulan Link</label>
            <div className="flex items-center gap-2 bg-surface-2 border border-border rounded-lg px-3 py-2.5">
              <p className="flex-1 text-xs font-mono text-accent break-all">{generatedUrl}</p>
              <button
                onClick={handleCopy}
                className="flex-shrink-0 text-xs text-text-muted hover:text-text transition-colors"
              >
                {copied ? (
                  <span className="text-success text-xs">Kopyalandı!</span>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

// ── Growth Metrics ────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <p className="text-2xl font-bold text-text">{value.toLocaleString("tr-TR")}</p>
      <p className="text-xs font-medium text-text-secondary mt-1">{label}</p>
      {sub && <p className="text-xs text-text-muted opacity-60 mt-0.5">{sub}</p>}
    </div>
  );
}

interface MetricsProps {
  metrics: PlatformGrowthMetrics;
}

function GrowthMetrics({ metrics }: MetricsProps) {
  const funnelItems = [
    { label: "Toplam Ajans", value: metrics.total_agencies },
    { label: "Marka Ekleyenler", value: metrics.agencies_with_first_brand, sub: "En az 1 marka" },
    { label: "Brief Oluşturanlar", value: metrics.agencies_with_first_brief, sub: "En az 1 brief" },
  ];

  const conversionRate = metrics.total_agencies > 0
    ? Math.round((metrics.agencies_with_first_brief / metrics.total_agencies) * 100)
    : 0;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <MetricCard label="Toplam Ajans" value={metrics.total_agencies} />
        <MetricCard label="Aktif Ajans" value={metrics.active_agencies} />
        <MetricCard label="Toplam Marka" value={metrics.total_brands} />
        <MetricCard label="Aktif Marka" value={metrics.active_brands} />
        <MetricCard label="Toplam Kullanıcı" value={metrics.total_users} />
        <MetricCard label="Bu Ay Yeni Kullanıcı" value={metrics.new_users_this_month} sub="Mevcut ay" />
      </div>

      <Card title="Bu Ay">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-surface-2 border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-accent">+{metrics.new_agencies_this_month}</p>
            <p className="text-xs text-text-muted mt-1">Yeni Ajans</p>
          </div>
          <div className="bg-surface-2 border border-border rounded-xl p-4">
            <p className="text-2xl font-bold text-accent">+{metrics.new_users_this_month}</p>
            <p className="text-xs text-text-muted mt-1">Yeni Kullanıcı</p>
          </div>
        </div>
      </Card>

      <Card title="Aktivasyon Hunisi">
        <div className="space-y-3">
          {funnelItems.map((item, i) => {
            const pct = metrics.total_agencies > 0
              ? Math.round((item.value / metrics.total_agencies) * 100)
              : 0;
            return (
              <div key={i}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text-muted">{item.label}</span>
                  <span className="text-text-secondary font-medium">{item.value} <span className="text-text-muted">({pct}%)</span></span>
                </div>
                <div className="h-2 bg-surface-2 rounded-full overflow-hidden">
                  <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-text-muted opacity-60 mt-4">
          Brief dönüşüm oranı: <span className="text-accent font-medium">%{conversionRate}</span>
        </p>
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlatformSeoPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("genel");
  const [seoPages, setSeoPages] = useState<PlatformSeoPageRead[]>([]);
  const [tracking, setTracking] = useState<PlatformGrowthSettingsRead | null>(null);
  const [robotsTxt, setRobotsTxt] = useState<string | null>(null);
  const [sitemapAt, setSitemapAt] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<PlatformGrowthMetrics | null>(null);
  const [auditIssues, setAuditIssues] = useState<PlatformSeoAuditIssue[]>([]);
  const [pageInventory, setPageInventory] = useState<PlatformSeoPageInventoryItem[]>([]);
  const [health, setHealth] = useState<PlatformSeoHealthSummary | null>(null);
  const [pagespeedStatus, setPagespeedStatus] = useState<PlatformIntegrationStatus | null>(null);
  const [gscStatus, setGscStatus] = useState<PlatformIntegrationStatus | null>(null);
  const [ga4Status, setGa4Status] = useState<PlatformIntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  function showToast(type: "ok" | "err", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3500);
  }

  useEffect(() => {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    Promise.all([
      platformApi.listSeoPages(token).catch(() => []),
      platformApi.getTracking(token).catch(() => null),
      platformApi.getRobots(token).catch(() => ({ robots_txt: null })),
      platformApi.getGrowthMetrics(token).catch(() => null),
      platformApi.getSeoAudit(token).catch(() => []),
      platformApi.getSeoPageInventory(token).catch(() => []),
      platformApi.getSeoHealth(token).catch(() => null),
      platformApi.getIntegrationStatus("pagespeed", token).catch(() => null),
      platformApi.getIntegrationStatus("search-console", token).catch(() => null),
      platformApi.getIntegrationStatus("ga4", token).catch(() => null),
    ]).then(([pages, track, robots, met, audit, inventory, healthSummary, psStatus, gsc, ga4]) => {
      setSeoPages(pages);
      setTracking(track);
      setRobotsTxt(robots?.robots_txt ?? null);
      setSitemapAt(track?.sitemap_last_generated_at ?? null);
      setMetrics(met);
      setAuditIssues(audit);
      setPageInventory(inventory);
      setHealth(healthSummary);
      setPagespeedStatus(psStatus);
      setGscStatus(gsc);
      setGa4Status(ga4);
    }).finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const tabs: { id: TabId; label: string }[] = [
    { id: "genel", label: "Genel Bakış" },
    { id: "envanter", label: "Sayfa Envanteri" },
    { id: "denetim", label: `Teknik Denetim${auditIssues.length ? ` (${auditIssues.length})` : ""}` },
    { id: "seo", label: "SEO Meta" },
    { id: "takip", label: "Takip Kodları" },
    { id: "pagespeed", label: "PageSpeed" },
    { id: "entegrasyonlar", label: "Entegrasyonlar" },
    { id: "robots", label: "robots.txt" },
    { id: "utm", label: "UTM Builder" },
    { id: "metrikler", label: "Büyüme" },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">Platform Ayarları</p>
        <h1 className="text-2xl font-bold text-text">SEO & Büyüme Merkezi</h1>
        <p className="mt-1 text-sm text-text-muted">
          PostPiloter public sayfalarının arama motoru görünürlüğü, izleme kodları ve büyüme metrikleri.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-8 bg-surface-2 border border-border rounded-xl p-1 w-fit">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${activeTab === t.id ? "bg-accent text-white shadow-sm" : "text-text-muted hover:text-text-secondary"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div>
          {activeTab === "genel" && <HealthOverview health={health} issues={auditIssues} />}
          {activeTab === "envanter" && <PageInventory items={pageInventory} />}
          {activeTab === "denetim" && <AuditIssueList issues={auditIssues} />}
          {activeTab === "pagespeed" && (
            <PageSpeedPanel
              configured={pagespeedStatus?.configured ?? false}
              requiredEnv={pagespeedStatus?.detail?.required_env}
            />
          )}
          {activeTab === "entegrasyonlar" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <IntegrationCard
                title="Google Search Console"
                description="Tıklama, gösterim, CTR ve arama sorgusu verileri için."
                status={gscStatus}
              />
              <IntegrationCard
                title="Google Analytics 4"
                description="Kullanıcı, oturum ve dönüşüm verileri için."
                status={ga4Status}
              />
            </div>
          )}
          {activeTab === "seo" && (
            <SeoEditor
              pages={seoPages}
              onSaved={(updated) => setSeoPages((prev) => {
                const idx = prev.findIndex((p) => p.page_key === updated.page_key);
                if (idx >= 0) { const next = [...prev]; next[idx] = updated; return next; }
                return [...prev, updated];
              })}
              onToast={showToast}
            />
          )}
          {activeTab === "takip" && <TrackingEditor settings={tracking} onToast={showToast} />}
          {activeTab === "robots" && <RobotsEditor robotsTxt={robotsTxt} onToast={showToast} />}
          {activeTab === "utm" && <UtmBuilder />}
          {activeTab === "metrikler" && metrics && (
            <GrowthMetrics metrics={metrics} />
          )}
          {activeTab === "metrikler" && !metrics && (
            <div className="text-center py-12 text-text-muted opacity-60">Metrikler yüklenemedi.</div>
          )}
        </div>
      )}

      {/* Sitemap always visible */}
      {activeTab === "robots" && !loading && (
        <div className="mt-5">
          <SitemapCard
            lastGenerated={sitemapAt}
            onToast={showToast}
            onRegenerated={(at) => setSitemapAt(at)}
          />
        </div>
      )}

      <Toast toast={toast} />
    </div>
  );
}
