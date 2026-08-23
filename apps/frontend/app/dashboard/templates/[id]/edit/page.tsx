"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  templateApi,
  industryApi,
  type TemplateDetail,
  type SectionDetail,
  type FieldRead,
  type FieldCreate,
  type FieldUpdate,
  type IndustryRead,
  ApiError,
} from "@/lib/api-client";

const FIELD_TYPES = [
  { value: "text", label: "Kısa Metin" },
  { value: "textarea", label: "Uzun Metin" },
  { value: "rich_text", label: "Zengin Metin" },
  { value: "select", label: "Tekli Seçim" },
  { value: "multi_select", label: "Çoklu Seçim" },
  { value: "checkbox", label: "Onay Kutusu" },
  { value: "date", label: "Tarih" },
  { value: "url", label: "URL" },
  { value: "number", label: "Sayı" },
  { value: "file", label: "Dosya" },
  { value: "color", label: "Renk" },
  { value: "moodboard", label: "Moodboard" },
  { value: "reference_images", label: "Referans Görseller" },
  { value: "platform_selector", label: "Platform Seçimi" },
  { value: "campaign_goal", label: "Kampanya Hedefi" },
  { value: "target_audience", label: "Hedef Kitle" },
];

const FIELD_TYPE_ICONS: Record<string, string> = {
  text: "T",
  textarea: "¶",
  rich_text: "Ψ",
  select: "▾",
  multi_select: "☰",
  checkbox: "☑",
  date: "◷",
  url: "⊕",
  number: "#",
  file: "⊞",
  color: "◉",
  moodboard: "⊡",
  reference_images: "⊟",
  platform_selector: "◈",
  campaign_goal: "◎",
  target_audience: "◍",
};

const OPTIONS_REQUIRED = new Set(["select", "multi_select"]);

// ── Field editor modal ────────────────────────────────────────────────────────

interface FieldEditorModalProps {
  initial?: FieldRead | null;
  sectionId: string;
  onSave: (data: FieldCreate | FieldUpdate, fieldId?: string) => Promise<void>;
  onClose: () => void;
}

function FieldEditorModal({ initial, sectionId, onSave, onClose }: FieldEditorModalProps) {
  const [fieldKey, setFieldKey] = useState(initial?.field_key ?? "");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [helpText, setHelpText] = useState(initial?.help_text ?? "");
  const [fieldType, setFieldType] = useState(initial?.field_type ?? "text");
  const [isRequired, setIsRequired] = useState(initial?.is_required ?? false);
  const [placeholder, setPlaceholder] = useState(initial?.placeholder ?? "");
  const [optionsText, setOptionsText] = useState(
    initial?.options ? JSON.stringify(initial.options, null, 2) : ""
  );
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const needsOptions = OPTIONS_REQUIRED.has(fieldType);

  const handleSave = async () => {
    setError(null);
    if (!label.trim()) { setError("Etiket zorunludur"); return; }
    if (!initial && !fieldKey.trim()) { setError("Alan anahtarı zorunludur"); return; }
    if (needsOptions && !optionsText.trim()) {
      setError("Bu alan tipi için seçenekler zorunludur (JSON)");
      return;
    }

    let parsedOptions: Record<string, unknown> | null = null;
    if (optionsText.trim()) {
      try {
        parsedOptions = JSON.parse(optionsText) as Record<string, unknown>;
      } catch {
        setError("Seçenekler geçerli bir JSON olmalıdır");
        return;
      }
    }

    setIsSaving(true);
    try {
      if (initial) {
        const data: FieldUpdate = {
          label: label.trim(),
          help_text: helpText.trim() || null,
          field_type: fieldType,
          is_required: isRequired,
          placeholder: placeholder.trim() || null,
          options: parsedOptions,
        };
        await onSave(data, initial.id);
      } else {
        const data: FieldCreate = {
          field_key: fieldKey.trim(),
          label: label.trim(),
          help_text: helpText.trim() || null,
          field_type: fieldType,
          is_required: isRequired,
          placeholder: placeholder.trim() || null,
          options: parsedOptions,
        };
        await onSave(data);
      }
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kaydedilemedi");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-lg shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-text">
            {initial ? "Alanı Düzenle" : "Yeni Alan Ekle"}
          </h2>
          <button
            onClick={onClose}
            aria-label="Modal'ı kapat"
            className="text-text-muted hover:text-text transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
          {!initial && (
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Alan Anahtarı <span className="text-danger">*</span>
              </label>
              <input
                type="text"
                value={fieldKey}
                onChange={(e) => setFieldKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
                placeholder="alan_adi (küçük harf, alt çizgi)"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">
              Etiket <span className="text-danger">*</span>
            </label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Kullanıcıya gösterilecek ad"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Alan Tipi</label>
            <select
              value={fieldType}
              onChange={(e) => setFieldType(e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            >
              {FIELD_TYPES.map((ft) => (
                <option key={ft.value} value={ft.value}>{ft.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Yardım Metni</label>
            <input
              type="text"
              value={helpText}
              onChange={(e) => setHelpText(e.target.value)}
              placeholder="Kullanıcıya ipucu ver (opsiyonel)"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1">Placeholder</label>
            <input
              type="text"
              value={placeholder}
              onChange={(e) => setPlaceholder(e.target.value)}
              placeholder="Giriş alanı placeholder metni"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            />
          </div>

          {needsOptions && (
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Seçenekler (JSON) <span className="text-danger">*</span>
              </label>
              <textarea
                value={optionsText}
                onChange={(e) => setOptionsText(e.target.value)}
                rows={4}
                placeholder={'{"choices": ["Seçenek 1", "Seçenek 2"]}'}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none"
              />
            </div>
          )}

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is-required"
              checked={isRequired}
              onChange={(e) => setIsRequired(e.target.checked)}
              className="w-4 h-4 rounded accent-accent"
            />
            <label htmlFor="is-required" className="text-sm text-text cursor-pointer">
              Zorunlu alan
            </label>
          </div>

          {error && (
            <div className="bg-danger/10 border border-danger/20 rounded-lg px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}
        </div>

        <div className="flex gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-border rounded-lg text-sm font-medium text-text hover:bg-surface-2 transition-colors"
          >
            İptal
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex-1 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors"
          >
            {isSaving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Field preview widget ──────────────────────────────────────────────────────

function FieldPreview({ field }: { field: FieldRead }) {
  const label = (
    <span className="text-sm font-medium text-text">
      {field.label}
      {field.is_required && <span className="text-danger ml-0.5">*</span>}
    </span>
  );

  let input: React.ReactNode;
  if (field.field_type === "textarea" || field.field_type === "rich_text") {
    input = (
      <textarea
        disabled
        placeholder={field.placeholder ?? ""}
        rows={3}
        className="w-full px-3 py-2 bg-surface-2/50 border border-border/50 rounded-lg text-sm text-text-muted resize-none cursor-not-allowed"
      />
    );
  } else if (field.field_type === "select" || field.field_type === "multi_select") {
    const choices = (field.options as { choices?: string[] })?.choices ?? [];
    input = (
      <select disabled className="w-full px-3 py-2 bg-surface-2/50 border border-border/50 rounded-lg text-sm text-text-muted cursor-not-allowed">
        <option>{choices[0] ?? "Seçin…"}</option>
      </select>
    );
  } else if (field.field_type === "checkbox") {
    input = (
      <div className="flex items-center gap-2">
        <input type="checkbox" disabled className="w-4 h-4 cursor-not-allowed" />
        <span className="text-sm text-text-muted">{field.placeholder ?? "Evet"}</span>
      </div>
    );
  } else if (field.field_type === "date") {
    input = (
      <input
        type="date"
        disabled
        className="w-full px-3 py-2 bg-surface-2/50 border border-border/50 rounded-lg text-sm text-text-muted cursor-not-allowed"
      />
    );
  } else if (field.field_type === "color") {
    input = (
      <div className="flex items-center gap-2">
        <input type="color" disabled className="h-8 w-10 cursor-not-allowed" />
        <span className="text-sm text-text-muted">#000000</span>
      </div>
    );
  } else {
    input = (
      <input
        type="text"
        disabled
        placeholder={field.placeholder ?? ""}
        className="w-full px-3 py-2 bg-surface-2/50 border border-border/50 rounded-lg text-sm text-text-muted cursor-not-allowed"
      />
    );
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        {label}
        <span className="text-[10px] text-text-muted bg-surface-2 px-1.5 py-0.5 rounded">
          {FIELD_TYPE_ICONS[field.field_type] ?? "?"} {field.field_type}
        </span>
      </div>
      {field.help_text && (
        <p className="text-xs text-text-muted">{field.help_text}</p>
      )}
      {input}
    </div>
  );
}

// ── Main builder ──────────────────────────────────────────────────────────────

interface BuilderState {
  template: TemplateDetail;
  industries: IndustryRead[];
}

export default function TemplateEditPage() {
  const { id: templateId } = useParams<{ id: string }>();
  const router = useRouter();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();

  const [state, setState] = useState<BuilderState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSavingMeta, setIsSavingMeta] = useState(false);

  // Section add state
  const [addingSectionTitle, setAddingSectionTitle] = useState("");
  const [isAddingSection, setIsAddingSection] = useState(false);

  // Field modal state
  const [fieldModal, setFieldModal] = useState<{
    sectionId: string;
    field?: FieldRead;
  } | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !activeAgency) return;
    setIsLoading(true);
    setError(null);
    try {
      const [template, industries] = await Promise.all([
        templateApi.get(templateId, activeAgency.id, accessToken),
        industryApi.list(),
      ]);
      setState({ template, industries });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Şablon yüklenemedi");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, activeAgency, templateId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSaveMeta = async () => {
    if (!state || !accessToken || !activeAgency) return;
    setIsSavingMeta(true);
    try {
      const updated = await templateApi.update(
        templateId,
        { name: state.template.name, description: state.template.description, industry: state.template.industry },
        activeAgency.id,
        accessToken
      );
      setState((s) => s ? { ...s, template: { ...s.template, ...updated } } : s);
    } catch {
      /* show inline if needed */
    } finally {
      setIsSavingMeta(false);
    }
  };

  const handleAddSection = async () => {
    if (!addingSectionTitle.trim() || !accessToken || !activeAgency) return;
    setIsAddingSection(true);
    try {
      const section = await templateApi.addSection(
        templateId,
        { title: addingSectionTitle.trim(), sort_order: state?.template.sections.length ?? 0 },
        activeAgency.id,
        accessToken
      );
      setState((s) => {
        if (!s) return s;
        return {
          ...s,
          template: {
            ...s.template,
            sections: [...s.template.sections, { ...section, fields: [] }],
          },
        };
      });
      setAddingSectionTitle("");
    } catch {
      /* ignore */
    } finally {
      setIsAddingSection(false);
    }
  };

  const handleDeleteSection = async (sectionId: string) => {
    if (!accessToken || !activeAgency) return;
    await templateApi.deleteSection(templateId, sectionId, activeAgency.id, accessToken);
    setState((s) => {
      if (!s) return s;
      return {
        ...s,
        template: {
          ...s.template,
          sections: s.template.sections.filter((sec) => sec.id !== sectionId),
        },
      };
    });
  };

  const handleSaveField = async (
    data: Parameters<typeof templateApi.addField>[2] | Parameters<typeof templateApi.updateField>[3],
    fieldId?: string
  ) => {
    if (!accessToken || !activeAgency || !fieldModal) return;
    const { sectionId } = fieldModal;
    if (fieldId) {
      const updated = await templateApi.updateField(
        templateId, sectionId, fieldId, data as Parameters<typeof templateApi.updateField>[3],
        activeAgency.id, accessToken
      );
      setState((s) => {
        if (!s) return s;
        return {
          ...s,
          template: {
            ...s.template,
            sections: s.template.sections.map((sec) =>
              sec.id === sectionId
                ? { ...sec, fields: sec.fields.map((f) => (f.id === fieldId ? updated : f)) }
                : sec
            ),
          },
        };
      });
    } else {
      const created = await templateApi.addField(
        templateId, sectionId, data as Parameters<typeof templateApi.addField>[2],
        activeAgency.id, accessToken
      );
      setState((s) => {
        if (!s) return s;
        return {
          ...s,
          template: {
            ...s.template,
            sections: s.template.sections.map((sec) =>
              sec.id === sectionId ? { ...sec, fields: [...sec.fields, created] } : sec
            ),
          },
        };
      });
    }
  };

  const handleDeleteField = async (sectionId: string, fieldId: string) => {
    if (!accessToken || !activeAgency) return;
    await templateApi.deleteField(templateId, sectionId, fieldId, activeAgency.id, accessToken);
    setState((s) => {
      if (!s) return s;
      return {
        ...s,
        template: {
          ...s.template,
          sections: s.template.sections.map((sec) =>
            sec.id === sectionId
              ? { ...sec, fields: sec.fields.filter((f) => f.id !== fieldId) }
              : sec
          ),
        },
      };
    });
  };

  if (isLoading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="h-8 bg-surface-2 rounded w-56 mb-6 animate-pulse" />
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-32 bg-surface animate-pulse rounded-xl border border-border" />
            ))}
          </div>
          <div className="h-96 bg-surface animate-pulse rounded-xl border border-border" />
        </div>
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="bg-danger/10 border border-danger/20 rounded-xl p-4 text-sm text-danger">
          {error ?? "Şablon bulunamadı"}
        </div>
      </div>
    );
  }

  const { template, industries } = state;
  const isSystemTemplate = template.is_system_template;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/dashboard/templates")}
            className="text-text-muted hover:text-text transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-text">{template.name}</h1>
              {isSystemTemplate && (
                <span className="text-[10px] font-medium px-1.5 py-0.5 bg-blue-50 text-blue-600 border border-blue-200 rounded-full">
                  Sistem
                </span>
              )}
            </div>
            <p className="text-xs text-text-muted">Şablon Düzenleyici</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6">
        {/* Left: Builder */}
        <div className="space-y-6">
          {/* Meta card */}
          {!isSystemTemplate && (
            <div className="bg-surface border border-border rounded-xl p-5">
              <h2 className="text-sm font-semibold text-text mb-4">Şablon Bilgileri</h2>
              <div className="space-y-3">
                <input
                  type="text"
                  value={template.name}
                  onChange={(e) => setState((s) => s ? { ...s, template: { ...s.template, name: e.target.value } } : s)}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                />
                <textarea
                  value={template.description ?? ""}
                  onChange={(e) => setState((s) => s ? { ...s, template: { ...s.template, description: e.target.value || null } } : s)}
                  rows={2}
                  placeholder="Açıklama (opsiyonel)"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                />
                <div className="flex items-center gap-3">
                  <select
                    value={template.industry ?? ""}
                    onChange={(e) => setState((s) => s ? { ...s, template: { ...s.template, industry: e.target.value || null } } : s)}
                    className="flex-1 px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                  >
                    <option value="">Sektör seçin</option>
                    {industries.map((ind) => (
                      <option key={ind.code} value={ind.code}>{ind.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={handleSaveMeta}
                    disabled={isSavingMeta}
                    className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors"
                  >
                    {isSavingMeta ? "…" : "Kaydet"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Sections */}
          <div className="space-y-4">
            {template.sections.length === 0 && (
              <div className="text-center py-12 text-text-muted text-sm border-2 border-dashed border-border rounded-xl">
                Henüz bölüm yok. Aşağıdan bir bölüm ekleyin.
              </div>
            )}

            {template.sections.map((section) => (
              <SectionCard
                key={section.id}
                section={section}
                isReadOnly={isSystemTemplate}
                onAddField={() => setFieldModal({ sectionId: section.id })}
                onEditField={(field) => setFieldModal({ sectionId: section.id, field })}
                onDeleteField={(fieldId) => void handleDeleteField(section.id, fieldId)}
                onDeleteSection={() => void handleDeleteSection(section.id)}
              />
            ))}

            {/* Add section */}
            {!isSystemTemplate && (
              <div className="bg-surface border border-dashed border-border rounded-xl p-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={addingSectionTitle}
                    onChange={(e) => setAddingSectionTitle(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") void handleAddSection(); }}
                    placeholder="Yeni bölüm adı…"
                    className="flex-1 px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                  />
                  <button
                    onClick={() => void handleAddSection()}
                    disabled={isAddingSection || !addingSectionTitle.trim()}
                    className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors"
                  >
                    + Bölüm Ekle
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Live Preview */}
        <div className="xl:sticky xl:top-8 xl:self-start">
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-surface-2/50">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                Canlı Önizleme
              </h3>
            </div>
            <div className="p-4 max-h-[calc(100vh-200px)] overflow-y-auto">
              {template.sections.length === 0 ? (
                <p className="text-sm text-text-muted text-center py-8">
                  Bölüm ekledikçe önizleme burada görünür
                </p>
              ) : (
                <div className="space-y-6">
                  {template.sections.map((section) => (
                    <div key={section.id}>
                      <div className="mb-3">
                        <h4 className="text-sm font-semibold text-text">{section.title}</h4>
                        {section.description && (
                          <p className="text-xs text-text-muted mt-0.5">{section.description}</p>
                        )}
                      </div>
                      <div className="space-y-3 pl-3 border-l-2 border-accent/20">
                        {section.fields.length === 0 ? (
                          <p className="text-xs text-text-muted italic">Henüz alan yok</p>
                        ) : (
                          section.fields.map((field) => (
                            <FieldPreview key={field.id} field={field} />
                          ))
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Field modal */}
      {fieldModal && (
        <FieldEditorModal
          initial={fieldModal.field}
          sectionId={fieldModal.sectionId}
          onSave={handleSaveField}
          onClose={() => setFieldModal(null)}
        />
      )}
    </div>
  );
}

// ── Section card ──────────────────────────────────────────────────────────────

function SectionCard({
  section,
  isReadOnly,
  onAddField,
  onEditField,
  onDeleteField,
  onDeleteSection,
}: {
  section: SectionDetail;
  isReadOnly: boolean;
  onAddField: () => void;
  onEditField: (field: FieldRead) => void;
  onDeleteField: (fieldId: string) => void;
  onDeleteSection: () => void;
}) {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-surface-2/50 border-b border-border">
        <div>
          <h3 className="text-sm font-semibold text-text">{section.title}</h3>
          {section.description && (
            <p className="text-xs text-text-muted">{section.description}</p>
          )}
        </div>
        {!isReadOnly && (
          <div className="flex items-center gap-1">
            <button
              onClick={(e) => onAddField()}
              className="text-xs px-2.5 py-1.5 text-accent hover:bg-accent/10 rounded-lg transition-colors font-medium"
            >
              + Alan
            </button>
<button
              onClick={onDeleteSection}
              className="text-xs px-2.5 py-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
              aria-label="Bölümü sil"
            >
              Sil
            </button>
          </div>
        )}
      </div>

      <div className="divide-y divide-border">
        {section.fields.length === 0 ? (
          <div className="px-4 py-4 text-sm text-text-muted text-center">
            Bu bölümde henüz alan yok.
          </div>
        ) : (
          section.fields.map((field) => (
            <div
              key={field.id}
              className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2/50 transition-colors group"
            >
              <span className="w-7 h-7 flex items-center justify-center bg-accent/10 text-accent rounded-lg text-xs font-mono flex-shrink-0">
                {FIELD_TYPE_ICONS[field.field_type] ?? "?"}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-text truncate">{field.label}</span>
                  {field.is_required && (
                    <span className="flex-shrink-0 text-danger text-xs">*</span>
                  )}
                </div>
                <span className="text-xs text-text-muted">{field.field_key} · {field.field_type}</span>
              </div>
              {!isReadOnly && (
<div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => onEditField(field)}
                    className="p-1.5 text-text-muted hover:text-accent hover:bg-accent/10 rounded-lg transition-colors"
                    aria-label="Alan düzenle"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => onDeleteField(field.id)}
                    className="p-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
                    aria-label="Alan sil"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
