"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useLocale } from "@/context/locale-context";
import { useToast } from "@/components/ui/toast";
import {
  agencyApi,
  briefApi,
  templateApi,
  type AgencyMemberRead,
  type BrandMemberRead,
  type BrandRead,
  type BriefPriority,
  type TemplateRead,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";

const PRIORITY_OPTIONS = [
  { value: "low", labelKey: "briefs.priority.low", color: "status-neutral" },
  { value: "normal", labelKey: "briefs.priority.normal", color: "status-info" },
  { value: "high", labelKey: "briefs.priority.high", color: "status-warning" },
  { value: "urgent", labelKey: "briefs.priority.urgent", color: "status-danger" },
] as const satisfies ReadonlyArray<{
  value: BriefPriority;
  labelKey: "briefs.priority.low" | "briefs.priority.normal" | "briefs.priority.high" | "briefs.priority.urgent";
  color: string;
}>;

const PLATFORM_OPTIONS = [
  { value: "Instagram", labelKey: "briefs.new.platform.instagram" },
  { value: "TikTok", labelKey: "briefs.new.platform.tiktok" },
  { value: "YouTube", labelKey: "briefs.new.platform.youtube" },
  { value: "Twitter/X", labelKey: "briefs.new.platform.twitter" },
  { value: "LinkedIn", labelKey: "briefs.new.platform.linkedin" },
  { value: "Facebook", labelKey: "briefs.new.platform.facebook" },
  { value: "Pinterest", labelKey: "briefs.new.platform.pinterest" },
  { value: "Snapchat", labelKey: "briefs.new.platform.snapchat" },
  { value: "Twitch", labelKey: "briefs.new.platform.twitch" },
  { value: "Podcast", labelKey: "briefs.new.platform.podcast" },
  { value: "Blog", labelKey: "briefs.new.platform.blog" },
  { value: "E-posta", labelKey: "briefs.new.platform.email" },
  { value: "SMS", labelKey: "briefs.new.platform.sms" },
  { value: "Web Sitesi", labelKey: "briefs.new.platform.website" },
  { value: "OOH", labelKey: "briefs.new.platform.ooh" },
] as const;

const CONTENT_TYPE_OPTIONS = [
  { value: "Fotoğraf", labelKey: "briefs.new.contentType.photo" },
  { value: "Video", labelKey: "briefs.new.contentType.video" },
  { value: "Reels / Short", labelKey: "briefs.new.contentType.shortVideo" },
  { value: "Story", labelKey: "briefs.new.contentType.story" },
  { value: "Carousel", labelKey: "briefs.new.contentType.carousel" },
  { value: "Infografik", labelKey: "briefs.new.contentType.infographic" },
  { value: "Animasyon", labelKey: "briefs.new.contentType.animation" },
  { value: "Metin / Yazı", labelKey: "briefs.new.contentType.copy" },
  { value: "Podcast Bölümü", labelKey: "briefs.new.contentType.podcastEpisode" },
  { value: "Haber Bülteni", labelKey: "briefs.new.contentType.newsletter" },
  { value: "Banner Reklam", labelKey: "briefs.new.contentType.bannerAd" },
  { value: "Case Study", labelKey: "briefs.new.contentType.caseStudy" },
  { value: "Sunum", labelKey: "briefs.new.contentType.presentation" },
] as const;

type DateFieldKey = "startDate" | "draftDate" | "feedbackDate" | "deadline" | "publishDate";

interface AssigneeCandidate {
  userId: string;
  fullName: string;
  email: string;
  source: "agency" | "brand";
}

interface SelectOption {
  value: string;
  label: string;
}

const inputClassName =
  "w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-text outline-none transition-colors placeholder:text-text-muted/50 focus:border-accent focus:ring-2 focus:ring-accent/25";

function MultiSelectChips({
  options,
  selected,
  onChange,
}: {
  options: SelectOption[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => {
        const active = selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() =>
              onChange(active ? selected.filter((value) => value !== option.value) : [...selected, option.value])
            }
            className={cn(
              "min-h-10 rounded-full border px-3 py-2 text-xs font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent/40",
              active
                ? "border-accent bg-accent text-white"
                : "border-border bg-surface-2 text-text-muted hover:border-accent/40 hover:text-text"
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function AssigneePicker({
  candidates,
  selected,
  onChange,
}: {
  candidates: AssigneeCandidate[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const { t } = useLocale();

  if (candidates.length === 0) {
    return <p className="text-xs text-text-muted">{t("briefs.new.assignees.empty")}</p>;
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {candidates.map((candidate) => {
        const active = selected.includes(candidate.userId);
        const displayName = candidate.fullName || candidate.email;
        return (
          <button
            key={candidate.userId}
            type="button"
            aria-pressed={active}
            onClick={() =>
              onChange(active ? selected.filter((id) => id !== candidate.userId) : [...selected, candidate.userId])
            }
            className={cn(
              "flex min-w-0 items-center gap-3 rounded-lg border px-3 py-2 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent/40",
              active ? "border-accent/50 bg-accent/5" : "border-border bg-background hover:border-border-hover"
            )}
          >
            <span
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                active ? "bg-accent text-white" : "bg-surface-2 text-text-muted"
              )}
            >
              {displayName[0]?.toUpperCase() ?? "?"}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-text">{displayName}</span>
              <span className="block truncate text-xs text-text-muted">{candidate.email}</span>
            </span>
            <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-text-muted">
              {candidate.source === "agency" ? t("briefs.new.assignees.agency") : t("briefs.new.assignees.brand")}
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
  onChange: (values: string[]) => void;
}) {
  const { t } = useLocale();
  const [input, setInput] = useState("");

  const addLink = () => {
    const link = input.trim();
    if (!link || links.includes(link)) return;
    onChange([...links, link]);
    setInput("");
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="reference-link"
          type="url"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addLink();
            }
          }}
          placeholder={t("briefs.new.references.placeholder")}
          className={cn(inputClassName, "min-w-0 flex-1")}
        />
        <button
          type="button"
          onClick={addLink}
          disabled={!input.trim()}
          className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium text-text outline-none transition-colors hover:border-accent/40 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-accent/40"
        >
          {t("briefs.new.references.add")}
        </button>
      </div>

      {links.length > 0 ? (
        <ul className="space-y-2">
          {links.map((link) => (
            <li key={link} className="flex min-w-0 items-center gap-2 rounded-lg bg-surface-2 px-3 py-2">
              <a
                href={link}
                target="_blank"
                rel="noreferrer"
                className="min-w-0 flex-1 truncate text-xs text-accent outline-none hover:underline focus-visible:ring-2 focus-visible:ring-accent/40"
              >
                {link}
              </a>
              <button
                type="button"
                onClick={() => onChange(links.filter((item) => item !== link))}
                aria-label={t("briefs.new.references.remove", { link })}
                className="rounded p-1 text-text-muted outline-none transition-colors hover:bg-danger/10 hover:text-danger focus-visible:ring-2 focus-visible:ring-accent/40"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="p-5 sm:p-6">
      <div className="mb-5">
        <h2 className="text-base font-semibold tracking-tight text-text">{title}</h2>
        <p className="mt-1 text-sm text-text-muted">{description}</p>
      </div>
      {children}
    </section>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] gap-3 border-b border-border/70 py-2.5 last:border-b-0">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="min-w-0 break-words text-right text-xs font-medium text-text">{value}</dd>
    </div>
  );
}

export default function NewBriefPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const { intlLocale, t } = useLocale();
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentAgencyId = activeAgency?.id ?? null;

  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateRead | null>(null);
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [agencyMembers, setAgencyMembers] = useState<AgencyMemberRead[]>([]);
  const [brandMembers, setBrandMembers] = useState<BrandMemberRead[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [brandId, setBrandId] = useState("");
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
  const [creating, setCreating] = useState(false);
  const [titleError, setTitleError] = useState(false);

  const creatingRef = useRef(false);
  const allowNavigationRef = useRef(false);
  const dateRefs = useRef<Record<DateFieldKey, HTMLInputElement | null>>({
    startDate: null,
    draftDate: null,
    feedbackDate: null,
    deadline: null,
    publishDate: null,
  });

  const requestedTemplateId = searchParams.get("templateId");
  const requestedBrandId = searchParams.get("brand_id") ?? searchParams.get("brandId");

  useEffect(() => {
    if (!accessToken || !currentAgencyId) {
      setBrands([]);
      setAgencyMembers([]);
      return;
    }

    let cancelled = false;
    void Promise.all([
      agencyApi.listBrands(currentAgencyId, accessToken).catch(() => [] as BrandRead[]),
      agencyApi.listMembers(currentAgencyId, accessToken).catch(() => [] as AgencyMemberRead[]),
    ]).then(([brandList, memberList]) => {
      if (cancelled) return;
      setBrands(brandList);
      setAgencyMembers(memberList);
      if (requestedBrandId && brandList.some((brand) => brand.id === requestedBrandId)) {
        setBrandId(requestedBrandId);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [accessToken, currentAgencyId, requestedBrandId]);

  useEffect(() => {
    if (!accessToken || !currentAgencyId || !brandId) {
      setBrandMembers([]);
      return;
    }

    let cancelled = false;
    void agencyApi
      .listBrandMembers(brandId, currentAgencyId, accessToken)
      .then((members) => {
        if (!cancelled) setBrandMembers(members);
      })
      .catch(() => {
        if (!cancelled) setBrandMembers([]);
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, brandId, currentAgencyId]);

  useEffect(() => {
    if (!requestedTemplateId) {
      setSelectedTemplateId(null);
      setSelectedTemplate(null);
      return;
    }

    setSelectedTemplateId(requestedTemplateId);
    if (!accessToken || !currentAgencyId) return;

    let cancelled = false;
    void templateApi
      .get(requestedTemplateId, currentAgencyId, accessToken)
      .then((template) => {
        if (!cancelled) setSelectedTemplate(template);
      })
      .catch(() => {
        if (cancelled) return;
        setSelectedTemplate(null);
        setSelectedTemplateId(null);
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, currentAgencyId, requestedTemplateId]);

  const assigneeCandidates = useMemo(() => {
    const candidates = new Map<string, AssigneeCandidate>();
    agencyMembers
      .filter((member) => member.status === "active")
      .forEach((member) => {
        candidates.set(member.user_id, {
          userId: member.user_id,
          fullName: member.user_full_name ?? "",
          email: member.user_email ?? "",
          source: "agency",
        });
      });
    brandMembers
      .filter((member) => member.status === "active")
      .forEach((member) => {
        if (candidates.has(member.user_id)) return;
        candidates.set(member.user_id, {
          userId: member.user_id,
          fullName: member.user_full_name ?? "",
          email: member.user_email ?? "",
          source: "brand",
        });
      });
    return Array.from(candidates.values());
  }, [agencyMembers, brandMembers]);

  const platformOptions = PLATFORM_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }));
  const contentTypeOptions = CONTENT_TYPE_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }));

  const dateFields = useMemo(
    () => [
      { key: "startDate" as const, value: startDate, label: t("briefs.new.fields.startDate") },
      { key: "draftDate" as const, value: draftDate, label: t("briefs.new.fields.draftDate") },
      { key: "feedbackDate" as const, value: feedbackDate, label: t("briefs.new.fields.feedbackDate") },
      { key: "deadline" as const, value: deadline, label: t("briefs.new.fields.deadline") },
      { key: "publishDate" as const, value: publishDate, label: t("briefs.new.fields.publishDate") },
    ],
    [deadline, draftDate, feedbackDate, publishDate, startDate, t]
  );

  const dateViolation = useMemo(() => {
    const populated = dateFields.filter((field): field is typeof field & { value: string } => Boolean(field.value));
    for (let index = 0; index < populated.length - 1; index += 1) {
      if (populated[index].value > populated[index + 1].value) {
        return {
          key: populated[index].key,
          message: t("briefs.new.error.dateOrder", {
            earlier: populated[index].label,
            later: populated[index + 1].label,
          }),
        };
      }
    }
    return null;
  }, [dateFields, t]);

  const hasUnsavedChanges = Boolean(
    title.trim() ||
      description.trim() ||
      brandId ||
      selectedTemplateId ||
      priority !== "normal" ||
      startDate ||
      draftDate ||
      feedbackDate ||
      deadline ||
      publishDate ||
      !addToCalendar ||
      platforms.length ||
      contentTypes.length ||
      referenceLinks.length ||
      assigneeIds.length
  );

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges || allowNavigationRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    if (!hasUnsavedChanges) return;

    const handleInternalNavigation = (event: MouseEvent) => {
      if (
        allowNavigationRef.current ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const target = event.target;
      const anchor = target instanceof Element ? target.closest<HTMLAnchorElement>("a[href]") : null;
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return;

      const destination = new URL(anchor.href, window.location.href);
      if (
        destination.origin !== window.location.origin ||
        destination.href === window.location.href ||
        destination.hash && destination.pathname === window.location.pathname && destination.search === window.location.search
      ) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      if (!window.confirm(t("briefs.new.unsaved.confirm"))) return;

      allowNavigationRef.current = true;
      router.push(`${destination.pathname}${destination.search}${destination.hash}`);
    };

    document.addEventListener("click", handleInternalNavigation, true);
    return () => document.removeEventListener("click", handleInternalNavigation, true);
  }, [hasUnsavedChanges, router, t]);

  const formatDate = useCallback(
    (value: string) => {
      return new Intl.DateTimeFormat(intlLocale, { day: "numeric", month: "short", year: "numeric" }).format(
        new Date(`${value}T00:00:00`)
      );
    },
    [intlLocale]
  );

  const selectedBrandName = brands.find((brand) => brand.id === brandId)?.name;
  const selectedPriorityLabel = t(
    PRIORITY_OPTIONS.find((option) => option.value === priority)?.labelKey ?? "briefs.priority.normal"
  );
  const selectedPlatformLabels = platformOptions
    .filter((option) => platforms.includes(option.value))
    .map((option) => option.label);
  const selectedContentTypeLabels = contentTypeOptions
    .filter((option) => contentTypes.includes(option.value))
    .map((option) => option.label);
  const hasSummaryContent = Boolean(
    title.trim() ||
      selectedBrandName ||
      selectedTemplate ||
      platforms.length ||
      contentTypes.length ||
      startDate ||
      draftDate ||
      feedbackDate ||
      deadline ||
      publishDate
  );

  const handleBack = () => {
    if (
      hasUnsavedChanges &&
      !window.confirm(t("briefs.new.unsaved.confirm"))
    ) {
      return;
    }
    allowNavigationRef.current = true;
    router.back();
  };

  const handleCreate = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (creatingRef.current) return;

      if (!accessToken || !currentAgencyId) {
        toast(t("briefs.new.error.noAgency"), "error");
        return;
      }
      if (!title.trim()) {
        setTitleError(true);
        document.getElementById("brief-title")?.focus();
        toast(t("briefs.new.error.titleRequired"), "error");
        return;
      }
      if (dateViolation) {
        dateRefs.current[dateViolation.key]?.focus();
        toast(dateViolation.message, "error");
        return;
      }

      creatingRef.current = true;
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
        allowNavigationRef.current = true;
        router.push(`/dashboard/briefs/${brief.id}`);
      } catch {
        toast(t("briefs.new.error.create"), "error");
        creatingRef.current = false;
        setCreating(false);
      }
    },
    [
      accessToken,
      addToCalendar,
      assigneeIds,
      brandId,
      contentTypes,
      currentAgencyId,
      dateViolation,
      deadline,
      description,
      draftDate,
      feedbackDate,
      platforms,
      priority,
      publishDate,
      referenceLinks,
      router,
      selectedTemplateId,
      startDate,
      t,
      title,
      toast,
    ]
  );

  if (!currentAgencyId) {
    return (
      <main className="mx-auto max-w-[1280px] px-4 py-8 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={() => router.back()}
          className="mb-6 inline-flex items-center gap-2 rounded text-sm text-text-muted outline-none transition-colors hover:text-text focus-visible:ring-2 focus-visible:ring-accent/40"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m15 19-7-7 7-7" />
          </svg>
          {t("briefs.new.back")}
        </button>
        <div className="rounded-2xl border border-border bg-surface px-6 py-12 text-center">
          <h1 className="text-xl font-semibold text-text">{t("briefs.new.noAgency.title")}</h1>
          <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">{t("briefs.new.noAgency.description")}</p>
        </div>
      </main>
    );
  }

  return (
    <div className="bg-background">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto max-w-[1280px] px-4 py-5 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={handleBack}
            className="mb-3 inline-flex items-center gap-2 rounded text-sm text-text-muted outline-none transition-colors hover:text-text focus-visible:ring-2 focus-visible:ring-accent/40"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m15 19-7-7 7-7" />
            </svg>
            {t("briefs.new.back")}
          </button>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-text">{t("briefs.new.title")}</h1>
              <p className="mt-1 text-sm text-text-muted">{t("briefs.new.description")}</p>
            </div>
            {hasUnsavedChanges ? (
              <span className="rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
                {t("briefs.new.unsaved.label")}
              </span>
            ) : null}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6 lg:px-8">
        <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(280px,3fr)] lg:items-start">
          <form
            id="new-brief-form"
            onSubmit={handleCreate}
            className="min-w-0 divide-y divide-border overflow-hidden rounded-2xl border border-border bg-surface shadow-sm"
          >
            <FormSection
              title={t("briefs.new.sections.information.title")}
              description={t("briefs.new.sections.information.description")}
            >
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="brief-title" className="mb-1.5 block text-xs font-medium text-text-muted">
                    {t("briefs.new.fields.name")} <span className="text-danger" aria-hidden="true">*</span>
                  </label>
                  <input
                    id="brief-title"
                    type="text"
                    autoFocus
                    aria-required="true"
                    aria-invalid={titleError}
                    aria-describedby={titleError ? "brief-title-error" : undefined}
                    value={title}
                    onChange={(event) => {
                      setTitle(event.target.value);
                      if (event.target.value.trim()) setTitleError(false);
                    }}
                    placeholder={t("briefs.new.fields.namePlaceholder")}
                    className={cn(inputClassName, titleError && "border-danger focus:border-danger focus:ring-danger/20")}
                  />
                  {titleError ? (
                    <p id="brief-title-error" className="mt-1.5 text-xs text-danger">
                      {t("briefs.new.error.titleRequired")}
                    </p>
                  ) : null}
                </div>

                <div>
                  <label htmlFor="brief-brand" className="mb-1.5 block text-xs font-medium text-text-muted">
                    {t("briefs.new.fields.brand")}
                  </label>
                  <select
                    id="brief-brand"
                    value={brandId}
                    onChange={(event) => {
                      setBrandId(event.target.value);
                      setAssigneeIds((current) =>
                        current.filter((id) => agencyMembers.some((member) => member.user_id === id))
                      );
                    }}
                    className={inputClassName}
                  >
                    <option value="">{t("briefs.new.fields.brandPlaceholder")}</option>
                    {brands.map((brand) => (
                      <option key={brand.id} value={brand.id}>
                        {brand.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <span className="mb-1.5 block text-xs font-medium text-text-muted">
                    {t("briefs.new.fields.template")}
                  </span>
                  <div className="flex min-h-[42px] items-center rounded-lg border border-border bg-surface-2 px-3 text-sm text-text">
                    {selectedTemplate?.name ?? t("briefs.new.summary.notSelected")}
                  </div>
                </div>

                <fieldset>
                  <legend className="mb-1.5 text-xs font-medium text-text-muted">{t("briefs.new.fields.priority")}</legend>
                  <div className="grid grid-cols-2 gap-2">
                    {PRIORITY_OPTIONS.map((option) => {
                      const active = priority === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          aria-pressed={active}
                          onClick={() => setPriority(option.value)}
                          className={cn(
                            "min-h-10 rounded-lg border px-2 py-2 text-xs font-semibold outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent/40",
                            active
                              ? cn(option.color, "border-transparent")
                              : "border-border bg-background text-text-muted hover:border-border-hover hover:text-text"
                          )}
                        >
                          {t(option.labelKey)}
                        </button>
                      );
                    })}
                  </div>
                </fieldset>

                <fieldset className="sm:col-span-2">
                  <legend className="mb-1.5 text-xs font-medium text-text-muted">{t("briefs.new.assignees.label")}</legend>
                  <p className="mb-3 text-xs text-text-muted">{t("briefs.new.assignees.help")}</p>
                  <AssigneePicker candidates={assigneeCandidates} selected={assigneeIds} onChange={setAssigneeIds} />
                </fieldset>
              </div>
            </FormSection>

            <FormSection
              title={t("briefs.new.sections.content.title")}
              description={t("briefs.new.sections.content.description")}
            >
              <div className="space-y-5">
                <div>
                  <label htmlFor="brief-description" className="mb-1.5 block text-xs font-medium text-text-muted">
                    {t("briefs.new.fields.description")}
                  </label>
                  <textarea
                    id="brief-description"
                    rows={5}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder={t("briefs.new.fields.descriptionPlaceholder")}
                    className={cn(inputClassName, "resize-y")}
                  />
                </div>

                <fieldset>
                  <legend className="mb-2 text-xs font-medium text-text-muted">{t("briefs.new.fields.platforms")}</legend>
                  <MultiSelectChips options={platformOptions} selected={platforms} onChange={setPlatforms} />
                </fieldset>

                <fieldset>
                  <legend className="mb-2 text-xs font-medium text-text-muted">{t("briefs.new.fields.contentTypes")}</legend>
                  <MultiSelectChips options={contentTypeOptions} selected={contentTypes} onChange={setContentTypes} />
                </fieldset>
              </div>
            </FormSection>

            <FormSection
              title={t("briefs.new.sections.planning.title")}
              description={t("briefs.new.sections.planning.description")}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                {dateFields.map((field) => {
                  const setters: Record<DateFieldKey, (value: string | null) => void> = {
                    startDate: setStartDate,
                    draftDate: setDraftDate,
                    feedbackDate: setFeedbackDate,
                    deadline: setDeadline,
                    publishDate: setPublishDate,
                  };
                  const invalid = dateViolation?.key === field.key;
                  return (
                    <div key={field.key} className={cn("min-w-0", field.key === "publishDate" && "sm:col-span-2")}>
                      <label htmlFor={`brief-${field.key}`} className="mb-1.5 block text-xs font-medium text-text-muted">
                        {field.label}
                      </label>
                      <input
                        ref={(element) => {
                          dateRefs.current[field.key] = element;
                        }}
                        id={`brief-${field.key}`}
                        type="date"
                        value={field.value ?? ""}
                        onChange={(event) => setters[field.key](event.target.value || null)}
                        aria-invalid={invalid}
                        aria-describedby={invalid ? "brief-date-error" : undefined}
                        className={cn(inputClassName, invalid && "border-danger focus:border-danger focus:ring-danger/20")}
                      />
                    </div>
                  );
                })}
              </div>

              {dateViolation ? (
                <p id="brief-date-error" role="alert" className="mt-3 text-xs text-danger">
                  {dateViolation.message}
                </p>
              ) : null}

              <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-lg bg-surface-2 px-3 py-3">
                <input
                  type="checkbox"
                  checked={addToCalendar}
                  onChange={(event) => setAddToCalendar(event.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-border text-accent focus:ring-accent/40"
                />
                <span>
                  <span className="block text-sm font-medium text-text">{t("briefs.new.fields.addToCalendar")}</span>
                  <span className="mt-0.5 block text-xs text-text-muted">{t("briefs.new.fields.addToCalendarHelp")}</span>
                </span>
              </label>
            </FormSection>

            <FormSection
              title={t("briefs.new.sections.references.title")}
              description={t("briefs.new.sections.references.description")}
            >
              <label htmlFor="reference-link" className="mb-1.5 block text-xs font-medium text-text-muted">
                {t("briefs.new.references.label")}
              </label>
              <ReferenceLinksEditor links={referenceLinks} onChange={setReferenceLinks} />
              <div className="mt-5 border-l-2 border-border pl-3">
                <p className="text-xs font-medium text-text">{t("briefs.new.references.internalNotesTitle")}</p>
                <p className="mt-1 text-xs leading-5 text-text-muted">
                  {t("briefs.new.references.internalNoteGuidance")}
                </p>
              </div>
            </FormSection>
          </form>

          <aside className="min-w-0 self-start rounded-2xl border border-border bg-surface p-5 shadow-sm lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto">
            <div className="mb-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                {t("briefs.new.summary.eyebrow")}
              </p>
              <h2 className="mt-1 text-base font-semibold text-text">{t("briefs.new.summary.title")}</h2>
            </div>

            {hasSummaryContent ? (
              <dl>
                {title.trim() ? <SummaryRow label={t("briefs.new.summary.name")} value={title.trim()} /> : null}
                {selectedBrandName ? <SummaryRow label={t("briefs.new.summary.brand")} value={selectedBrandName} /> : null}
                {selectedTemplate ? <SummaryRow label={t("briefs.new.summary.template")} value={selectedTemplate.name} /> : null}
                <SummaryRow label={t("briefs.new.summary.priority")} value={selectedPriorityLabel} />
                {platforms.length > 0 ? (
                  <SummaryRow
                    label={t("briefs.new.summary.platforms")}
                    value={t("briefs.new.summary.platformSelection", {
                      count: platforms.length,
                      names: selectedPlatformLabels.join(", "),
                    })}
                  />
                ) : null}
                {contentTypes.length > 0 ? (
                  <SummaryRow label={t("briefs.new.summary.contentTypes")} value={selectedContentTypeLabels.join(", ")} />
                ) : null}
                {deadline ? <SummaryRow label={t("briefs.new.summary.deadline")} value={formatDate(deadline)} /> : null}
                {startDate ? <SummaryRow label={t("briefs.new.summary.startDate")} value={formatDate(startDate)} /> : null}
                {draftDate ? <SummaryRow label={t("briefs.new.summary.draftDate")} value={formatDate(draftDate)} /> : null}
                {feedbackDate ? (
                  <SummaryRow label={t("briefs.new.summary.feedbackDate")} value={formatDate(feedbackDate)} />
                ) : null}
                {publishDate ? <SummaryRow label={t("briefs.new.summary.publishDate")} value={formatDate(publishDate)} /> : null}
                <SummaryRow
                  label={t("briefs.new.summary.calendar")}
                  value={addToCalendar ? t("briefs.new.summary.calendarYes") : t("briefs.new.summary.calendarNo")}
                />
              </dl>
            ) : (
              <div className="rounded-xl bg-surface-2 px-4 py-8 text-center">
                <p className="text-sm font-medium text-text">{t("briefs.new.summary.emptyTitle")}</p>
                <p className="mt-1 text-xs leading-5 text-text-muted">{t("briefs.new.summary.emptyDescription")}</p>
              </div>
            )}

            <button
              type="submit"
              form="new-brief-form"
              disabled={creating}
              aria-busy={creating}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white outline-none transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
            >
              {creating ? (
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4Z" />
                </svg>
              ) : null}
              {creating ? t("briefs.new.actions.creating") : t("briefs.new.actions.create")}
            </button>
            <p className="mt-2 text-center text-xs text-text-muted">{t("briefs.new.actions.createHelp")}</p>
          </aside>
        </div>
      </main>
    </div>
  );
}
