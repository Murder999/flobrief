"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  templateApi,
  briefApi,
  agencyApi,
  brandIdentityApi,
  type TemplateRead,
  type BrandRead,
  type BriefPriority,
  type AgencyMemberRead,
  type BrandMemberRead,
  type BrandDNASummary,
} from "@/lib/api-client";

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
              active
                ? "border-accent/50 bg-accent/5"
                : "border-border bg-surface hover:border-border-hover"
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
          className="flex-1 h-9 px-3 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
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

export default function NewBriefPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const currentAgencyId = activeAgency?.id ?? null;
  const router = useRouter();

  const [step, setStep] = useState<Step>("template");
  const [templates, setTemplates] = useState<TemplateRead[]>([]);
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [agencyMembers, setAgencyMembers] = useState<AgencyMemberRead[]>([]);
  const [brandMembers, setBrandMembers] = useState<BrandMemberRead[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state — Step 1
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  const [dnaSummary, setDnaSummary] = useState<BrandDNASummary | null>(null);

  // Form state — Step 2: Content
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [brandId, setBrandId] = useState<string>("");
  const [priority, setPriority] = useState<BriefPriority>("normal");
  const [deadline, setDeadline] = useState("");
  const [addToCalendar, setAddToCalendar] = useState(true);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [contentTypes, setContentTypes] = useState<string[]>([]);

  // Form state — Step 3: People & Media
  const [assigneeIds, setAssigneeIds] = useState<string[]>([]);
  const [referenceLinks, setReferenceLinks] = useState<string[]>([]);

  useEffect(() => {
    if (!accessToken || !currentAgencyId) return;
    const load = async () => {
      setLoadingTemplates(true);
      try {
        const [tmplRes, brandRes, memberRes] = await Promise.all([
          templateApi.list(currentAgencyId, accessToken),
          agencyApi.listBrands(currentAgencyId, accessToken),
          agencyApi.listMembers(currentAgencyId, accessToken),
        ]);
        setTemplates(tmplRes);
        setBrands(brandRes);
        setAgencyMembers(memberRes);
      } finally {
        setLoadingTemplates(false);
      }
    };
    load();
  }, [accessToken, currentAgencyId]);

  const loadBrandMembers = useCallback(async (bId: string) => {
    if (!accessToken || !currentAgencyId || !bId) {
      setBrandMembers([]);
      return;
    }
    try {
      const members = await agencyApi.listBrandMembers(bId, currentAgencyId, accessToken);
      setBrandMembers(members);
    } catch {
      setBrandMembers([]);
    }
  }, [accessToken, currentAgencyId]);

  useEffect(() => {
    if (brandId) loadBrandMembers(brandId);
    else setBrandMembers([]);
  }, [brandId, loadBrandMembers]);

  useEffect(() => {
    if (!brandId || !accessToken || !currentAgencyId) {
      setDnaSummary(null);
      return;
    }
    brandIdentityApi.getDNASummary(brandId, currentAgencyId, accessToken)
      .then(s => setDnaSummary(s))
      .catch(() => setDnaSummary(null));
  }, [brandId, accessToken, currentAgencyId]);

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId) ?? null;

  const assigneeCandidates: AssigneeCandidate[] = [
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

  const handleCreate = async () => {
    if (!accessToken || !currentAgencyId || !title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const brief = await briefApi.create(
        {
          template_id: selectedTemplateId ?? undefined,
          brand_id: brandId || undefined,
          title: title.trim(),
          description: description.trim() || undefined,
          priority,
          deadline: deadline || undefined,
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
      setError(msg);
      setCreating(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => router.back()}
          className="text-sm text-text-muted hover:text-text transition-colors mb-3 flex items-center gap-1.5"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Geri
        </button>
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-text">Yeni Brief Oluştur</h1>
          {selectedTemplate && (
            <span className="text-xs font-medium text-accent bg-accent/10 px-2.5 py-1 rounded-full">
              {selectedTemplate.name}
            </span>
          )}
        </div>
      </div>

      <StepIndicator current={step} onNavigate={setStep} />

      {/* ─── STEP 1: Template ─── */}
      {step === "template" && (
        <div>
          <p className="text-sm text-text-muted mb-5">
            Hazır sektör şablonlarından birini seçin veya boş başlayın.
          </p>

          {loadingTemplates ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-28 bg-surface-2 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setSelectedTemplateId(null)}
                className={`text-left p-4 rounded-xl border-2 transition-all ${
                  selectedTemplateId === null
                    ? "border-accent bg-accent/5 shadow-sm"
                    : "border-border bg-surface hover:border-accent/30"
                }`}
              >
                <div className="w-8 h-8 rounded-lg bg-surface-2 flex items-center justify-center mb-3 text-base">📄</div>
                <div className="font-medium text-sm text-text">Şablonsuz Brief</div>
                <div className="text-xs text-text-muted mt-1">Boş başla, kendin yapılandır</div>
              </button>
              {templates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelectedTemplateId(t.id)}
                  className={`text-left p-4 rounded-xl border-2 transition-all ${
                    selectedTemplateId === t.id
                      ? "border-accent bg-accent/5 shadow-sm"
                      : "border-border bg-surface hover:border-accent/30"
                  }`}
                >
                  {t.industry && (
                    <span className="text-[10px] font-semibold text-accent/80 bg-accent/10 px-2 py-0.5 rounded-full uppercase tracking-wide">
                      {INDUSTRY_LABEL[t.industry] ?? t.industry}
                    </span>
                  )}
                  <div className="font-medium text-sm text-text mt-2 leading-snug">{t.name}</div>
                  {t.description && (
                    <p className="text-xs text-text-muted mt-1 line-clamp-2">{t.description}</p>
                  )}
                </button>
              ))}
            </div>
          )}

          <div className="flex justify-end mt-6">
            <button
              onClick={() => setStep("details")}
              className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors flex items-center gap-2"
            >
              Devam
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* ─── STEP 2: Content Details ─── */}
      {step === "details" && (
        <div className="space-y-4">
          {/* Core info */}
          <SectionCard title="Temel Bilgiler" description="Brief başlığı, marka ve son tarih">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">
                Brief Başlığı <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                autoFocus
                className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                placeholder="örn. Yaz Koleksiyonu Sosyal Medya Kampanyası"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">Açıklama</label>
              <textarea
                className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-y transition-colors"
                placeholder="Brief hakkında detaylar, beklentiler, notlar…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
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
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1.5">Son Tarih</label>
                <input
                  type="date"
                  className="w-full px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 transition-colors"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                />
              </div>
            </div>

            {/* DNA Summary */}
            {brandId && (
              <div className={`rounded-lg border px-4 py-3 text-xs ${
                dnaSummary?.profile_id
                  ? "border-accent/20 bg-accent/5"
                  : "border-border bg-surface-2/50"
              }`}>
                {dnaSummary?.profile_id ? (
                  <div>
                    <p className="font-medium text-text mb-1.5 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent inline-block" />
                      Marka DNA Özeti
                      {dnaSummary.status === "approved" && (
                        <span className="text-success text-[10px] bg-success/10 px-1.5 py-0.5 rounded-full">Onaylandı</span>
                      )}
                    </p>
                    {dnaSummary.summary && (
                      <p className="text-text-muted line-clamp-2 mb-2">{dnaSummary.summary}</p>
                    )}
                    <div className="flex flex-wrap gap-3 mt-1">
                      {dnaSummary.primary_colors && dnaSummary.primary_colors.slice(0, 4).map((c, i) => (
                        c.hex && (
                          <div key={i} className="flex items-center gap-1">
                            <div className="w-4 h-4 rounded border border-border/50" style={{ backgroundColor: c.hex }} />
                            <span className="font-mono text-text-muted">{c.hex}</span>
                          </div>
                        )
                      ))}
                      {dnaSummary.typography && dnaSummary.typography.slice(0, 2).map((f, i) => (
                        f.family && (
                          <span key={i} className="text-text-muted bg-surface rounded px-1.5 py-0.5 border border-border/50">
                            {f.family}
                          </span>
                        )
                      ))}
                    </div>
                    {dnaSummary.dont_rules && dnaSummary.dont_rules.length > 0 && (
                      <p className="text-danger/80 mt-2">
                        ⚠ {dnaSummary.dont_rules[0]}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-text-muted">
                    Bu marka için henüz Marka DNA oluşturulmadı.{" "}
                    <a href={`/dashboard/brands/${brandId}`} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                      Kurumsal kimlik dosyası yükle
                    </a>
                  </p>
                )}
              </div>
            )}

            {deadline && (
              <button
                type="button"
                onClick={() => setAddToCalendar(!addToCalendar)}
                className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl border transition-all text-left ${
                  addToCalendar ? "border-accent/40 bg-accent/5" : "border-border bg-surface"
                }`}
              >
                <div className={`w-9 h-5 rounded-full relative transition-colors flex-shrink-0 ${addToCalendar ? "bg-accent" : "bg-border"}`}>
                  <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${addToCalendar ? "left-[18px]" : "left-0.5"}`} />
                </div>
                <p className="text-sm text-text">
                  {addToCalendar ? "Takvime eklenecek" : "Takvime eklenmeyecek"}
                </p>
              </button>
            )}
          </SectionCard>

          {/* Priority */}
          <SectionCard title="Öncelik">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {PRIORITY_OPTIONS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setPriority(p.value)}
                  className={`py-2.5 px-2 rounded-lg text-xs font-semibold transition-all ${
                    priority === p.value
                      ? p.color
                      : "border border-border bg-surface text-text-muted hover:border-border-hover hover:text-text"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </SectionCard>

          {/* Platforms */}
          <SectionCard title="Platformlar" description="Hangi platformlarda yayınlanacak? (çoklu seçim)">
            <MultiSelectChips
              options={PLATFORM_OPTIONS}
              selected={platforms}
              onChange={setPlatforms}
            />
            {platforms.length > 0 && (
              <p className="text-xs text-text-muted">{platforms.length} platform seçildi</p>
            )}
          </SectionCard>

          {/* Content Types */}
          <SectionCard title="İçerik Tipi" description="Ne tür içerik üretilecek? (çoklu seçim)">
            <MultiSelectChips
              options={CONTENT_TYPE_OPTIONS}
              selected={contentTypes}
              onChange={setContentTypes}
            />
            {contentTypes.length > 0 && (
              <p className="text-xs text-text-muted">{contentTypes.length} içerik tipi seçildi</p>
            )}
          </SectionCard>

          <div className="flex justify-between pt-2">
            <button
              onClick={() => setStep("template")}
              className="px-4 py-2.5 border border-border rounded-lg text-sm text-text-muted hover:text-text hover:border-border-hover transition-colors flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Geri
            </button>
            <button
              onClick={() => setStep("people")}
              disabled={!title.trim()}
              className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              Devam
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* ─── STEP 3: People & Media ─── */}
      {step === "people" && (
        <div className="space-y-4">
          <SectionCard
            title="Atanan Kişiler"
            description="Bu brief üzerinde çalışacak ajans ve marka ekip üyelerini seçin"
          >
            <AssigneePicker
              candidates={assigneeCandidates}
              selected={assigneeIds}
              onChange={setAssigneeIds}
            />
            {assigneeIds.length > 0 && (
              <p className="text-xs text-text-muted">{assigneeIds.length} kişi seçildi</p>
            )}
          </SectionCard>

          <SectionCard
            title="Referans Bağlantıları"
            description="İlham veya referans için URL ekleyin"
          >
            <ReferenceLinksEditor links={referenceLinks} onChange={setReferenceLinks} />
          </SectionCard>

          <div className="flex justify-between pt-2">
            <button
              onClick={() => setStep("details")}
              className="px-4 py-2.5 border border-border rounded-lg text-sm text-text-muted hover:text-text hover:border-border-hover transition-colors flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Geri
            </button>
            <button
              onClick={() => setStep("review")}
              className="px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors flex items-center gap-2"
            >
              İncele
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* ─── STEP 4: Review & Create ─── */}
      {step === "review" && (
        <div>
          <p className="text-sm text-text-muted mb-5">Bilgileri kontrol edin ve brief&apos;i oluşturun.</p>

          <div className="bg-surface rounded-xl border border-border overflow-hidden mb-5">
            {[
              { label: "Başlık", value: title },
              description && { label: "Açıklama", value: description },
              { label: "Şablon", value: selectedTemplate?.name ?? "Şablonsuz" },
              brandId && { label: "Marka", value: brands.find((b) => b.id === brandId)?.name ?? "—" },
              { label: "Öncelik", value: PRIORITY_OPTIONS.find((p) => p.value === priority)?.label ?? priority },
              deadline && {
                label: "Son Tarih",
                value: new Date(deadline).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }),
              },
              platforms.length > 0 && { label: "Platformlar", value: platforms.join(", ") },
              contentTypes.length > 0 && { label: "İçerik Tipi", value: contentTypes.join(", ") },
              assigneeIds.length > 0 && {
                label: "Atananlar",
                value: assigneeIds
                  .map((id) => assigneeCandidates.find((c) => c.user_id === id)?.full_name ?? id)
                  .join(", "),
              },
              referenceLinks.length > 0 && { label: "Referanslar", value: `${referenceLinks.length} bağlantı` },
            ]
              .filter(Boolean)
              .map((row, i) => {
                const r = row as { label: string; value: string };
                return (
                  <div key={i} className="px-5 py-3.5 flex gap-4 border-b border-border last:border-0">
                    <span className="text-xs font-medium text-text-muted w-28 flex-shrink-0 pt-0.5">{r.label}</span>
                    <span className="text-sm text-text">{r.value}</span>
                  </div>
                );
              })}
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="flex justify-between">
            <button
              onClick={() => setStep("people")}
              className="px-4 py-2.5 border border-border rounded-lg text-sm text-text-muted hover:text-text hover:border-border-hover transition-colors flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Geri
            </button>
            <button
              onClick={handleCreate}
              disabled={creating}
              className="px-6 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors flex items-center gap-2"
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
        </div>
      )}
    </div>
  );
}
