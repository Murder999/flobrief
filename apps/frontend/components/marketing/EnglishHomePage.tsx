"use client";

import Link from "next/link";
import { ArrowRight, CalendarDays, CheckCircle2, FileText, MessageSquareText, PanelsTopLeft, Sparkles } from "lucide-react";
import { useLocale } from "@/context/locale-context";
import { PublicHeader } from "./PublicHeader";
import { PublicFooter } from "./PublicFooter";

export function EnglishHomePage() {
  const { t } = useLocale();
  const features = [
    { id: "brief", icon: FileText, title: t("marketing.home.feature.brief.title"), description: t("marketing.home.feature.brief.description") },
    { id: "feedback", icon: MessageSquareText, title: t("marketing.home.feature.feedback.title"), description: t("marketing.home.feature.feedback.description") },
    { id: "approval", icon: CheckCircle2, title: t("marketing.home.feature.approval.title"), description: t("marketing.home.feature.approval.description") },
    { id: "calendar", icon: CalendarDays, title: t("marketing.home.feature.calendar.title"), description: t("marketing.home.feature.calendar.description") },
    { id: "portal", icon: PanelsTopLeft, title: t("marketing.home.feature.portal.title"), description: t("marketing.home.feature.portal.description") },
    { id: "brand", icon: Sparkles, title: t("marketing.home.feature.brand.title"), description: t("marketing.home.feature.brand.description") },
  ];
  const workflowSteps = [
    t("marketing.home.workflow.step1"),
    t("marketing.home.workflow.step2"),
    t("marketing.home.workflow.step3"),
    t("marketing.home.workflow.step4"),
  ];

  return (
    <div className="min-h-screen overflow-x-hidden bg-background">
      <PublicHeader />
      <main id="main-content">
        <section className="relative overflow-hidden px-6 pb-20 pt-36 sm:pt-44">
          <div className="hero-grid absolute inset-0 opacity-50" />
          <div className="absolute left-1/2 top-20 h-[520px] w-[760px] -translate-x-1/2 rounded-full bg-accent/10 blur-[130px]" />
          <div className="relative mx-auto max-w-5xl text-center">
            <p className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent-subtle px-4 py-2 text-xs font-semibold text-accent">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              {t("marketing.home.eyebrow")}
            </p>
            <h1 className="text-display text-text">{t("marketing.home.title")}</h1>
            <p className="mx-auto mt-7 max-w-2xl text-lg leading-8 text-text-secondary">
              {t("marketing.home.description")}
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link href="/demo" className="inline-flex min-h-12 items-center gap-2 rounded-xl bg-gradient-accent px-7 text-sm font-semibold text-white shadow-accent transition-transform hover:scale-[1.02]">
                {t("marketing.home.primaryCta")} <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/auth/register" className="inline-flex min-h-12 items-center rounded-xl border border-border bg-surface px-7 text-sm font-semibold text-text transition-colors hover:border-border-hover">
                {t("marketing.home.secondaryCta")}
              </Link>
            </div>
          </div>
        </section>

        <section id="features" className="border-y border-border bg-surface px-6 py-24">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-2xl">
              <p className="text-label-sm text-accent">{t("marketing.home.features.eyebrow")}</p>
              <h2 className="mt-3 text-heading-xl text-text">{t("marketing.home.features.title")}</h2>
              <p className="mt-4 text-base leading-7 text-text-secondary">{t("marketing.home.features.description")}</p>
            </div>
            <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {features.map(({ id, icon: Icon, title, description }) => (
                <article key={id} className="rounded-2xl border border-border bg-background p-6 shadow-card">
                  <span className="mb-5 flex h-10 w-10 items-center justify-center rounded-xl bg-accent-subtle text-accent"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                  <h3 className="text-base font-semibold text-text">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-text-muted">{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" className="px-6 py-24">
          <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <div>
              <p className="text-label-sm text-accent">{t("marketing.home.workflow.eyebrow")}</p>
              <h2 className="mt-3 text-heading-xl text-text">{t("marketing.home.workflow.title")}</h2>
              <p className="mt-4 text-base leading-7 text-text-secondary">{t("marketing.home.workflow.description")}</p>
            </div>
            <ol className="grid gap-3 sm:grid-cols-2">
              {workflowSteps.map((step, index) => (
                <li key={step} className="flex items-center gap-4 rounded-2xl border border-border bg-surface p-5">
                  <span className="flex h-9 w-9 flex-none items-center justify-center rounded-xl bg-accent-subtle text-sm font-bold text-accent">{index + 1}</span>
                  <span className="text-sm font-semibold text-text">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="px-6 pb-24">
          <div className="mx-auto max-w-5xl rounded-3xl border border-accent/20 bg-gradient-to-br from-accent-subtle to-surface p-10 text-center shadow-xl sm:p-16">
            <h2 className="text-heading-lg text-text">{t("marketing.home.cta.title")}</h2>
            <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-text-secondary">{t("marketing.home.cta.description")}</p>
            <Link href="/demo" className="mt-8 inline-flex min-h-12 items-center gap-2 rounded-xl bg-gradient-accent px-7 text-sm font-semibold text-white shadow-accent">{t("marketing.home.primaryCta")} <ArrowRight className="h-4 w-4" /></Link>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}
