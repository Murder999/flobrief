"use client";

import { useCallback, useState } from "react";
import type { SectionDetail, FieldRead, BriefFieldValueRead } from "@/lib/api-client";

interface DynamicBriefFormProps {
  sections: SectionDetail[];
  initialValues: BriefFieldValueRead[];
  onSave: (values: { template_field_id: string; value: unknown }[]) => Promise<void>;
  readOnly?: boolean;
}

function getInitialValueMap(values: BriefFieldValueRead[]): Record<string, unknown> {
  const map: Record<string, unknown> = {};
  for (const v of values) {
    map[v.template_field_id] = v.value;
  }
  return map;
}

interface FieldInputProps {
  field: FieldRead;
  value: unknown;
  onChange: (fieldId: string, value: unknown) => void;
  readOnly: boolean;
}

function FieldInput({ field, value, onChange, readOnly }: FieldInputProps) {
  const strVal = typeof value === "string" ? value : "";
  const numVal = typeof value === "number" ? value : "";
  const choices = (field.options as { choices?: string[] } | null)?.choices ?? [];

  const base =
    "w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors disabled:opacity-60 disabled:cursor-not-allowed";

  switch (field.field_type) {
    case "textarea":
    case "rich_text":
      return (
        <textarea
          className={`${base} resize-y min-h-[100px]`}
          placeholder={field.placeholder ?? ""}
          value={strVal}
          disabled={readOnly}
          onChange={(e) => onChange(field.id, e.target.value)}
          rows={4}
        />
      );

    case "select":
      return (
        <select
          className={base}
          value={strVal}
          disabled={readOnly}
          onChange={(e) => onChange(field.id, e.target.value)}
        >
          <option value="">Seçiniz…</option>
          {choices.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      );

    case "multi_select":
      return (
        <div className="flex flex-wrap gap-2">
          {choices.map((c) => {
            const selected = Array.isArray(value) ? (value as string[]).includes(c) : false;
            return (
              <button
                key={c}
                type="button"
                disabled={readOnly}
                onClick={() => {
                  const current = Array.isArray(value) ? (value as string[]) : [];
                  const next = selected ? current.filter((x) => x !== c) : [...current, c];
                  onChange(field.id, next);
                }}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  selected
                    ? "bg-accent text-white border-accent"
                    : "bg-surface border-border text-text-muted hover:border-accent hover:text-accent"
                } disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {c}
              </button>
            );
          })}
        </div>
      );

    case "checkbox":
      return (
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            className="w-4 h-4 accent-accent"
            checked={value === true}
            disabled={readOnly}
            onChange={(e) => onChange(field.id, e.target.checked)}
          />
          <span className="text-sm text-text">Evet</span>
        </label>
      );

    case "date":
      return (
        <input
          type="date"
          className={base}
          value={strVal}
          disabled={readOnly}
          onChange={(e) => onChange(field.id, e.target.value)}
        />
      );

    case "url":
      return (
        <input
          type="url"
          className={base}
          placeholder={field.placeholder ?? "https://"}
          value={strVal}
          disabled={readOnly}
          onChange={(e) => onChange(field.id, e.target.value)}
        />
      );

    case "number":
      return (
        <input
          type="number"
          className={base}
          placeholder={field.placeholder ?? ""}
          value={numVal}
          disabled={readOnly}
          onChange={(e) => onChange(field.id, e.target.valueAsNumber || e.target.value)}
        />
      );

    case "color":
      return (
        <div className="flex items-center gap-3">
          <input
            type="color"
            className="h-10 w-16 rounded cursor-pointer disabled:cursor-not-allowed"
            value={strVal || "#000000"}
            disabled={readOnly}
            onChange={(e) => onChange(field.id, e.target.value)}
          />
          <input
            type="text"
            className={`${base} flex-1`}
            placeholder="#000000"
            value={strVal}
            disabled={readOnly}
            onChange={(e) => onChange(field.id, e.target.value)}
          />
        </div>
      );

    case "platform_selector": {
      const platforms = [
        { id: "instagram", label: "Instagram" },
        { id: "tiktok", label: "TikTok" },
        { id: "youtube", label: "YouTube" },
        { id: "facebook", label: "Facebook" },
        { id: "twitter", label: "X / Twitter" },
        { id: "linkedin", label: "LinkedIn" },
        { id: "google_ads", label: "Google Ads" },
        { id: "web", label: "Web Sitesi" },
      ];
      return (
        <div className="flex flex-wrap gap-2">
          {platforms.map((p) => {
            const selected = Array.isArray(value)
              ? (value as string[]).includes(p.id)
              : false;
            return (
              <button
                key={p.id}
                type="button"
                disabled={readOnly}
                onClick={() => {
                  const current = Array.isArray(value) ? (value as string[]) : [];
                  const next = selected ? current.filter((x) => x !== p.id) : [...current, p.id];
                  onChange(field.id, next);
                }}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  selected
                    ? "bg-accent text-white border-accent"
                    : "bg-surface border-border text-text-muted hover:border-accent hover:text-accent"
                } disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      );
    }

    case "campaign_goal": {
      const goals = [
        "Marka Bilinirliği",
        "Satış / Dönüşüm",
        "Lead Toplama",
        "Uygulama İndirme",
        "Topluluk Büyütme",
        "Ürün Lansmanı",
      ];
      return (
        <div className="flex flex-wrap gap-2">
          {goals.map((g) => {
            const selected = strVal === g;
            return (
              <button
                key={g}
                type="button"
                disabled={readOnly}
                onClick={() => onChange(field.id, selected ? "" : g)}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  selected
                    ? "bg-accent text-white border-accent"
                    : "bg-surface border-border text-text-muted hover:border-accent hover:text-accent"
                } disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {g}
              </button>
            );
          })}
        </div>
      );
    }

    case "target_audience":
      return (
        <textarea
          className={`${base} min-h-[80px]`}
          placeholder={
            field.placeholder ?? "Yaş, cinsiyet, ilgi alanları, gelir düzeyi…"
          }
          value={strVal}
          disabled={readOnly}
          onChange={(e) => onChange(field.id, e.target.value)}
          rows={3}
        />
      );

    case "moodboard":
    case "reference_images":
      return (
        <div className="rounded-lg border-2 border-dashed border-border p-6 text-center text-sm text-text-muted">
          <div className="text-2xl mb-2">🖼</div>
          <p className="font-medium">Görsel yükle</p>
          <p className="text-xs mt-1 opacity-60">PNG, JPG, WEBP • Maks. 10MB</p>
          <p className="text-xs mt-2 italic opacity-50">
            (Dosya yükleme Part 7&apos;de aktifleşecek)
          </p>
        </div>
      );

    default:
      return (
        <input
          type="text"
          className={base}
          placeholder={field.placeholder ?? ""}
          value={strVal}
          disabled={readOnly}
          onChange={(e) => onChange(field.id, e.target.value)}
        />
      );
  }
}

export function DynamicBriefForm({
  sections,
  initialValues,
  onSave,
  readOnly = false,
}: DynamicBriefFormProps) {
  const [values, setValues] = useState<Record<string, unknown>>(
    getInitialValueMap(initialValues)
  );
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  const handleChange = useCallback((fieldId: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [fieldId]: value }));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = Object.entries(values).map(([template_field_id, value]) => ({
        template_field_id,
        value,
      }));
      await onSave(payload);
      setSavedAt(new Date());
    } finally {
      setSaving(false);
    }
  };

  if (sections.length === 0) {
    return (
      <div className="text-center py-12 text-text-muted text-sm">
        Bu şablona henüz alan eklenmemiş.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {sections.map((section) => (
        <div key={section.id} className="bg-surface rounded-xl border border-border overflow-hidden">
          <div className="px-6 py-4 border-b border-border bg-surface-2/40">
            <h3 className="font-semibold text-text text-sm">{section.title}</h3>
            {section.description && (
              <p className="text-xs text-text-muted mt-0.5">{section.description}</p>
            )}
          </div>
          <div className="p-6 space-y-5">
            {section.fields.map((field) => (
              <div key={field.id}>
                <label className="block text-sm font-medium text-text mb-1.5">
                  {field.label}
                  {field.is_required && (
                    <span className="text-red-500 ml-1">*</span>
                  )}
                </label>
                {field.help_text && (
                  <p className="text-xs text-text-muted mb-2">{field.help_text}</p>
                )}
                <FieldInput
                  field={field}
                  value={values[field.id]}
                  onChange={handleChange}
                  readOnly={readOnly}
                />
              </div>
            ))}
          </div>
        </div>
      ))}

      {!readOnly && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-text-muted">
            {savedAt
              ? `Son kayıt: ${savedAt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}`
              : "Kaydedilmedi"}
          </span>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {saving ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Kaydediliyor…
              </>
            ) : (
              "Kaydet"
            )}
          </button>
        </div>
      )}
    </div>
  );
}
