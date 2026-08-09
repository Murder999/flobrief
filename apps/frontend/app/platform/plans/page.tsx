"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, platformApi, type PlanRead } from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import { AlertTriangle, RefreshCw, Check } from "lucide-react";

const FEATURE_FIELDS: { key: keyof PlanRead; label: string }[] = [
  { key: "white_label_enabled", label: "White-label" },
  { key: "advanced_reporting_enabled", label: "Gelişmiş raporlama" },
  { key: "pdf_export_enabled", label: "PDF dışa aktarma" },
  { key: "public_report_link_enabled", label: "Herkese açık rapor linki" },
  { key: "whatsapp_infrastructure_enabled", label: "WhatsApp bildirimleri" },
];

const LIMIT_FIELDS: { key: keyof PlanRead; label: string }[] = [
  { key: "max_brands", label: "Marka limiti" },
  { key: "max_users", label: "Kullanıcı limiti" },
  { key: "max_brief_templates", label: "Şablon limiti" },
  { key: "max_storage_gb", label: "Depolama (GB)" },
];

type Draft = Record<string, Partial<PlanRead>>;

export default function PlatformPlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<PlanRead[]>([]);
  const [draft, setDraft] = useState<Draft>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  async function load() {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await platformApi.listPlans(token);
      setPlans(data);
      setDraft({});
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        platformAuthStorage.clearAll();
        router.replace("/platform/login");
      } else {
        setError(err instanceof ApiError ? err.message : "Paketler yüklenemedi");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const valueFor = (plan: PlanRead, key: keyof PlanRead) =>
    draft[plan.id]?.[key] ?? plan[key];

  const setField = (planId: string, key: keyof PlanRead, value: unknown) => {
    setDraft((d) => ({ ...d, [planId]: { ...d[planId], [key]: value } }));
    setSavedId(null);
  };

  const isDirty = (planId: string) => Boolean(draft[planId] && Object.keys(draft[planId]).length > 0);

  async function handleSave(plan: PlanRead) {
    const token = platformAuthStorage.getToken();
    const changes = draft[plan.id];
    if (!token || !changes || Object.keys(changes).length === 0) return;
    setSavingId(plan.id);
    setError(null);
    try {
      const updated = await platformApi.updatePlan(plan.id, changes, token);
      setPlans((prev) => prev.map((p) => (p.id === plan.id ? updated : p)));
      setDraft((d) => { const next = { ...d }; delete next[plan.id]; return next; });
      setSavedId(plan.id);
      setTimeout(() => setSavedId((id) => (id === plan.id ? null : id)), 2500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kaydedilemedi");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">Kiracılar</p>
          <h1 className="text-2xl font-bold text-text tracking-tight">Paketler</h1>
          <p className="text-sm text-text-muted mt-1">
            {loading ? "Yükleniyor…" : `${plans.length} paket — özellik ve limitleri buradan yönetin`}
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

      {error && (
        <div className="mb-6 flex items-start gap-2.5 bg-danger/8 border border-danger/20 rounded-xl px-4 py-3">
          <AlertTriangle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="grid md:grid-cols-2 gap-5">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-2xl p-6 h-64 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-5">
          {plans.map((plan) => (
            <div key={plan.id} className="bg-surface border border-border rounded-2xl p-6">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-lg font-semibold text-text">{plan.name}</h2>
                <span className="text-xs font-mono text-text-muted">{plan.code}</span>
              </div>
              <p className="text-xs text-text-muted mb-5">
                ${(plan.monthly_price_cents / 100).toFixed(0)}/ay
              </p>

              <p className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2.5">Limitler</p>
              <div className="grid grid-cols-2 gap-3 mb-5">
                {LIMIT_FIELDS.map(({ key, label }) => (
                  <div key={key}>
                    <label className="block text-xs text-text-muted mb-1">{label}</label>
                    <input
                      type="number"
                      min={0}
                      value={(valueFor(plan, key) as number | null) ?? ""}
                      placeholder="Sınırsız"
                      onChange={(e) =>
                        setField(plan.id, key, e.target.value === "" ? null : Number(e.target.value))
                      }
                      className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                    />
                  </div>
                ))}
              </div>

              <p className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2.5">Özellikler</p>
              <div className="space-y-2 mb-5">
                {FEATURE_FIELDS.map(({ key, label }) => (
                  <label key={key} className="flex items-center justify-between text-sm text-text cursor-pointer">
                    {label}
                    <input
                      type="checkbox"
                      checked={Boolean(valueFor(plan, key))}
                      onChange={(e) => setField(plan.id, key, e.target.checked)}
                      className="w-4 h-4 rounded border-border text-accent focus:ring-accent/30"
                    />
                  </label>
                ))}
              </div>

              <button
                onClick={() => handleSave(plan)}
                disabled={!isDirty(plan.id) || savingId === plan.id}
                className="w-full px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors flex items-center justify-center gap-2"
              >
                {savingId === plan.id ? (
                  "Kaydediliyor…"
                ) : savedId === plan.id ? (
                  <>
                    <Check className="w-4 h-4" /> Kaydedildi
                  </>
                ) : (
                  "Kaydet"
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
