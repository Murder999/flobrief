"use client";

import Link from "next/link";
import {
  ArrowRight,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  Clock3,
  FileText,
  FolderOpen,
  History,
  LayoutDashboard,
  MessageSquareText,
  Palette,
  Send,
  Sparkles,
  Users,
} from "lucide-react";
import type { ComponentType, SVGProps } from "react";

import { PublicFooter } from "./PublicFooter";
import { PublicHeader } from "./PublicHeader";
import { LandingTitleSync } from "./LandingTitleSync";
import { SEO_LANDING_PAGES, type LandingFeature, type LandingPageConfig, type LandingSlug } from "./seo-landing-data";
import { SEO_LANDING_PAGES_EN } from "./seo-landing-data-en";
import { useLocale } from "@/context/locale-context";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

const iconMap: Record<LandingFeature["icon"], IconComponent> = {
  brief: FileText,
  message: MessageSquareText,
  check: CheckCircle2,
  history: History,
  portal: LayoutDashboard,
  file: FolderOpen,
  palette: Palette,
  users: Users,
};

const toneClasses: Record<LandingPageConfig["tone"], { soft: string; text: string; border: string; dot: string }> = {
  indigo: { soft: "bg-accent-subtle", text: "text-accent", border: "border-accent/20", dot: "bg-accent" },
  emerald: { soft: "bg-success-subtle", text: "text-success", border: "border-success/20", dot: "bg-success" },
  amber: { soft: "bg-warning-subtle", text: "text-warning", border: "border-warning/20", dot: "bg-warning" },
  violet: { soft: "bg-purple-subtle", text: "text-purple", border: "border-purple/20", dot: "bg-purple" },
  blue: { soft: "bg-info-subtle", text: "text-info", border: "border-info/20", dot: "bg-info" },
};

const relatedLabels: Record<LandingSlug, string> = {
  "ajans-programi": "Ajans programı",
  "musteri-onay-sistemi": "Müşteri onay sistemi",
  "revizyon-takip": "Revizyon takibi",
  "musteri-portali": "Müşteri portalı",
  "online-brief": "Online brief",
};

const relatedLabelsEn: Record<LandingSlug, string> = {
  "ajans-programi": "Agency management software",
  "musteri-onay-sistemi": "Client approval software",
  "revizyon-takip": "Creative proofing software",
  "musteri-portali": "Client portal software",
  "online-brief": "Online creative briefs",
};

function AgencyVisual() {
  const steps = ["Müşteri", "Brief", "İş", "Revizyon", "Onay", "Teslim"];
  return (
    <div className="rounded-3xl border border-border bg-surface p-4 shadow-xl sm:p-6" aria-label="Ajans iş akışı ürün görünümü">
      <div className="mb-5 flex items-center justify-between border-b border-border pb-4">
        <div>
          <p className="text-xs font-semibold text-text">Kampanya operasyonu</p>
          <p className="mt-1 text-[11px] text-text-muted">Ajans ve müşteri aynı akışta</p>
        </div>
        <span className="rounded-full bg-accent-subtle px-2.5 py-1 text-[10px] font-semibold text-accent">Aktif iş</span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {steps.map((step, index) => (
          <div key={step} className="rounded-xl border border-border bg-surface-2/70 p-3">
            <div className="mb-3 flex items-center justify-between">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-surface text-[10px] font-bold text-accent shadow-xs">{index + 1}</span>
              {index < 4 ? <span className="h-1.5 w-1.5 rounded-full bg-warning" /> : <Check className="h-3.5 w-3.5 text-success" />}
            </div>
            <p className="text-xs font-semibold text-text">{step}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ApprovalVisual() {
  return (
    <div className="mx-auto max-w-3xl rounded-3xl border border-border bg-surface p-3 shadow-xl sm:p-5" aria-label="Müşteri onay çalışma alanı ürün görünümü">
      <div className="grid gap-3 md:grid-cols-[1.4fr_0.75fr]">
        <div className="rounded-2xl border border-border bg-surface-2/60 p-4">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-accent text-xs font-bold text-white">P</span>
              <div><p className="text-xs font-semibold text-text">Kampanya teslimi</p><p className="text-[10px] text-text-muted">Teslim · v2</p></div>
            </div>
            <span className="rounded-full bg-warning-subtle px-2 py-1 text-[10px] font-semibold text-warning">İncelemede</span>
          </div>
          <div className="flex aspect-[16/9] items-center justify-center rounded-xl border border-border bg-background">
            <div className="text-center"><Sparkles className="mx-auto mb-2 h-7 w-7 text-accent" /><p className="text-xs font-semibold text-text">Tasarım önizlemesi</p><p className="mt-1 text-[10px] text-text-muted">İlgili teslim bağlamında</p></div>
          </div>
        </div>
        <div className="flex flex-col rounded-2xl border border-border p-4">
          <p className="mb-3 text-xs font-semibold text-text">Geri bildirim</p>
          <div className="rounded-xl bg-surface-2 p-3 text-[11px] leading-relaxed text-text-secondary">Başlıktaki hizalamayı güncelleyebilir miyiz?</div>
          <div className="mt-auto grid gap-2 pt-5">
            <div className="flex min-h-10 items-center justify-center rounded-xl border border-warning/25 bg-warning-subtle text-xs font-semibold text-warning">Revizyon İste</div>
            <div className="flex min-h-10 items-center justify-center rounded-xl bg-success text-xs font-semibold text-white">Onayla</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RevisionVisual() {
  const versions = [
    { version: "v1", note: "İlk teslim", state: "Tamamlandı", tone: "bg-surface-3" },
    { version: "v2", note: "Revizyon uygulandı", state: "Geri bildirim", tone: "bg-warning" },
    { version: "v3", note: "Güncel teslim", state: "Onaylandı", tone: "bg-success" },
  ];
  return (
    <div className="rounded-3xl border border-border bg-surface p-5 shadow-xl sm:p-6" aria-label="Revizyon geçmişi ürün görünümü">
      <div className="mb-5 flex items-center justify-between">
        <div><p className="text-xs font-semibold text-text">Teslim geçmişi</p><p className="mt-1 text-[10px] text-text-muted">Sürümler ve geri bildirimler</p></div>
        <History className="h-5 w-5 text-warning" />
      </div>
      <div className="space-y-3">
        {versions.map((item, index) => (
          <div key={item.version} className="relative flex items-center gap-3 rounded-2xl border border-border bg-surface-2/50 p-3.5">
            {index < versions.length - 1 && <span className="absolute left-[29px] top-12 h-6 w-px bg-border-strong" />}
            <span className={`flex h-9 w-9 items-center justify-center rounded-xl text-[11px] font-bold text-white ${item.tone}`}>{item.version}</span>
            <div className="min-w-0 flex-1"><p className="text-xs font-semibold text-text">{item.note}</p><p className="mt-0.5 text-[10px] text-text-muted">İlgili yorumlar bu sürümle birlikte</p></div>
            <span className="text-[10px] font-medium text-text-secondary">{item.state}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PortalVisual() {
  return (
    <div className="rounded-3xl border border-border bg-surface p-3 shadow-xl sm:p-5" aria-label="Müşteri portalı ürün görünümü">
      <div className="rounded-2xl border border-border bg-background p-4">
        <div className="mb-5 flex items-center justify-between border-b border-border pb-4">
          <div className="flex items-center gap-2.5"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple text-xs font-black text-white">A</span><div><p className="text-xs font-semibold text-text">Ajans müşteri alanı</p><p className="text-[10px] text-text-muted">Marka çalışma alanı</p></div></div>
          <span className="rounded-full bg-success-subtle px-2 py-1 text-[10px] font-semibold text-success">Müşteri görünümü</span>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[{ label: "Briefler", value: "Güncel", icon: FileText }, { label: "İşler", value: "Takipte", icon: BriefcaseBusiness }, { label: "Onaylar", value: "Bekliyor", icon: CheckCircle2 }, { label: "Dosyalar", value: "Paylaşıldı", icon: FolderOpen }].map(({ label, value, icon: Icon }) => (
            <div key={label} className="rounded-xl border border-border bg-surface p-3"><Icon className="mb-4 h-4 w-4 text-purple" /><p className="text-[10px] text-text-muted">{label}</p><p className="mt-1 text-xs font-semibold text-text">{value}</p></div>
          ))}
        </div>
        <div className="mt-3 rounded-xl border border-border bg-surface p-3.5">
          <div className="flex items-center justify-between"><div><p className="text-xs font-semibold text-text">Yaz kampanyası</p><p className="mt-1 text-[10px] text-text-muted">Güncel teslim müşteri incelemesinde</p></div><span className="rounded-full bg-warning-subtle px-2 py-1 text-[10px] font-medium text-warning">Aksiyon gerekli</span></div>
        </div>
      </div>
    </div>
  );
}

function BriefVisual() {
  return (
    <div className="mx-auto max-w-3xl rounded-3xl border border-border bg-surface p-4 shadow-xl sm:p-6" aria-label="Online brief formu ürün görünümü">
      <div className="mb-5 flex items-center justify-between"><div><p className="text-xs font-semibold text-text">Kampanya briefi</p><p className="mt-1 text-[10px] text-text-muted">Müşteri brief formu</p></div><span className="rounded-full bg-info-subtle px-2.5 py-1 text-[10px] font-semibold text-info">Taslak</span></div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface-2/60 p-3"><p className="mb-2 text-[10px] font-medium text-text-secondary">Kampanyanın amacı</p><div className="h-8 rounded-lg border border-border bg-surface" /></div>
        <div className="rounded-xl border border-border bg-surface-2/60 p-3"><p className="mb-2 text-[10px] font-medium text-text-secondary">Teslim tarihi</p><div className="h-8 rounded-lg border border-border bg-surface" /></div>
        <div className="rounded-xl border border-border bg-surface-2/60 p-3 sm:col-span-2"><p className="mb-2 text-[10px] font-medium text-text-secondary">Hedef kitle ve temel mesaj</p><div className="h-16 rounded-lg border border-border bg-surface" /></div>
        <div className="flex items-center gap-3 rounded-xl border border-dashed border-info/30 bg-info-subtle p-3 sm:col-span-2"><FolderOpen className="h-4 w-4 text-info" /><div><p className="text-[10px] font-semibold text-text">Destekleyici dosyalar</p><p className="text-[10px] text-text-muted">Brief kaydıyla birlikte</p></div></div>
      </div>
    </div>
  );
}

function EnglishProductVisual() {
  return <div className="rounded-3xl border border-border bg-surface p-5 shadow-xl sm:p-7" aria-label="PostPiloter creative workflow preview"><div className="mb-5 flex items-center justify-between"><div><p className="text-xs font-semibold text-text">Summer campaign</p><p className="mt-1 text-[10px] text-text-muted">Client and agency workspace</p></div><span className="rounded-full bg-warning-subtle px-2.5 py-1 text-[10px] font-semibold text-warning">In review</span></div><div className="grid gap-3 sm:grid-cols-2">{["Creative brief", "Deliverable review", "Client feedback", "Final approval"].map((label, index) => <div key={label} className="rounded-xl border border-border bg-background p-4"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-subtle text-[10px] font-bold text-accent">{index + 1}</span><p className="mt-3 text-xs font-semibold text-text">{label}</p></div>)}</div></div>;
}

function ProductVisual({ type, locale }: { type: LandingPageConfig["visual"]; locale: "en" | "tr" }) {
  if (locale === "en") return <EnglishProductVisual />;
  if (type === "approval") return <ApprovalVisual />;
  if (type === "revision") return <RevisionVisual />;
  if (type === "portal") return <PortalVisual />;
  if (type === "brief") return <BriefVisual />;
  return <AgencyVisual />;
}

function ProblemSection({ config, locale }: { config: LandingPageConfig; locale: "en" | "tr" }) {
  const tone = toneClasses[config.tone];
  return (
    <section className="border-y border-border bg-surface py-20 sm:py-24" aria-labelledby={`${config.slug}-problem-title`}>
      <div className="mx-auto grid max-w-7xl gap-10 px-6 lg:grid-cols-2 lg:gap-16">
        <div>
          <p className={`mb-3 text-xs font-bold uppercase tracking-[0.16em] ${tone.text}`}>{config.problem.eyebrow}</p>
          <h2 id={`${config.slug}-problem-title`} className="max-w-xl text-3xl font-black leading-tight tracking-tight text-text sm:text-4xl">{config.problem.title}</h2>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-text-secondary">{config.problem.description}</p>
          <ul className="mt-7 space-y-3">
            {config.problem.points.map((point) => (
              <li key={point} className="flex items-start gap-3 text-sm text-text-secondary"><span className={`mt-1.5 h-2 w-2 flex-none rounded-full ${tone.dot}`} /><span>{point}</span></li>
            ))}
          </ul>
        </div>
        <div className={`rounded-3xl border p-7 sm:p-9 ${tone.border} ${tone.soft}`}>
          <p className={`mb-3 text-xs font-bold uppercase tracking-[0.16em] ${tone.text}`}>{config.solution.eyebrow}</p>
          <h3 className="text-2xl font-bold leading-tight tracking-tight text-text sm:text-3xl">{config.solution.title}</h3>
          <p className="mt-5 text-base leading-relaxed text-text-secondary">{config.solution.description}</p>
          <Link href="/demo" className={`mt-7 inline-flex min-h-11 items-center gap-2 rounded-xl border bg-surface px-4 text-sm font-semibold ${tone.border} ${tone.text}`}>
            {locale === "tr" ? "Ürün akışını incele" : "Explore the workflow"} <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}

function WorkflowSection({ config, locale }: { config: LandingPageConfig; locale: "en" | "tr" }) {
  const tone = toneClasses[config.tone];
  return (
    <section className="py-20 sm:py-24" aria-labelledby={`${config.slug}-workflow-title`}>
      <div className="mx-auto max-w-7xl px-6">
        <div className={config.hero === "centered" ? "mx-auto max-w-3xl text-center" : "max-w-3xl"}>
          <p className={`mb-3 text-xs font-bold uppercase tracking-[0.16em] ${tone.text}`}>{locale === "tr" ? "Süreç" : "Workflow"}</p>
          <h2 id={`${config.slug}-workflow-title`} className="text-3xl font-black tracking-tight text-text sm:text-4xl">{config.workflow.title}</h2>
          <p className="mt-4 text-base leading-relaxed text-text-secondary">{config.workflow.description}</p>
        </div>
        <ol className={`mt-10 grid gap-3 ${config.workflow.steps.length >= 6 ? "md:grid-cols-3 lg:grid-cols-6" : "md:grid-cols-3 lg:grid-cols-5"}`}>
          {config.workflow.steps.map((step, index) => (
            <li key={step} className="group relative rounded-2xl border border-border bg-surface p-5 shadow-card">
              <div className="mb-5 flex items-center justify-between"><span className={`flex h-8 w-8 items-center justify-center rounded-xl text-xs font-bold ${tone.soft} ${tone.text}`}>{index + 1}</span>{index < config.workflow.steps.length - 1 && <ArrowRight className="hidden h-4 w-4 text-text-muted/40 lg:block" />}</div>
              <p className="text-sm font-semibold leading-snug text-text">{step}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function FeaturesSection({ config, locale }: { config: LandingPageConfig; locale: "en" | "tr" }) {
  const tone = toneClasses[config.tone];
  return (
    <section className="border-y border-border bg-surface py-20 sm:py-24" aria-labelledby={`${config.slug}-features-title`}>
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center"><p className={`mb-3 text-xs font-bold uppercase tracking-[0.16em] ${tone.text}`}>{locale === "tr" ? "İlgili ürün özellikleri" : "Product capabilities"}</p><h2 id={`${config.slug}-features-title`} className="text-3xl font-black tracking-tight text-text sm:text-4xl">{locale === "tr" ? "Bu akışı destekleyen gerçek PostPiloter özellikleri" : "The tools behind a clearer creative workflow"}</h2></div>
        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {config.features.map((feature) => {
            const Icon = iconMap[feature.icon];
            return <article key={feature.title} className="rounded-2xl border border-border bg-background p-6 shadow-card sm:p-7"><span className={`mb-5 flex h-11 w-11 items-center justify-center rounded-2xl ${tone.soft}`}><Icon className={`h-5 w-5 ${tone.text}`} /></span><h3 className="text-lg font-bold text-text">{feature.title}</h3><p className="mt-2 text-sm leading-relaxed text-text-secondary">{feature.description}</p></article>;
          })}
        </div>
      </div>
    </section>
  );
}

function ScenarioSection({ config, locale }: { config: LandingPageConfig; locale: "en" | "tr" }) {
  const tone = toneClasses[config.tone];
  return (
    <section className="py-20 sm:py-24" aria-labelledby={`${config.slug}-scenario-title`}>
      <div className="mx-auto max-w-6xl px-6">
        <div className="overflow-hidden rounded-3xl border border-border bg-surface shadow-lg">
          <div className="grid lg:grid-cols-[1.1fr_0.9fr]">
            <div className="p-7 sm:p-10"><p className={`mb-3 text-xs font-bold uppercase tracking-[0.16em] ${tone.text}`}>{locale === "tr" ? "Kullanım senaryosu" : "In practice"}</p><h2 id={`${config.slug}-scenario-title`} className="text-3xl font-black leading-tight tracking-tight text-text">{config.scenario.title}</h2><p className="mt-5 text-base leading-relaxed text-text-secondary">{config.scenario.description}</p></div>
            <div className={`grid gap-3 border-t p-6 lg:border-l lg:border-t-0 ${tone.border} ${tone.soft}`}>
              <div className="rounded-2xl border border-border bg-surface p-5"><div className="mb-3 flex items-center gap-2 text-xs font-bold text-text"><Users className={`h-4 w-4 ${tone.text}`} />{locale === "tr" ? "Ajans tarafı" : "Agency view"}</div><p className="text-sm leading-relaxed text-text-secondary">{config.scenario.agency}</p></div>
              <div className="rounded-2xl border border-border bg-surface p-5"><div className="mb-3 flex items-center gap-2 text-xs font-bold text-text"><BriefcaseBusiness className={`h-4 w-4 ${tone.text}`} />{locale === "tr" ? "Müşteri tarafı" : "Client view"}</div><p className="text-sm leading-relaxed text-text-secondary">{config.scenario.customer}</p></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function SeoLandingPage({ config }: { config: LandingPageConfig }) {
  const { locale } = useLocale();
  config = locale === "en" ? SEO_LANDING_PAGES_EN[config.slug] : config;
  const tone = toneClasses[config.tone];
  const sections = {
    problem: <ProblemSection key="problem" config={config} locale={locale} />,
    workflow: <WorkflowSection key="workflow" config={config} locale={locale} />,
    features: <FeaturesSection key="features" config={config} locale={locale} />,
    scenario: <ScenarioSection key="scenario" config={config} locale={locale} />,
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-background">
      <LandingTitleSync title={config.title} />
      <PublicHeader />
      <main id="main-content">
        <section className="relative overflow-hidden pb-16 pt-32 sm:pb-20 sm:pt-36">
          <div className="hero-grid absolute inset-0 opacity-40" />
          <div className="pointer-events-none absolute left-1/2 top-0 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-accent-subtle blur-[120px]" />
          <div className={`relative mx-auto max-w-7xl px-6 ${config.hero === "centered" ? "text-center" : "grid items-center gap-12 lg:grid-cols-[1.02fr_0.98fr]"}`}>
            <div className={config.hero === "centered" ? "mx-auto max-w-4xl" : ""}>
              <div className={`mb-6 inline-flex items-center gap-2 rounded-full border bg-surface px-3.5 py-1.5 shadow-xs ${tone.border}`}><span className={`h-2 w-2 rounded-full ${tone.dot}`} /><span className={`text-xs font-semibold ${tone.text}`}>{config.badge}</span></div>
              <h1 className="text-balance text-4xl font-black leading-[1.05] tracking-[-0.045em] text-text sm:text-5xl lg:text-6xl">{config.h1}</h1>
              <p className={`mt-6 text-lg leading-relaxed text-text-secondary ${config.hero === "centered" ? "mx-auto max-w-2xl" : "max-w-xl"}`}>{config.description}</p>
              <div className={`mt-8 flex flex-col gap-3 sm:flex-row ${config.hero === "centered" ? "sm:justify-center" : ""}`}>
                <Link href="/demo" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-gradient-accent px-6 text-sm font-bold text-white shadow-accent transition-transform hover:scale-[1.02]">{locale === "tr" ? "Demoyu İncele" : "Explore the demo"} <ArrowRight className="h-4 w-4" /></Link>
                <Link href="/auth/register" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-border bg-surface px-6 text-sm font-semibold text-text hover:border-border-hover">{locale === "tr" ? "Hesap Oluştur" : "Create an account"}</Link>
              </div>
              <div className={`mt-7 flex flex-wrap gap-x-5 gap-y-2 ${config.hero === "centered" ? "justify-center" : ""}`}>
                {config.proof.map((item) => <span key={item} className="inline-flex items-center gap-1.5 text-xs text-text-muted"><CheckCircle2 className="h-3.5 w-3.5 text-success" />{item}</span>)}
              </div>
            </div>
            {config.hero === "split" && <div className="relative"><ProductVisual type={config.visual} locale={locale} /></div>}
          </div>
          {config.hero === "centered" && <div className="relative mx-auto mt-12 max-w-5xl px-6"><ProductVisual type={config.visual} locale={locale} /></div>}
        </section>

        {config.sectionOrder.map((key) => sections[key])}

        <section className="border-y border-border bg-surface py-16" aria-labelledby={`${config.slug}-related-title`}>
          <div className="mx-auto max-w-7xl px-6"><h2 id={`${config.slug}-related-title`} className="text-xl font-bold text-text">{locale === "tr" ? "İlgili çözümler" : "Related solutions"}</h2><div className="mt-5 flex flex-wrap gap-3">{config.related.map((slug) => <Link key={slug} href={`${locale === "tr" ? "/tr" : ""}/${slug}`} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-border bg-background px-4 text-sm font-semibold text-text-secondary transition-colors hover:border-border-hover hover:text-text">{locale === "tr" ? relatedLabels[slug] : relatedLabelsEn[slug]} <ArrowRight className="h-3.5 w-3.5" /></Link>)}</div></div>
        </section>

        <section className="relative overflow-hidden py-20 sm:py-24">
          <div className="hero-grid absolute inset-0 opacity-20" />
          <div className="relative mx-auto max-w-5xl px-6">
            <div className="overflow-hidden rounded-3xl border border-border bg-surface p-8 text-center shadow-xl sm:p-12"><div className={`mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl ${tone.soft}`}><Send className={`h-5 w-5 ${tone.text}`} /></div><h2 className="text-3xl font-black tracking-tight text-text sm:text-4xl">{locale === "tr" ? "Ajans–müşteri sürecinizi tek çalışma alanında görün" : "See your agency–client workflow in one workspace"}</h2><p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-text-secondary">{locale === "tr" ? "PostPiloter’ın gerçek brief, iş, yorum, revizyon ve onay akışını demo ortamında inceleyin." : "Explore PostPiloter’s brief, feedback, revision, and approval workflow in a demo workspace."}</p><div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row"><Link href="/demo" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-gradient-accent px-6 text-sm font-bold text-white shadow-accent">{locale === "tr" ? "Demoyu İncele" : "Explore the demo"} <ArrowRight className="h-4 w-4" /></Link><Link href={locale === "tr" ? "/tr/pricing" : "/pricing"} className="inline-flex min-h-12 items-center justify-center rounded-xl border border-border bg-background px-6 text-sm font-semibold text-text">{locale === "tr" ? "Fiyatlandırmayı Gör" : "View pricing"}</Link></div></div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}

export function getLandingPageConfig(slug: LandingSlug): LandingPageConfig {
  return SEO_LANDING_PAGES[slug];
}
