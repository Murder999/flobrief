"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Clock3,
  FlaskConical,
  Gauge,
  RefreshCw,
  Save,
  ShieldCheck,
  StopCircle,
  Users,
} from "lucide-react";
import {
  ApiError,
  platformApi,
  type PlatformDemoSandbox,
  type PlatformDemoSettings,
} from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";

const STATUS_LABEL: Record<string, string> = {
  active: "Aktif",
  expired: "Süresi doldu",
  terminated: "Sonlandırıldı",
};

const STATUS_CLASS: Record<string, string> = {
  active: "bg-success/10 text-success border-success/20",
  expired: "bg-warning/10 text-warning border-warning/20",
  terminated: "bg-danger/10 text-danger border-danger/20",
};

function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number | string;
  icon: React.ElementType;
  accent?: boolean;
}) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 flex items-center gap-3">
      <div
        className={`w-9 h-9 rounded-xl flex items-center justify-center ${
          accent ? "bg-accent/12 text-accent" : "bg-surface-2 text-text-muted"
        }`}
      >
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-xl font-bold text-text">{value}</p>
        <p className="text-xs text-text-muted">{label}</p>
      </div>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <label className="flex items-center justify-between gap-5 py-4 cursor-pointer">
      <span>
        <span className="block text-sm font-medium text-text">{label}</span>
        <span className="block text-xs text-text-muted mt-1">{description}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-11 h-6 rounded-full transition-colors ${
          checked ? "bg-accent" : "bg-surface-3"
        }`}
      >
        <span
          className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </label>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function PlatformDemoPage() {
  const [settings, setSettings] = useState<PlatformDemoSettings | null>(null);
  const [draft, setDraft] = useState<PlatformDemoSettings | null>(null);
  const [sandboxes, setSandboxes] = useState<PlatformDemoSandbox[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");

  const load = useCallback(async () => {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [config, rows] = await Promise.all([
        platformApi.getDemoSettings(token),
        platformApi.listDemoSandboxes(token, statusFilter || undefined),
      ]);
      setSettings(config);
      setDraft(config);
      setSandboxes(rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Demo yönetimi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const changed = useMemo(
    () =>
      Boolean(
        settings &&
          draft &&
          (settings.enabled !== draft.enabled ||
            settings.duration_hours !== draft.duration_hours ||
            settings.max_active_sandboxes !== draft.max_active_sandboxes ||
            settings.max_creations_per_ip_per_day !==
              draft.max_creations_per_ip_per_day ||
            settings.captcha_required !== draft.captcha_required)
      ),
    [settings, draft]
  );

  async function save() {
    const token = platformAuthStorage.getToken();
    if (!token || !draft) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await platformApi.updateDemoSettings(
        {
          enabled: draft.enabled,
          duration_hours: draft.duration_hours,
          max_active_sandboxes: draft.max_active_sandboxes,
          max_creations_per_ip_per_day: draft.max_creations_per_ip_per_day,
          captcha_required: draft.captcha_required,
        },
        token
      );
      setSettings(updated);
      setDraft(updated);
      setNotice("Demo sandbox ayarları kaydedildi.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ayarlar kaydedilemedi");
    } finally {
      setSaving(false);
    }
  }

  async function terminate(sandboxId: string) {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setBusyId(sandboxId);
    setError(null);
    try {
      await platformApi.terminateDemoSandbox(sandboxId, token);
      setNotice("Demo çalışma alanı sonlandırıldı.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Demo sonlandırılamadı");
    } finally {
      setBusyId(null);
    }
  }

  async function cleanup() {
    const token = platformAuthStorage.getToken();
    if (!token) return;
    setBusyId("cleanup");
    setError(null);
    try {
      const result = await platformApi.cleanupDemoSandboxes(token);
      setNotice(
        result.cleaned
          ? `${result.cleaned} süresi dolmuş demo kapatıldı.`
          : "Kapatılmayı bekleyen demo bulunamadı."
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Temizlik çalıştırılamadı");
    } finally {
      setBusyId(null);
    }
  }

  if (loading && !draft) {
    return (
      <div className="p-8 space-y-6">
        <div className="h-16 w-80 bg-surface-2 rounded-xl animate-pulse" />
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-24 bg-surface-2 rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="h-80 bg-surface-2 rounded-xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="p-5 md:p-8 max-w-7xl">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-7">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">
            Büyüme ve ürün deneyimi
          </p>
          <h1 className="text-2xl font-bold text-text tracking-tight">Demo Sandbox</h1>
          <p className="text-sm text-text-muted mt-1 max-w-2xl">
            Kamuya açık, süreli ve birbirinden izole demo çalışma alanlarını yönetin.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={cleanup}
            disabled={busyId === "cleanup"}
            className="h-9 px-3 rounded-lg border border-border bg-surface text-xs font-medium text-text-muted hover:text-text hover:border-border-hover disabled:opacity-50 flex items-center gap-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${busyId === "cleanup" ? "animate-spin" : ""}`} />
            Süresi dolanları kapat
          </button>
          <button
            type="button"
            onClick={save}
            disabled={!changed || saving}
            className="h-9 px-3 rounded-lg bg-accent text-white text-xs font-semibold hover:bg-accent-hover disabled:opacity-45 flex items-center gap-2"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-5 rounded-xl border border-danger/20 bg-danger/8 px-4 py-3 flex gap-3 text-sm text-danger">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-5 rounded-xl border border-success/20 bg-success/8 px-4 py-3 text-sm text-success">
          {notice}
        </div>
      )}

      {draft && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <MetricCard
              label="Aktif demo"
              value={draft.active_sandboxes}
              icon={FlaskConical}
              accent
            />
            <MetricCard label="Toplam oluşturulan" value={draft.total_created} icon={Users} />
            <MetricCard
              label="Kapanan demo"
              value={draft.expired_or_terminated}
              icon={StopCircle}
            />
            <MetricCard
              label="Kapasite kullanımı"
              value={`${draft.active_sandboxes}/${draft.max_active_sandboxes}`}
              icon={Gauge}
            />
          </div>

          <div className="grid lg:grid-cols-[380px_1fr] gap-6">
            <section className="bg-surface border border-border rounded-xl p-5 h-fit">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck className="w-4 h-4 text-accent" />
                <h2 className="text-sm font-semibold text-text">Yayın ayarları</h2>
              </div>
              <div className="divide-y divide-border">
                <Toggle
                  checked={draft.enabled}
                  onChange={(enabled) => setDraft({ ...draft, enabled })}
                  label="Kamuya açık demo"
                  description="Ana sayfadaki self-service demo girişini açar."
                />
                <Toggle
                  checked={draft.captcha_required}
                  onChange={(captcha_required) => setDraft({ ...draft, captcha_required })}
                  label="CAPTCHA zorunlu"
                  description="Otomatik ve kötüye kullanım amaçlı oluşturmayı engeller."
                />
              </div>

              {draft.captcha_required && !draft.captcha_configured && (
                <div className="rounded-lg border border-warning/20 bg-warning/8 p-3 text-xs text-warning leading-relaxed">
                  Turnstile anahtarları tanımlanmadan kamuya açık demo etkinleştirilemez.
                </div>
              )}

              <div className="space-y-4 mt-5">
                <label className="block">
                  <span className="text-xs font-medium text-text-muted">Demo süresi (saat)</span>
                  <input
                    type="number"
                    min={1}
                    max={72}
                    value={draft.duration_hours}
                    onChange={(event) =>
                      setDraft({ ...draft, duration_hours: Number(event.target.value) })
                    }
                    className="mt-1.5 w-full h-10 rounded-lg border border-border bg-background px-3 text-sm text-text outline-none focus:border-accent"
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-text-muted">
                    Eşzamanlı demo kapasitesi
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={draft.max_active_sandboxes}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        max_active_sandboxes: Number(event.target.value),
                      })
                    }
                    className="mt-1.5 w-full h-10 rounded-lg border border-border bg-background px-3 text-sm text-text outline-none focus:border-accent"
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-text-muted">
                    IP başına günlük oluşturma
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={draft.max_creations_per_ip_per_day}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        max_creations_per_ip_per_day: Number(event.target.value),
                      })
                    }
                    className="mt-1.5 w-full h-10 rounded-lg border border-border bg-background px-3 text-sm text-text outline-none focus:border-accent"
                  />
                </label>
              </div>
            </section>

            <section className="bg-surface border border-border rounded-xl overflow-hidden">
              <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-text">Demo çalışma alanları</h2>
                  <p className="text-xs text-text-muted mt-0.5">Son 100 sandbox kaydı</p>
                </div>
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  className="h-9 rounded-lg border border-border bg-background px-3 text-xs text-text outline-none focus:border-accent"
                >
                  <option value="">Tüm durumlar</option>
                  <option value="active">Aktif</option>
                  <option value="expired">Süresi doldu</option>
                  <option value="terminated">Sonlandırıldı</option>
                </select>
              </div>

              {sandboxes.length === 0 ? (
                <div className="py-16 text-center px-5">
                  <div className="w-12 h-12 rounded-2xl bg-surface-2 text-text-muted mx-auto flex items-center justify-center">
                    <FlaskConical className="w-5 h-5" />
                  </div>
                  <p className="text-sm font-medium text-text mt-4">Demo kaydı bulunamadı</p>
                  <p className="text-xs text-text-muted mt-1">
                    Sistem açıldığında oluşturulan çalışma alanları burada görünür.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {sandboxes.map((sandbox) => (
                    <div
                      key={sandbox.id}
                      className="px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3"
                    >
                      <div className="w-9 h-9 rounded-xl bg-accent/10 text-accent flex items-center justify-center flex-shrink-0">
                        <FlaskConical className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-text truncate">
                          {sandbox.agency_name}
                        </p>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-text-muted">
                          <span>Başlangıç: {formatDate(sandbox.created_at)}</span>
                          <span className="inline-flex items-center gap-1">
                            <Clock3 className="w-3 h-3" />
                            Bitiş: {formatDate(sandbox.expires_at)}
                          </span>
                        </div>
                      </div>
                      <span
                        className={`px-2 py-1 rounded-md border text-[11px] font-semibold ${
                          STATUS_CLASS[sandbox.status] ?? STATUS_CLASS.terminated
                        }`}
                      >
                        {STATUS_LABEL[sandbox.status] ?? sandbox.status}
                      </span>
                      {sandbox.status === "active" && (
                        <button
                          type="button"
                          onClick={() => terminate(sandbox.id)}
                          disabled={busyId === sandbox.id}
                          className="h-8 px-2.5 rounded-lg border border-danger/20 text-xs font-medium text-danger hover:bg-danger/8 disabled:opacity-50"
                        >
                          {busyId === sandbox.id ? "Kapatılıyor…" : "Sonlandır"}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
