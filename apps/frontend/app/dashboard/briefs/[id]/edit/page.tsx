"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useToast } from "@/components/ui/toast";
import {
  briefApi,
  templateApi,
  agencyApi,
  type BriefDetail,
  type BriefPriority,
  type TemplateDetail,
  type BriefFieldValueIn,
  type BrandRead,
} from "@/lib/api-client";
import { BriefStatusBadge } from "@/components/briefs/brief-status-badge";
import { DynamicBriefForm } from "@/components/briefs/dynamic-brief-form";

const PRIORITY_OPTIONS: { value: BriefPriority; label: string }[] = [
  { value: "low", label: "Düşük" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "Yüksek" },
  { value: "urgent", label: "Acil" },
];

function Skeleton() {
  return (
    <div className="p-8 max-w-3xl mx-auto animate-pulse space-y-6">
      <div className="h-6 bg-surface-2 rounded w-1/3" />
      <div className="h-4 bg-surface-2 rounded w-1/4" />
      <div className="space-y-4 mt-8">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-14 bg-surface-2 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

export default function BriefEditPage() {
  const { id: briefId } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const currentAgencyId = activeAgency?.id ?? null;
  const router = useRouter();
  const { toast } = useToast();

  const [brief, setBrief] = useState<BriefDetail | null>(null);
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<BriefPriority>("normal");
  const [deadline, setDeadline] = useState("");
  const [brandId, setBrandId] = useState<string>("");

  const loadData = useCallback(async () => {
    if (!accessToken || !currentAgencyId) return;
    setLoading(true);
    setError(null);
    try {
      const [b, brandList] = await Promise.all([
        briefApi.get(briefId, currentAgencyId, accessToken),
        agencyApi.listBrands(currentAgencyId, accessToken),
      ]);
      setBrief(b);
      setBrands(brandList);
      setTitle(b.title);
      setDescription(b.description ?? "");
      setPriority(b.priority);
      setDeadline(b.deadline ? b.deadline.split("T")[0] : "");
      setBrandId(b.brand_id ?? "");
      if (b.template_id) {
        const tmpl = await templateApi.get(b.template_id, currentAgencyId, accessToken);
        setTemplate(tmpl);
      }
    } catch {
      setError("Brief yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, currentAgencyId, briefId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSave = async () => {
    if (!accessToken || !currentAgencyId || !brief) return;
    if (!title.trim()) {
      toast("Başlık zorunludur.", "error");
      return;
    }
    setSaving(true);
    try {
      await briefApi.update(
        briefId,
        {
          title: title.trim(),
          description: description.trim() || null,
          priority,
          deadline: deadline || null,
          brand_id: brandId || null,
        },
        currentAgencyId,
        accessToken
      );
      toast("Brief güncellendi.", "success");
      router.push(`/dashboard/briefs/${briefId}`);
    } catch {
      toast("Güncelleme başarısız.", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveFields = async (values: BriefFieldValueIn[]) => {
    if (!accessToken || !currentAgencyId) return;
    const updated = await briefApi.updateFieldValues(
      briefId,
      { values },
      currentAgencyId,
      accessToken
    );
    setBrief(updated);
    toast("Alanlar güncellendi.", "success");
  };

  if (loading) return <Skeleton />;

  if (error || !brief) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {error ?? "Brief bulunamadı."}
          <button onClick={loadData} className="ml-3 underline">Tekrar dene</button>
        </div>
      </div>
    );
  }

  if (brief.status === "archived") {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="rounded-xl border border-border bg-surface px-5 py-8 text-center">
          <p className="text-text-muted text-sm">Arşivlenmiş briefler düzenlenemez.</p>
          <button
            onClick={() => router.push(`/dashboard/briefs/${briefId}`)}
            className="mt-3 text-sm text-accent hover:underline"
          >
            ← Detaya Dön
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Back */}
      <button
        onClick={() => router.push(`/dashboard/briefs/${briefId}`)}
        className="text-sm text-text-muted hover:text-text transition-colors mb-6 flex items-center gap-1.5"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Brief Detayı
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-8">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-text">Brief Düzenle</h1>
            <BriefStatusBadge status={brief.status} />
          </div>
          <p className="text-sm text-text-muted mt-1">
            Temel bilgileri ve şablon alanlarını güncelleyin
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => router.push(`/dashboard/briefs/${briefId}`)}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text-muted hover:border-text-muted hover:text-text transition-colors"
          >
            İptal
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-60 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {saving ? (
              <>
                <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Kaydediliyor...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Kaydet
              </>
            )}
          </button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Core fields */}
        <div className="bg-surface rounded-xl border border-border p-6 space-y-5">
          <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wide">
            Temel Bilgiler
          </h2>

          {/* Title */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted">
              Başlık <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Brief başlığı"
              className="w-full px-4 py-3 rounded-xl bg-bg border border-border text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-colors text-sm"
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted">Açıklama</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief hakkında kısa açıklama..."
              rows={3}
              className="w-full px-4 py-3 rounded-xl bg-bg border border-border text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-colors text-sm resize-none"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Priority */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted">Öncelik</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as BriefPriority)}
                className="w-full px-4 py-3 rounded-xl bg-bg border border-border text-text focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-colors text-sm appearance-none cursor-pointer"
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>

            {/* Deadline */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted">Son Tarih</label>
              <input
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-bg border border-border text-text focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-colors text-sm"
              />
            </div>

            {/* Brand */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted">Marka</label>
              <select
                value={brandId}
                onChange={(e) => setBrandId(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-bg border border-border text-text focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent transition-colors text-sm appearance-none cursor-pointer"
              >
                <option value="">— Marka yok —</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Template fields */}
        {template && template.sections.length > 0 && (
          <div className="bg-surface rounded-xl border border-border p-6 space-y-4">
            <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wide">
              Şablon Alanları
            </h2>
            <DynamicBriefForm
              sections={template.sections}
              initialValues={brief.field_values}
              onSave={handleSaveFields}
              readOnly={false}
            />
          </div>
        )}
      </div>
    </div>
  );
}
