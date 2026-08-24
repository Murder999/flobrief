"use client";

import { useEffect, useState, useCallback, useRef, useContext, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useLocale } from "@/context/locale-context";
import { InfoTooltip } from "@/components/contextual-help/InfoTooltip";
import { useToast } from "@/components/ui/toast";
import { BriefPriority, BrandRead, AgencyMemberRead, BrandMemberRead, TemplateRead } from "@/lib/api-client";
import { agencyApi, briefApi, templateApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type Step = "template" | "details" | "people" | "review";

const STEPS: { id: Step; label: string }[] = [
  { id: "template", label: "Şablon" },
  { id: "details", label: "İçerik" },
  { id: "people", label: "Ekip & Medya" },
  { id: "review", label: "Oluştur" },
];

const INDUSTRY_LABEL: Record<string, string> = {
  branding: "Marka & Kimlik",
  content: "İçerik",
  digital_ad: "Dijital Reklam",
  social_media: "Sosyal Medya",
  web: "Web",
  influencer: "Influencer",
  pr: "PR",
  event: "Etkinlik",
};

const PRIORITY_OPTIONS: { value: BriefPriority; label: string; color: string }[] = [
  { value: "low",    label: "Düşük",  color: "status-neutral" },
  { value: "normal", label: "Normal", color: "status-info" },
  { value: "high",   label: "Yüksek", color: "status-warning" },
  { value: "urgent", label: "Acil",   color: "status-danger" },
];

const PLATFORM_OPTIONS = [
  "Instagram", "TikTok", "YouTube", "Twitter/X", "LinkedIn",
  "Facebook", "Pinterest", "Snapchat", "Twitch", "Podcast",
  "Blog", "E-posta", "SMS", "Web Sitesi", "OOH",
];

const CONTENT_TYPE_OPTIONS = [
  "Fotoğraf", "Video", "Reels / Short", "Story", "Carousel",
  "Infografik", "Animasyon", "Metin / Yazı", "Podcast Bölümü",
  "Haber Bülteni", "Banner Reklam", "Case Study", "Sunum",
];

function StepIndicator({ current, onNavigate }: { current: Step; onNavigate: (s: Step) => void }) {
  const currentIdx = STEPS.findIndex((s) => s.id === current);
  return (
    <div className="flex items-center gap-0 mb-8">
      {STEPS.map((step, idx) => {
        const done = idx < currentIdx;
        const active = idx === currentIdx;
        return (
          <div key={step.id} className="flex items-center">
            <button
              type="button"
              onClick={() => done && onNavigate(step.id)}
              className={`flex items-center gap-2 px-1 transition-opacity ${
                active ? "opacity-100" : done ? "opacity-100 cursor-pointer" : "opacity-35 cursor-default"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  done
                    ? "bg-success text-white"
                    : active
                    ? "bg-accent text-white"
                    : "bg-surface-2 text-text-muted"
                }`}
              >
                {done ? (
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  idx + 1
                )}
              </div>
              <span className={`text-sm font-medium hidden sm:block ${active ? "text-text" : "text-text-muted"}`}>
                {step.label}
              </span>
            </button>
            {idx < STEPS.length - 1 && (
              <div className={`h-px w-6 mx-2 transition-colors ${idx < currentIdx ? "bg-success" : "bg-border"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function MultiSelectChips({
  options,
  selected,
  onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const toggle = (opt: string) => {
    onChange(selected.includes(opt) ? selected.filter((x) => x !== opt) : [...selected, opt]);
  };
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = selected.includes(opt);
        return (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
              active
                ? "bg-accent text-white border-accent shadow-sm"
                : "bg-surface-2 text-text-muted border-border hover:border-accent/40 hover:text-text"
            }`}
          >
            {active && <span className="mr-1">✓</span>}
            {opt}
          </button>
        );
      })}
    </div>
  );
}

interface AssigneeCandidate {
  user_id: string;
  full_name: string;
  email: string;
  source: "agency" | "brand";
  role: string;
}

function AssigneePicker({
  candidates,
  selected,
  onChange,
}: {
  candidates: AssigneeCandidate[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  };
  if (!candidates.length) {
    return <p className="text-xs text-text-muted">Henüz ekip üyesi yok.</p>;
  }
  return (
    <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
      {candidates.map((c) => {
        const active = selected.includes(c.user_id);
        return (
          <button
            key={c.user_id}
            type="button"
            onClick={() => toggle(c.user_id)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg border transition-all text-left ${
              active ? "border-accent/50 bg-accent/5" : "border-border bg-surface hover:border-border-hover"
            }`}
          >
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
              active ? "bg-accent text-white" : "bg-surface-2 text-text-muted"
            }`}>
              {active ? (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                (c.full_name || c.email)[0]?.toUpperCase() ?? "?"
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text truncate">{c.full_name || c.email}</p>
              <p className="text-xs text-text-muted truncate">{c.email}</p>
            </div>
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded flex-shrink-0 ${
              c.source === "agency"
                ? "bg-violet-500/10 text-violet-400"
                : "bg-sky-500/10 text-sky-400"
            }`}>
              {c.source === "agency" ? "Ajans" : "Marka"}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ReferenceLinksEditor({
  links,
  onChange,
}: {
  links: string[];
  onChange: (v: string[]) => void;
}) {
  const [input, setInput] = useState("");

  const add = () => {
    const url = input.trim();
    if (!url || links.includes(url)) return;
    onChange([...links, url]);
    setInput("");
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          type="url"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
          placeholder="https://referans-bağlantısı.com"
          className="flex-1 h-9 px-3 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
        />
        <button
          type="button"
          onClick={add}
          disabled={!input.trim()}
          className="h-9 px-3 rounded-lg border border-border bg-surface text-sm text-text-muted hover:text-text hover:border-accent/40 transition-colors disabled:opacity-40"
        >
          Ekle
        </button>
      </div>
      {links.length > 0 && (
        <div className="space-y-1">
          {links.map((link, i) => (
            <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-2 border border-border group">
              <svg className="w-3.5 h-3.5 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              <a href={link} target="_blank" rel="noreferrer" className="flex-1 text-xs text-accent truncate hover:underline">
                {link}
              </a>
              <button
                type="button"
                onClick={() => onChange(links.filter((_, j) => j !== i))}
                className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-danger transition-all"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SectionCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        {description && <p className="text-xs text-text-muted mt-0.5">{description}</p>}
      </div>
      {children}
    </div>
  );
}

// ============================================================
// NEW BRIEF PAGE — PREMIUM TWO-COLUMN WORKSPACE (PART 6)
// ============================================================

export default function NewBriefPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const currentAgencyId = activeAgency?.id ?? null;
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useLocale();
  const { toast } = useToast();

  // ── Form state (all fields from existing BriefCreate UI) ──────────────
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateRead | null>(null);
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [agencyMembers, setAgencyMembers] = useState<AgencyMemberRead[]>([]);
  const [brandMembers, setBrandMembers] = useState<BrandMemberRead[]>([]);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [brandId, setBrandId] = useState<string>("");
  const [priority, setPriority] = useState<BriefPriority>("normal");
  const [startDate, setStartDate] = useState<string | null>(null);
  const [draftDate, setDraftDate] = useState<string | null>(null);
  const [feedbackDate, setFeedbackDate] = useState<string | null>(null);
  const [deadline, setDeadline] = useState<string | null>(null);
  const [publishDate, setPublishDate] = useState<string | null>(null);
  const [addToCalendar, setAddToCalendar] = useState(true);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [contentTypes, setContentTypes] = useState<string[]>([]);
  const [referenceLinks, setReferenceLinks] = useState<string[]>([]);
  const [assigneeIds, setAssigneeIds] = useState<string[]>([]);

  // ── Refs for tooltips ──────────────────────────────────────────────
  const titleRef = useRef<HTMLInputElement>(null);
  const brandRef = useRef<HTMLSelectElement>(null);
  const descRef = useRef<HTMLTextAreaElement>(null);
  const startDateRef = useRef<HTMLInputElement>(null);
  const draftDateRef = useRef<HTMLInputElement>(null);
  const feedbackDateRef = useRef<HTMLInputElement>(null);
  const deadlineRef = useRef<HTMLInputElement>(null);
  const publishDateRef = useRef<HTMLInputElement>(null);
  const notesRef = useRef<HTMLTextAreaElement>(null);

  // ── Load brands ────────────────────────────────────────────────────
  useEffect(() => {
    if (!accessToken || !currentAgencyId) return;
    agencyApi.listBrands(currentAgencyId, accessToken).then(
      (res) => setBrands(res),
      () => setBrands([])
    );
  }, [accessToken, currentAgencyId]);

  // ── Selected template ──────────────────────────────────────────────
  const requestedTemplateId = searchParams.get("templateId");

useEffect(() => {
  if (!requestedTemplateId) {
    setSelectedTemplateId(null);
    setSelectedTemplate(null);
    return;
  }

  setSelectedTemplateId(requestedTemplateId);

  if (!accessToken || !currentAgencyId) {
    return;
  }

  let cancelled = false;

  void templateApi
    .get(requestedTemplateId, currentAgencyId, accessToken)
    .then((template) => {
      if (cancelled) return;

      setSelectedTemplate(template);
    })
    .catch(() => {
      if (cancelled) return;

      setSelectedTemplate(null);
      setSelectedTemplateId(null);
    });

  return () => {
    cancelled = true;
  };
}, [requestedTemplateId, accessToken, currentAgencyId]);

  // ── Assignee candidates ────────────────────────────────────────────
  const assigneeCandidates: AssigneeCandidate[] = useMemo(() => {
    if (!accessToken || !currentAgencyId) return [];
    return [
      ...agencyMembers
        .filter((m) => m.status === "active")
        .map((m) => ({
          user_id: m.user_id,
          full_name: m.user_full_name ?? "",
          email: m.user_email ?? "",
          source: "agency" as const,
          role: m.role,
        })),
      ...brandMembers
        .filter((m) => m.status === "active")
        .map((m) => ({
          user_id: m.user_id,
          full_name: m.user_full_name ?? "",
          email: m.user_email ?? "",
          source: "brand" as const,
          role: m.role,
        })),
    ];
  }, [accessToken, currentAgencyId, agencyMembers, brandMembers]);

  // ── Date order validation ──────────────────────────────────────────
  useEffect(() => {
    const present = [
      { key: "start_date", value: startDate },
      { key: "draft_date", value: draftDate },
      { key: "feedback_date", value: feedbackDate },
      { key: "deadline", value: deadline },
      { key: "publish_date", value: publishDate },
    ].filter((d) => d.value !== null);

    const dateOrder = ["start_date", "draft_date", "feedback_date", "deadline", "publish_date"];
    const labels = {
      start_date: "Başlangıç tarihi",
      draft_date: "İlk taslak tarihi",
      feedback_date: "Geri bildirim tarihi",
      deadline: "Nihai teslim tarihi",
      publish_date: "Yayın tarihi",
    };

    for (let i = 0; i < dateOrder.length - 1; i++) {
      const v1 = present.find((d) => d.key === dateOrder[i])?.value;
      const v2 = present.find((d) => d.key === dateOrder[i + 1])?.value;
      if (v1 && v2 && v1 > v2) {
        // Date order violation - handled by backend validation
      }
    }
  }, [startDate, draftDate, feedbackDate, deadline, publishDate]);

  // ── Brief summary (sticky panel) ───────────────────────────────────
  const briefSummary = useMemo(() => {
    const items: Record<string, string> = {};

    if (title.trim()) items["Brief Adı"] = title.trim();
    if (brandId) items["Marka"] = brands.find((b) => b.id === brandId)?.name ?? "—";
    if (selectedTemplate) items["Template"] = selectedTemplate?.name ?? "—";
    if (priority) items["Öncelik"] = PRIORITY_OPTIONS.find((p) => p.value === priority)?.label ?? priority;
    if (platforms.length > 0) items["Platformlar"] = platforms.join(", ");
    if (contentTypes.length > 0) items["İçerik Tipi"] = contentTypes.join(", ");
    if (deadline) items["Son Tarih"] = new Date(deadline).toLocaleDateString("tr-TR", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
    if (startDate) items["Başlangıç"] = new Date(startDate).toLocaleDateString("tr-TR");
    if (draftDate) items["Taslak"] = new Date(draftDate).toLocaleDateString("tr-TR");
    if (feedbackDate) items["Geri Bildirim"] = new Date(feedbackDate).toLocaleDateString("tr-TR");
    if (publishDate) items["Yayın"] = new Date(publishDate).toLocaleDateString("tr-TR");
    if (addToCalendar) items["Takvim"] = "Eklenecek";

    return Object.keys(items).length > 0 ? items : null;
  }, [title, brandId, selectedTemplate, priority, platforms, contentTypes, deadline, startDate, draftDate, feedbackDate, publishDate, addToCalendar, brands]);

  // ── Handle create ──────────────────────────────────────────────────
  const handleCreate = useCallback(async () => {
    if (!accessToken || !currentAgencyId || !title.trim()) {
      toast("Brief başlığınızı giriniz.", "error");
      return;
    }

    setCreating(true);
    try {
      const brief = await briefApi.create(
        {
          template_id: selectedTemplateId ?? undefined,
          brand_id: brandId || undefined,
          title: title.trim(),
          description: description.trim() || undefined,
          priority,
          deadline: deadline || undefined,
          start_date: startDate || undefined,
          draft_date: draftDate || undefined,
          feedback_date: feedbackDate || undefined,
          publish_date: publishDate || undefined,
          add_to_calendar: addToCalendar,
          platforms,
          content_types: contentTypes,
          reference_links: referenceLinks,
          assignee_ids: assigneeIds,
        },
        currentAgencyId,
        accessToken
      );
      router.push(`/dashboard/briefs/${brief.id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Brief oluşturulamadı.";
      toast(msg, "error");
    }
  }, [
    accessToken,
    currentAgencyId,
    title,
    description,
    priority,
    deadline,
    startDate,
    draftDate,
    feedbackDate,
    publishDate,
    addToCalendar,
    platforms,
    contentTypes,
    referenceLinks,
    assigneeIds,
    selectedTemplateId,
    brandId,
  ]);

  // ── Load brands once ───────────────────────────────────────────────
  useEffect(() => {
    if (!accessToken || !currentAgencyId) return;
    agencyApi.listBrands(currentAgencyId, accessToken).then(
      (res) => setBrands(res),
      () => setBrands([])
    );
  }, [accessToken, currentAgencyId]);

  // ── Creating state ─────────────────────────────────────────────────
  const [creating, setCreating] = useState(false);

  // ── Desktop layout components ──────────────────────────────────────
  const desktopLayout = (
    <div className="grid md:grid-cols-2 gap-6">

      {/* LEFT COLUMN: Main Form */}
      <div className="space-y-6">

        {/* Section A: Brief Temeli */}
        <SectionCard title="Brief Temeli">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">
                Brief Başlığı <span className="text-red-400">*</span>
              </label>
              <InfoTooltip
                targetRef={titleRef}
                text="Brief'in başlığını verici ve özet olmalı. Kampanyanın ana konusunu ve hedef kitleyi açıklar."
                title="Brief Başlığı"
              >
                <input
                  ref={titleRef}
                  type="text"
                  autoFocus
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                  placeholder="örn. Yaz Koleksiyonu Sosyal Medya Kampanyası"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </InfoTooltip>
            </div>

            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">Marka</label>
              <InfoTooltip
                targetRef={brandRef}
                text="Brief'i bu markaya bağlamak istiyorsanız seçin. Marka seçilmezse briefler genel agency dashboard'ında görünür."
                title="Marka Seçimi"
              >
                <select
                  ref={brandRef}
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
                  value={brandId}
                  onChange={(e) => setBrandId(e.target.value)}
                >
                  <option value="">Marka seçin (opsiyonel)</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}</option>
                  ))}
                </select>
              </InfoTooltip>
            </div>
          </div>
        </SectionCard>

        {/* Section B: İçerik */}
        <SectionCard title="İçerik">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">
                Açıklama <span className="text-red-400">*</span>
              </label>
              <InfoTooltip
                targetRef={descRef}
                text="Brief'in amacını, kapsamını ve beklentilerinizi açıklayın. İçeriğin türünü ve hedef kitleyi belirtin."
                title="Brief Açıklaması"
              >
                <textarea
                  ref={descRef}
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-y transition-colors"
                  placeholder="Brief hakkında detaylar, beklentiler, notlar…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                />
              </InfoTooltip>
            </div>

            <div className="sm:col-span-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-text-muted mb-1.5">Öncelik</label>
                  <SectionCard title="Öncelik">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {PRIORITY_OPTIONS.map((p) => (
                        <button
                          key={p.value}
                          type="button"
                          onClick={() => setPriority(p.value)}
                          className={`py-2.5 px-2 rounded-lg text-xs font-semibold transition-all ${
                            priority === p.value ? p.color : "border border-border bg-surface text-text-muted hover:border-border-hover hover:text-text"
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </SectionCard>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-muted mb-1.5">Platformlar</label>
                  <InfoTooltip
                    text="Brief'i yayınlayacağınız platformları seçin. Birden fazla platform seçilebilir."
                    title="Platform Seçimi"
                  >
                    <MultiSelectChips
                      options={PLATFORM_OPTIONS}
                      selected={platforms}
                      onChange={setPlatforms}
                    />
                  </InfoTooltip>
                  {platforms.length > 0 && (
                    <p className="text-xs text-text-muted mt-1">{platforms.length} platform seçildi</p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-muted mb-1.5">İçerik Tipi</label>
                  <InfoTooltip
                    text="Brief için üretilecek içerik türlerini seçin."
                    title="İçerik Tipi"
                  >
                    <MultiSelectChips
                      options={CONTENT_TYPE_OPTIONS}
                      selected={contentTypes}
                      onChange={setContentTypes}
                    />
                  </InfoTooltip>
                  {contentTypes.length > 0 && (
                    <p className="text-xs text-text-muted mt-1">{contentTypes.length} içerik tipi seçildi</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </SectionCard>

        {/* Section C: Planlama */}
        <SectionCard title="Planlama">
          <p className="text-xs text-text-muted mb-2">
            Brief planlama tarihleri. Tüm tarihler YYYY-MM-DD formatında girilmelidir.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">
                Başlangıç Tarihi
              </label>
              <InfoTooltip
                targetRef={startDateRef}
                text="Brief'in başlangıç tarihi. Başka tarihlerden önce olmalı."
                title="Başlangıç Tarihi"
              >
                <input
                  ref={startDateRef}
                  type="date"
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
                  value={startDate ?? ""}
                  onChange={(e) => setStartDate(e.target.value || null)}
                />
              </InfoTooltip>
            </div>

            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">
                Taslak Tarihi
              </label>
              <InfoTooltip
                targetRef={draftDateRef}
                text="İlk taslak tarihini belirler."
                title="Taslak Tarihi"
              >
                <input
                  ref={draftDateRef}
                  type="date"
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
                  value={draftDate ?? ""}
                  onChange={(e) => setDraftDate(e.target.value || null)}
                />
              </InfoTooltip>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">
                Geri Bildirim Tarihi
              </label>
              <InfoTooltip
                targetRef={feedbackDateRef}
                text="Geri bildirim alınacak tarih."
                title="Geri Bildirim Tarihi"
              >
                <input
                  ref={feedbackDateRef}
                  type="date"
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
                  value={feedbackDate ?? ""}
                  onChange={(e) => setFeedbackDate(e.target.value || null)}
                />
              </InfoTooltip>
            </div>

            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">
                Son Tarih (Deadline) <span className="text-red-400">*</span>
              </label>
              <InfoTooltip
                targetRef={deadlineRef}
                text="Brief'in teslim tarihini belirler. Ajans bu tarihe göre çalışma planlar ve üretim zamanını ayarlar."
                title="Son Tarih"
              >
                <input
                  ref={deadlineRef}
                  type="date"
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
                  value={deadline ?? ""}
                  onChange={(e) => setDeadline(e.target.value || null)}
                />
              </InfoTooltip>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Yayın Tarihi
            </label>
            <InfoTooltip
              targetRef={publishDateRef}
              text="Brief'in yayın tarihini belirler."
              title="Yayın Tarihi"
            >
              <input
                ref={publishDateRef}
                type="date"
                className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
                value={publishDate ?? ""}
                onChange={(e) => setPublishDate(e.target.value || null)}
              />
            </InfoTooltip>
          </div>

          <div className="flex items-center gap-3 mt-3">
            <input
              type="checkbox"
              checked={addToCalendar}
              onChange={(e) => setAddToCalendar(e.target.checked)}
              className="w-4 h-4 rounded border border-border bg-background cursor-pointer"
            />
            <span className="text-sm text-text">
              Takvime eklenecek
            </span>
          </div>
        </SectionCard>

        {/* Section D: Referanslar ve Notlar */}
        <SectionCard title="Referanslar & Notlar">
          <ReferenceLinksEditor
            links={referenceLinks}
            onChange={setReferenceLinks}
          />
          {referenceLinks.length > 0 && (
            <p className="text-xs text-text-muted mt-2">
              {referenceLinks.length} bağlantı eklendi
            </p>
          )}

          <div className="mt-3">
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              İç Notlar (Dahili)
            </label>
            <InfoTooltip
              targetRef={notesRef}
              text="Sadece iç kullanım için notlar. Müşteriye görünmez."
              title="İç Notlar"
            >
              <textarea
                ref={notesRef}
                className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-y transition-colors"
                placeholder="Dahili notlar ve hatırlatmalar…"
                rows={3}
                disabled
              />
            </InfoTooltip>
          </div>
        </SectionCard>
      </div>

      {/* RIGHT COLUMN: Sticky Brief Summary (desktop only) */}
      <aside className="sticky top-6 h-screen bg-surface border-l border-border rounded-r-xl p-5 space-y-3 max-w-sm">
        <div className="border border-border rounded-xl p-4 mb-4">
          <h3 className="text-sm font-semibold text-text mb-3">
            Brief Özeti
          </h3>
          {briefSummary ? (
            <div className="space-y-2 text-sm text-text">
              {Object.entries(briefSummary).map(
                ([label, value], i) => (
                  <div key={i} className="flex justify-between pt-1.5">
                    <span className="text-text-muted">{label}:</span>
                    <span>{value}</span>
                  </div>
                )
              )}
            </div>
          ) : (
            <p className="text-text-muted text-center py-8">
              Henüz veri girmedi.
            </p>
          )}
        </div>

        {/* Template info if selected */}
        {selectedTemplate && (
          <div className="p-3 bg-accent/5 border border-accent/20 rounded-lg mb-3">
            <p className="text-xs text-accent mb-1">
              Şablon Kullanımı:
            </p>
            <p className="text-xs text-text-muted line-clamp-2">
              {selectedTemplate.description || "Açıklama yok"}
            </p>
          </div>
        )}

        {/* Action bar at bottom */}
        <div className="pt-4 border-t border-border">
          <button
            onClick={handleCreate}
            disabled={creating}
            className={`w-full px-4 py-2.5 rounded-lg text-sm font-medium ${
              creating ? "bg-accent/5 text-accent disabled:opacity-50" : "bg-accent text-white"
            } hover:bg-accent/90 transition-colors flex items-center gap-2`}
          >
            {creating ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Oluşturuluyor…
              </>
            ) : (
              <>
                Brief Oluştur
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </>
            )}
          </button>
        </div>
      </aside>
    </div>
  );

  // Mobile layout component
  const mobileLayout = (
    <div className="space-y-6">
      <SectionCard title="Brief Temeli">
        <div className="grid grid-cols-1 gap-4">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Brief Başlığı <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              placeholder="örn. Yaz Koleksiyonu Sosyal Medya Kampanyası"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Marka</label>
            <select
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
              value={brandId}
              onChange={(e) => setBrandId(e.target.value)}
            >
              <option value="">Marka seçin (opsiyonel)</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="İçerik">
        <textarea
          className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-y transition-colors"
          placeholder="Brief hakkında detaylar..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
        />
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Öncelik</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setPriority(p.value)}
                  className={`py-2.5 px-2 rounded-lg text-xs font-semibold transition-all ${
                    priority === p.value ? p.color : "border border-border bg-surface text-text-muted hover:border-border-hover hover:text-text"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Platformlar</label>
            <MultiSelectChips
              options={PLATFORM_OPTIONS}
              selected={platforms}
              onChange={setPlatforms}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">İçerik Tipi</label>
            <MultiSelectChips
              options={CONTENT_TYPE_OPTIONS}
              selected={contentTypes}
              onChange={setContentTypes}
            />
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Planlama">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Başlangıç Tarihi
            </label>
            <input
              type="date"
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
              value={startDate ?? ""}
              onChange={(e) => setStartDate(e.target.value || null)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Taslak Tarihi
            </label>
            <input
              type="date"
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
              value={draftDate ?? ""}
              onChange={(e) => setDraftDate(e.target.value || null)}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Geri Bildirim Tarihi
            </label>
            <input
              type="date"
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
              value={feedbackDate ?? ""}
              onChange={(e) => setFeedbackDate(e.target.value || null)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Son Tarih (Deadline) <span className="text-red-400">*</span>
            </label>
            <input
              type="date"
              className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
              value={deadline ?? ""}
              onChange={(e) => setDeadline(e.target.value || null)}
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1.5">
            Yayın Tarihi
          </label>
          <input
            type="date"
            className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
            value={publishDate ?? ""}
            onChange={(e) => setPublishDate(e.target.value || null)}
          />
        </div>
        <div className="flex items-center gap-3 mt-3">
          <input
            type="checkbox"
            checked={addToCalendar}
            onChange={(e) => setAddToCalendar(e.target.checked)}
            className="w-4 h-4 rounded border border-border bg-background cursor-pointer"
          />
          <span className="text-sm text-text">Takvime eklenecek</span>
        </div>
      </SectionCard>

      <SectionCard title="Referanslar & Notlar">
        <ReferenceLinksEditor
          links={referenceLinks}
          onChange={setReferenceLinks}
        />
        {referenceLinks.length > 0 && (
          <p className="text-xs text-text-muted mt-2">
            {referenceLinks.length} bağlantı eklendi
          </p>
        )}
        <div className="mt-3">
          <textarea
            className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-y transition-colors"
            placeholder="Dahili notlar..."
            rows={3}
            disabled
          />
        </div>
      </SectionCard>
    </div>
  );

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-background">
      {/* ---- Header ---- */}
      <header className="border-b border-border bg-surface px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div>
            <button
              onClick={() => router.back()}
              className="text-sm text-text-muted hover:text-text transition-colors flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Geri
            </button>
            <h1 className="text-xl font-semibold text-text">Yeni Brief Oluştur</h1>
          </div>

          {/* Template selection */}
          {currentAgencyId && selectedTemplateId && selectedTemplate && (
            <span className="text-xs font-medium text-accent bg-accent/10 px-2.5 py-1 rounded-full">
              {selectedTemplate.name}
            </span>
          )}

          {/* Unsaved changes indicator */}
          <span className="text-xs text-text-muted">
            {"briefs.center brief created"}
          </span>
        </div>
      </header>

      {/* ---- Main Content ────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto p-6 pb-8">
        {currentAgencyId ? (
          desktopLayout
        ) : (
          mobileLayout
        )}
      </main>

      {/* ---- Footer CTA (always visible) ---- */}
      <footer className="border-t border-border bg-surface mt-6 p-6">
        <div className="max-w-7xl mx-auto flex gap-3">
          <button
            onClick={handleCreate}
            disabled={creating}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium ${
              creating ? "bg-accent/5 text-accent disabled:opacity-50" : "bg-accent text-white"
            } hover:bg-accent/90 transition-colors`}
          >
            {creating ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Oluşturuluyor…
              </>
            ) : (
              <>
                Brief Oluştur
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </>
            )}
          </button>
        </div>
      </footer>
    </div>
  );
}