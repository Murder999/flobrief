"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, ApiError, type BrandBriefCreate, type AssetRead } from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";
import { Stepper, type StepperStep } from "@/components/ui/stepper";
import { Tabs } from "@/components/ui/tabs";
import { FileDropzone } from "@/components/brief-form/FileDropzone";
import RichTextEditor from "@/components/forms/RichTextEditor";
import {
  ArrowLeft, Send, Save, CheckCircle2, AlertCircle, Loader2,
  FileText, Target, Monitor, Calendar, StickyNote, ChevronDown, ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Constants ─────────────────────────────────────────────────────────────────

const PLATFORMS = [
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "youtube", label: "YouTube" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "x", label: "X" },
  { value: "web", label: "Web" },
  { value: "email", label: "E-posta" },
  { value: "print", label: "Basılı" },
  { value: "other", label: "Diğer" },
];

const CONTENT_TYPES = [
  { value: "post", label: "Post" },
  { value: "story", label: "Story" },
  { value: "reels", label: "Reels / Kısa Video" },
  { value: "carousel", label: "Carousel" },
  { value: "video", label: "Video" },
  { value: "banner", label: "Banner" },
  { value: "blog", label: "Blog" },
  { value: "landing_page", label: "Landing Page" },
  { value: "email", label: "E-posta" },
  { value: "presentation", label: "Sunum" },
  { value: "print", label: "Basılı Materyal" },
  { value: "other", label: "Diğer" },
];

const PRIORITY_OPTIONS = [
  { value: "low", label: "Düşük", desc: "Zaman baskısı yok" },
  { value: "normal", label: "Normal", desc: "Standart iş akışı" },
  { value: "high", label: "Yüksek", desc: "Öncelikli ele alınır" },
  { value: "urgent", label: "Acil", desc: "En kısa sürede" },
];

const DATE_FIELDS: { key: keyof BrandBriefCreate; label: string }[] = [
  { key: "start_date", label: "Başlangıç Tarihi" },
  { key: "draft_date", label: "İlk Taslak Tarihi" },
  { key: "feedback_date", label: "Geri Bildirim Tarihi" },
  { key: "deadline", label: "Nihai Teslim Tarihi" },
  { key: "publish_date", label: "Yayın Tarihi" },
];

const STEPS: StepperStep[] = [
  { key: "basics", label: "Brief Temeli" },
  { key: "platform", label: "Platform & İçerik" },
  { key: "details", label: "Hedef & Detaylar" },
  { key: "planning", label: "Öncelik & Tarihler" },
  { key: "references", label: "Referanslar & Notlar" },
];

const INITIAL: BrandBriefCreate = {
  title: "",
  description: "",
  description_html: "",
  campaign_goal: "",
  target_audience: "",
  platforms: [],
  content_types: [],
  priority: "normal",
  start_date: "",
  draft_date: "",
  feedback_date: "",
  deadline: "",
  publish_date: "",
  cta: "",
  key_message: "",
  mandatory_messages: "",
  things_to_avoid: "",
  success_criteria: "",
  technical_requirements: "",
  brand_tone: "",
  reference_links: [],
  additional_notes: "",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionCard({
  id,
  icon: Icon,
  title,
  children,
}: {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div id={id} className="bg-surface border border-border rounded-xl overflow-hidden scroll-mt-20">
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-border bg-surface-2/50">
        <Icon className="w-4 h-4 text-accent" />
        <h2 className="text-sm font-semibold text-text">{title}</h2>
      </div>
      <div className="p-5 space-y-4">{children}</div>
    </div>
  );
}

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs font-medium text-text-muted mb-1.5">
      {children}
      {required && <span className="text-danger ml-0.5">*</span>}
    </label>
  );
}

function TextField({
  value, onChange, placeholder, type = "text", error, className,
}: {
  value: string; onChange: (v: string) => void; placeholder?: string; type?: string;
  error?: string; className?: string;
}) {
  return (
    <div>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          "w-full h-9 px-3 bg-surface border rounded-lg text-sm text-text",
          "placeholder:text-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/15 transition-all",
          error ? "border-danger/50 focus:ring-danger/15" : "border-border focus:border-accent/60",
          className,
        )}
      />
      {error && <p className="text-xs text-danger mt-1">{error}</p>}
    </div>
  );
}

function Textarea({
  value, onChange, placeholder, rows = 3,
}: {
  value: string; onChange: (v: string) => void; placeholder?: string; rows?: number;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full px-3 py-2.5 bg-surface border border-border rounded-lg text-sm text-text placeholder:text-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/15 focus:border-accent/60 transition-all resize-none"
    />
  );
}

function MultiSelectPills({
  options, selected, onToggle,
}: {
  options: { value: string; label: string }[]; selected: string[]; onToggle: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const isSelected = selected.includes(opt.value);
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onToggle(opt.value)}
            aria-pressed={isSelected}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium border transition-all",
              isSelected
                ? "bg-accent/15 border-accent/40 text-accent"
                : "bg-surface border-border text-text-muted hover:text-text hover:border-accent/20",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// ── Success state ─────────────────────────────────────────────────────────────

function SuccessScreen({ title, onNew }: { title: string; onNew: () => void }) {
  const router = useRouter();
  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="flex flex-col items-center py-16 text-center">
        <div className="w-16 h-16 bg-emerald-500/10 rounded-2xl flex items-center justify-center mb-5 ring-1 ring-emerald-500/20">
          <CheckCircle2 className="w-8 h-8 text-emerald-400" />
        </div>
        <h2 className="text-xl font-semibold text-text mb-2">Brief talebiniz ajansınıza iletildi</h2>
        <p className="text-sm text-text-muted max-w-sm mb-1">
          <span className="font-medium text-text">&ldquo;{title}&rdquo;</span> talebi ajansınızın incelemesine gönderildi.
        </p>
        <p className="text-sm text-text-muted mb-8">Ajansınız talebi inceleyip sizinle iletişime geçecektir.</p>
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/brand/briefs")}
            className="px-4 py-2 bg-surface border border-border rounded-lg text-sm text-text hover:border-accent/30 transition-colors"
          >
            Brieflerime Dön
          </button>
          <button
            onClick={onNew}
            className="px-4 py-2 bg-gradient-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Yeni Talep Oluştur
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Summary panel ─────────────────────────────────────────────────────────────

function SummaryPanel({ form, fileCount }: { form: BrandBriefCreate; fileCount: number }) {
  const filledDates = DATE_FIELDS.filter((d) => form[d.key]);
  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Brief Özeti</h3>
      <div>
        <p className="text-sm font-semibold text-text truncate">{form.title || "Başlıksız Brief"}</p>
        {form.campaign_goal && <p className="text-xs text-text-muted mt-1 line-clamp-2">{form.campaign_goal}</p>}
      </div>

      {(form.platforms?.length || form.content_types?.length) ? (
        <div className="space-y-2">
          {!!form.platforms?.length && (
            <div className="flex flex-wrap gap-1">
              {form.platforms.map((p) => (
                <span key={p} className="px-1.5 py-0.5 rounded bg-surface-2 text-[10px] text-text-muted">{p}</span>
              ))}
            </div>
          )}
          {!!form.content_types?.length && (
            <div className="flex flex-wrap gap-1">
              {form.content_types.map((c) => (
                <span key={c} className="px-1.5 py-0.5 rounded bg-accent-subtle text-[10px] text-accent">{c}</span>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-text-muted/70">Platform veya içerik tipi seçilmedi</p>
      )}

      <div className="pt-3 border-t border-border space-y-1.5">
        <p className="text-xs text-text-muted">Öncelik: <span className="text-text font-medium">{form.priority}</span></p>
        {filledDates.length > 0 ? (
          filledDates.map((d) => (
            <p key={d.key} className="text-xs text-text-muted">
              {d.label}: <span className="text-text font-medium">{String(form[d.key])}</span>
            </p>
          ))
        ) : (
          <p className="text-xs text-text-muted/70">Tarih planlanmadı</p>
        )}
      </div>

      <div className="pt-3 border-t border-border">
        <p className="text-xs text-text-muted">{fileCount} dosya eklendi</p>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function NewBrandBriefPage() {
  const { accessToken } = useAuth();
  const router = useRouter();
  const { confirm } = useToast();

  const [form, setForm] = useState<BrandBriefCreate>({ ...INITIAL });
  const [refLinkInput, setRefLinkInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dateError, setDateError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ title: string } | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [refTab, setRefTab] = useState<"references" | "notes">("references");
  const [files, setFiles] = useState<AssetRead[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const savingRef = useRef(false);

  const set = (key: keyof BrandBriefCreate, value: unknown) => {
    setForm((f) => ({ ...f, [key]: value }));
    setIsDirty(true);
  };

  const togglePlatform = (p: string) => {
    const current = form.platforms ?? [];
    set("platforms", current.includes(p) ? current.filter((x) => x !== p) : [...current, p]);
  };

  const toggleContentType = (c: string) => {
    const current = form.content_types ?? [];
    set("content_types", current.includes(c) ? current.filter((x) => x !== c) : [...current, c]);
  };

  const addRefLink = () => {
    const link = refLinkInput.trim();
    if (!link) return;
    set("reference_links", [...(form.reference_links ?? []), link]);
    setRefLinkInput("");
  };

  const removeRefLink = (idx: number) => {
    set("reference_links", (form.reference_links ?? []).filter((_, i) => i !== idx));
  };

  // Warn on browser close/refresh with unsaved changes
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty && !success) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty, success]);

  // Scroll-spy for the stepper
  useEffect(() => {
    const sections = STEPS.map((s) => document.getElementById(s.key)).filter(Boolean) as HTMLElement[];
    if (sections.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) {
          const idx = sections.findIndex((s) => s.id === visible[0].target.id);
          if (idx >= 0) setActiveStep(idx);
        }
      },
      { rootMargin: "-15% 0px -70% 0px" }
    );
    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  const scrollToStep = (index: number) => {
    document.getElementById(STEPS[index].key)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const validateDateOrder = useCallback((): boolean => {
    const order = DATE_FIELDS.map((d) => ({ ...d, value: form[d.key] as string | undefined }))
      .filter((d) => d.value);
    for (let i = 0; i < order.length - 1; i++) {
      if (order[i].value! > order[i + 1].value!) {
        setDateError(`${order[i].label}, ${order[i + 1].label} tarihinden sonra olamaz.`);
        return false;
      }
    }
    setDateError(null);
    return true;
  }, [form]);

  const saveData = useCallback((): BrandBriefCreate => ({
    ...form,
    title: form.title.trim(),
    description: null,
    description_html: form.description_html || null,
    campaign_goal: form.campaign_goal?.trim() || null,
    target_audience: form.target_audience?.trim() || null,
    cta: form.cta?.trim() || null,
    key_message: form.key_message?.trim() || null,
    mandatory_messages: form.mandatory_messages?.trim() || null,
    things_to_avoid: form.things_to_avoid?.trim() || null,
    success_criteria: form.success_criteria?.trim() || null,
    technical_requirements: form.technical_requirements?.trim() || null,
    brand_tone: form.brand_tone?.trim() || null,
    start_date: form.start_date || null,
    draft_date: form.draft_date || null,
    feedback_date: form.feedback_date || null,
    deadline: form.deadline || null,
    publish_date: form.publish_date || null,
    additional_notes: form.additional_notes?.trim() || null,
  }), [form]);

  /** Ensures a draft exists on the server, saving one if needed. Used by the
   * file dropzone since attachments require a brief_id to link to. */
  const ensureBriefId = useCallback(async (): Promise<string | null> => {
    if (savedId) return savedId;
    if (!accessToken) return null;
    const title = form.title.trim();
    if (!title) {
      setError("Dosya eklemeden önce brief başlığı girin.");
      return null;
    }
    try {
      const res = await brandPortalApi.createBrief(saveData(), accessToken);
      setSavedId(res.id);
      return res.id;
    } catch {
      return null;
    }
  }, [savedId, accessToken, form, saveData]);

  const handleSaveDraft = async () => {
    if (!accessToken || savingRef.current) return;
    const title = form.title.trim();
    if (!title) { setError("Brief başlığı zorunludur."); return; }
    if (!validateDateOrder()) return;
    setError(null);
    savingRef.current = true;
    setSaving(true);
    try {
      const data = saveData();
      if (savedId) {
        await brandPortalApi.updateBrief(savedId, data, accessToken);
      } else {
        const res = await brandPortalApi.createBrief(data, accessToken);
        setSavedId(res.id);
      }
      setIsDirty(false);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : "Taslak kaydedilemedi.");
    } finally {
      setSaving(false);
      savingRef.current = false;
    }
  };

  const handleSubmit = async () => {
    if (!accessToken || savingRef.current) return;
    const title = form.title.trim();
    if (!title) { setError("Brief başlığı zorunludur."); return; }
    if (!validateDateOrder()) return;
    setError(null);
    savingRef.current = true;
    setSubmitting(true);
    try {
      const data = saveData();
      let id = savedId;
      if (id) {
        await brandPortalApi.updateBrief(id, data, accessToken);
      } else {
        const created = await brandPortalApi.createBrief(data, accessToken);
        id = created.id;
      }
      await brandPortalApi.submitBrief(id!, accessToken);
      setIsDirty(false);
      setSuccess({ title });
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : "Talep gönderilemedi.");
    } finally {
      setSubmitting(false);
      savingRef.current = false;
    }
  };

  const handleNew = () => {
    setForm({ ...INITIAL });
    setSavedId(null);
    setSuccess(null);
    setError(null);
    setDateError(null);
    setRefLinkInput("");
    setFiles([]);
    setIsDirty(false);
  };

  const handleCancelClick = async (e: React.MouseEvent) => {
    if (!isDirty) return;
    e.preventDefault();
    const ok = await confirm({
      title: "Kaydedilmemiş değişiklikler var",
      message: "Bu sayfadan ayrılırsanız kaydedilmemiş değişiklikler kaybolacak. Devam edilsin mi?",
      confirmLabel: "Sayfadan Ayrıl",
      destructive: true,
    });
    if (ok) router.push("/brand/briefs");
  };

  if (success) {
    return <SuccessScreen title={success.title} onNew={handleNew} />;
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-5">
        <Link
          href="/brand/briefs"
          onClick={handleCancelClick}
          className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text transition-colors mb-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Brieflerime dön
        </Link>
        <h1 className="text-xl font-semibold text-text tracking-tight">Yeni Brief Talebi</h1>
        <p className="text-sm text-text-muted mt-0.5">
          Ajansınıza iletmek istediğiniz yeni iş, kampanya veya içerik talebini oluşturun.
        </p>
      </div>

      {/* Stepper */}
      <div className="sticky top-0 z-10 -mx-8 px-8 py-3 mb-5 bg-background/95 backdrop-blur-sm border-b border-border">
        <Stepper steps={STEPS} activeIndex={activeStep} onStepClick={scrollToStep} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-danger/8 border border-danger/20 mb-5 text-sm text-danger">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-danger/60 hover:text-danger">×</button>
        </div>
      )}

      {/* Mobile summary toggle */}
      <button
        type="button"
        onClick={() => setSummaryOpen((v) => !v)}
        className="lg:hidden w-full flex items-center justify-between px-4 py-2.5 mb-4 bg-surface border border-border rounded-lg text-sm text-text"
      >
        Brief Özeti
        {summaryOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {summaryOpen && (
        <div className="lg:hidden mb-4">
          <SummaryPanel form={form} fileCount={files.length} />
        </div>
      )}

      <div className="grid lg:grid-cols-[1fr_280px] gap-5 items-start">
        <div className="space-y-4 min-w-0">
          {/* Section 1: Basics */}
          <SectionCard id="basics" icon={FileText} title="Brief Temeli">
            <div>
              <Label required>Brief Başlığı</Label>
              <TextField
                value={form.title}
                onChange={(v) => set("title", v)}
                placeholder="örn. Yaz Koleksiyonu Instagram Kampanyası"
              />
            </div>
            <div>
              <Label>Açıklama</Label>
              <RichTextEditor
                value={form.description_html ?? ""}
                onChange={(html) => set("description_html", html)}
                placeholder="Bu brief'in amacını ve kapsamını açıklayın..."
                minHeight={140}
              />
            </div>
            <div>
              <Label>Kampanya Amacı</Label>
              <TextField
                value={form.campaign_goal ?? ""}
                onChange={(v) => set("campaign_goal", v)}
                placeholder="örn. Marka bilinirliğini artırmak, yeni ürünü tanıtmak..."
              />
            </div>
          </SectionCard>

          {/* Section 2: Platform & Content Type */}
          <SectionCard id="platform" icon={Monitor} title="Platform ve İçerik Tipleri">
            <div>
              <Label>Platformlar (çoklu seçim)</Label>
              <MultiSelectPills options={PLATFORMS} selected={form.platforms ?? []} onToggle={togglePlatform} />
            </div>
            <div>
              <Label>İçerik Tipleri (çoklu seçim)</Label>
              <MultiSelectPills options={CONTENT_TYPES} selected={form.content_types ?? []} onToggle={toggleContentType} />
            </div>
          </SectionCard>

          {/* Section 3: Target & Details */}
          <SectionCard id="details" icon={Target} title="Hedef ve Detaylar">
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <Label>Hedef Kitle</Label>
                <TextField
                  value={form.target_audience ?? ""}
                  onChange={(v) => set("target_audience", v)}
                  placeholder="örn. 25-40 yaş arası kadınlar"
                />
              </div>
              <div>
                <Label>İstenen Aksiyon (CTA)</Label>
                <TextField
                  value={form.cta ?? ""}
                  onChange={(v) => set("cta", v)}
                  placeholder="örn. Hemen sipariş ver"
                />
              </div>
            </div>
            <div>
              <Label>Ana Mesaj</Label>
              <Textarea
                value={form.key_message ?? ""}
                onChange={(v) => set("key_message", v)}
                placeholder="İletilmesi gereken temel mesaj..."
                rows={2}
              />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <Label>Zorunlu Mesajlar</Label>
                <Textarea
                  value={form.mandatory_messages ?? ""}
                  onChange={(v) => set("mandatory_messages", v)}
                  placeholder="Mutlaka yer alması gereken ifadeler..."
                  rows={2}
                />
              </div>
              <div>
                <Label>Kaçınılması Gerekenler</Label>
                <Textarea
                  value={form.things_to_avoid ?? ""}
                  onChange={(v) => set("things_to_avoid", v)}
                  placeholder="Kullanılmaması gereken ifadeler, görseller..."
                  rows={2}
                />
              </div>
            </div>
            <div>
              <Label>Ton ve İletişim Dili</Label>
              <TextField
                value={form.brand_tone ?? ""}
                onChange={(v) => set("brand_tone", v)}
                placeholder="örn. samimi ve enerjik, kurumsal ve güven veren"
              />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <Label>Başarı Kriterleri</Label>
                <Textarea
                  value={form.success_criteria ?? ""}
                  onChange={(v) => set("success_criteria", v)}
                  placeholder="Bu içerik neyi başarırsa başarılı sayılır?"
                  rows={2}
                />
              </div>
              <div>
                <Label>Teknik Gereksinimler</Label>
                <Textarea
                  value={form.technical_requirements ?? ""}
                  onChange={(v) => set("technical_requirements", v)}
                  placeholder="Boyut, format, süre gibi teknik kısıtlar..."
                  rows={2}
                />
              </div>
            </div>
          </SectionCard>

          {/* Section 4: Priority & Dates */}
          <SectionCard id="planning" icon={Calendar} title="Öncelik ve Tarihler">
            <div>
              <Label>Öncelik</Label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {PRIORITY_OPTIONS.map((opt) => {
                  const selected = form.priority === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => set("priority", opt.value)}
                      className={cn(
                        "px-3 py-2.5 rounded-lg border text-left transition-all",
                        selected
                          ? "bg-accent/15 border-accent/40 text-accent"
                          : "bg-surface border-border text-text-muted hover:border-accent/20 hover:text-text",
                      )}
                    >
                      <p className="text-xs font-semibold">{opt.label}</p>
                      <p className="text-[11px] opacity-70 mt-0.5">{opt.desc}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              {DATE_FIELDS.map((d) => (
                <div key={d.key}>
                  <Label>{d.label}</Label>
                  <TextField
                    type="date"
                    value={(form[d.key] as string) ?? ""}
                    onChange={(v) => { set(d.key, v); }}
                  />
                </div>
              ))}
            </div>
            {dateError && (
              <p className="text-xs text-danger flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                {dateError}
              </p>
            )}
          </SectionCard>

          {/* Section 5: References & Notes */}
          <SectionCard id="references" icon={StickyNote} title="Referanslar ve Ek Notlar">
            <Tabs
              items={[
                { value: "references", label: "Referanslar" },
                { value: "notes", label: "Ek Notlar" },
              ]}
              value={refTab}
              onChange={(v) => setRefTab(v as "references" | "notes")}
            />

            {refTab === "references" ? (
              <div className="space-y-4 pt-1">
                <div>
                  <Label>Dosyalar</Label>
                  <FileDropzone
                    accessToken={accessToken}
                    ensureBriefId={ensureBriefId}
                    files={files}
                    onFilesChange={setFiles}
                    onUploadingChange={setIsUploading}
                  />
                </div>
                <div>
                  <Label>Referans Linkler / Moodboard URL</Label>
                  <div className="flex gap-2">
                    <input
                      type="url"
                      value={refLinkInput}
                      onChange={(e) => setRefLinkInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRefLink())}
                      placeholder="https://..."
                      className="flex-1 h-9 px-3 bg-surface border border-border rounded-lg text-sm text-text placeholder:text-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/15 focus:border-accent/60 transition-all"
                    />
                    <button
                      type="button"
                      onClick={addRefLink}
                      className="px-3 h-9 bg-surface border border-border rounded-lg text-xs text-text-muted hover:text-text hover:border-accent/30 transition-colors"
                    >
                      Ekle
                    </button>
                  </div>
                  {(form.reference_links ?? []).length > 0 && (
                    <div className="mt-2 space-y-1.5">
                      {(form.reference_links ?? []).map((link, idx) => (
                        <div key={idx} className="flex items-center gap-2 px-3 py-1.5 bg-surface-2 rounded-lg">
                          <span className="text-xs text-text-muted truncate flex-1">{link}</span>
                          <button
                            type="button"
                            onClick={() => removeRefLink(idx)}
                            className="text-text-muted/50 hover:text-danger transition-colors text-xs"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="pt-1">
                <Textarea
                  value={form.additional_notes ?? ""}
                  onChange={(v) => set("additional_notes", v)}
                  placeholder="Ajansınıza iletmek istediğiniz ek bilgiler..."
                  rows={5}
                />
              </div>
            )}
          </SectionCard>
        </div>

        {/* Sticky summary — desktop only */}
        <div className="hidden lg:block sticky top-20">
          <SummaryPanel form={form} fileCount={files.length} />
        </div>
      </div>

      {/* Action bar */}
      <div className="mt-6 flex items-center justify-between gap-3 pt-5 border-t border-border">
        <Link
          href="/brand/briefs"
          onClick={handleCancelClick}
          className="px-4 py-2 text-sm text-text-muted hover:text-text transition-colors"
        >
          İptal
        </Link>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSaveDraft}
            disabled={saving || submitting || isUploading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-surface border border-border rounded-lg text-sm text-text-muted hover:text-text hover:border-accent/30 transition-all disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Taslak Kaydet
          </button>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || submitting || isUploading || !form.title.trim()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 shadow-sm"
          >
            {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            Ajansa Gönder
          </button>
        </div>
      </div>
    </div>
  );
}
