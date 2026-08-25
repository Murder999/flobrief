"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { LoginModal } from "@/components/auth/LoginModal";
import { PostPiloterLogo } from "@/components/brand/PostPiloterLogo";
import { useLocale } from "@/context/locale-context";
import { localizePublicPath } from "@/lib/i18n/config";

export function PublicFooter() {
  const { locale, t } = useLocale();
  const [loginOpen, setLoginOpen] = useState(false);
  const localize = (path: string) => localizePublicPath(path, locale);
  const solutionLinks = [
    { label: t("marketing.solution.agency"), href: localize("/ajans-programi") },
    { label: t("marketing.solution.approval"), href: localize("/musteri-onay-sistemi") },
    { label: t("marketing.solution.revision"), href: localize("/revizyon-takip") },
    { label: t("marketing.solution.portal"), href: localize("/musteri-portali") },
    { label: t("marketing.solution.brief"), href: localize("/online-brief") },
  ];
  const legalLinks = [
    { label: t("marketing.legal.nav.terms"), href: localize("/terms") },
    { label: t("marketing.legal.nav.privacy"), href: localize("/privacy") },
    { label: t("marketing.legal.nav.refund"), href: localize("/refund-policy") },
    { label: t("marketing.legal.nav.contact"), href: localize("/contact") },
  ];

  return (
    <>
      <footer className="border-t border-border bg-background" data-testid="public-footer">
        <div className="mx-auto grid max-w-7xl gap-x-8 gap-y-10 px-6 py-14 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Link href={localize("/")} className="group mb-4 inline-flex items-center gap-2.5">
              <PostPiloterLogo className="h-8 w-auto transition-transform group-hover:scale-[1.02]" />
            </Link>
            <p className="mb-6 max-w-sm text-sm leading-relaxed text-text-muted">
              {t("marketing.footer.description")}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href={localize("/demo")} className="inline-flex min-h-11 items-center gap-1.5 rounded-xl bg-gradient-accent px-4 text-xs font-semibold text-white">
                {t("marketing.actions.demo")}
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
              <Link href={localize("/auth/register")} className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-xs font-semibold text-text-secondary hover:border-border-hover hover:text-text">
                {t("auth.actions.register")}
              </Link>
            </div>
          </div>

          <div>
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-text">{t("marketing.footer.solutions")}</h2>
          <ul className="space-y-3">
            {solutionLinks.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="text-sm text-text-muted transition-colors hover:text-text">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
          </div>

          <div>
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-text">{t("marketing.footer.getStarted")}</h2>
          <ul className="space-y-3">
            <li><Link href={localize("/pricing")} className="text-sm text-text-muted hover:text-text">{t("common.navigation.pricing")}</Link></li>
            <li><Link href={localize("/auth/register")} className="text-sm text-text-muted hover:text-text">{t("marketing.actions.freeSignup")}</Link></li>
            <li>
              <button
                type="button"
                aria-haspopup="dialog"
                onClick={() => setLoginOpen(true)}
                className="text-sm text-text-muted transition-colors hover:text-text"
              >
                {t("auth.actions.login")}
              </button>
            </li>
          </ul>
          </div>

          <div>
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-text">{t("marketing.footer.legal")}</h2>
          <ul className="space-y-3">
            {legalLinks.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="text-sm text-text-muted transition-colors hover:text-text">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
          </div>
        </div>
        <div className="border-t border-border">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-5 sm:flex-row">
            <p className="text-xs text-text-muted">© {new Date().getFullYear()} PostPiloter. {t("marketing.footer.rights")}</p>
            <p className="text-xs text-text-muted">{t("marketing.footer.tagline")}</p>
          </div>
        </div>
      </footer>
      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
    </>
  );
}
