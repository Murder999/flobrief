"use client";

import Link from "next/link";
import { ChevronRight, Menu, X } from "lucide-react";
import { useState } from "react";
import { LoginModal } from "@/components/auth/LoginModal";
import { LanguageSelector } from "@/components/i18n/language-selector";
import { useLocale } from "@/context/locale-context";
import { localizePublicPath } from "@/lib/i18n/config";

export function PublicHeader() {
  const { locale, t } = useLocale();
  const [menuOpen, setMenuOpen] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const localize = (path: string) => localizePublicPath(path, locale);
  const navigation = [
    { label: t("marketing.navigation.product"), href: `${localize("/")}#features` },
    { label: t("common.navigation.solutions"), href: localize("/ajans-programi") },
    { label: t("marketing.navigation.workflow"), href: `${localize("/")}#workflow` },
    { label: t("common.navigation.pricing"), href: localize("/pricing") },
  ];

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50 border-b border-border bg-background/90 backdrop-blur-xl">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-text"
      >
        {t("marketing.navigation.skip")}
      </a>
      <nav className="mx-auto max-w-7xl px-4 sm:px-6" aria-label={t("common.navigation.home")}>
        <div className="flex h-16 items-center justify-between">
          <Link href={localize("/")} className="group flex min-h-11 items-center gap-2.5" aria-label={t("marketing.navigation.homeLabel")}>
            <span
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-accent text-xs font-black text-white shadow-accent transition-transform group-hover:scale-105"
              aria-hidden="true"
            >
              P
            </span>
            <span className="hidden text-sm font-bold tracking-tight text-text min-[380px]:inline">PostPiloter</span>
          </Link>

          <div className="hidden items-center gap-1 md:flex">
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-lg px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-hover hover:text-text focus-visible:ring-2 focus-visible:ring-accent"
              >
                {item.label}
              </Link>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <LanguageSelector compact />
            <button
              type="button"
              aria-haspopup="dialog"
              onClick={() => setLoginOpen(true)}
              className="hidden min-h-11 items-center rounded-lg px-3 text-sm text-text-secondary transition-colors hover:bg-hover hover:text-text sm:flex"
            >
              {t("auth.actions.login")}
            </button>
            <Link
              href="/demo"
              className="hidden min-h-11 items-center gap-1.5 rounded-xl bg-gradient-accent px-4 text-sm font-semibold text-white shadow-accent transition-transform hover:scale-[1.02] sm:flex"
            >
              {t("marketing.actions.demo")}
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
            <button
              type="button"
              className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-surface text-text md:hidden"
              aria-expanded={menuOpen}
              aria-controls="public-mobile-menu"
              aria-label={menuOpen ? t("marketing.navigation.closeMenu") : t("marketing.navigation.openMenu")}
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <div id="public-mobile-menu" className="border-t border-border py-4 md:hidden">
            <div className="grid gap-1">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex min-h-11 items-center rounded-xl px-3 text-sm font-medium text-text-secondary hover:bg-surface-2 hover:text-text"
                  onClick={() => setMenuOpen(false)}
                >
                  {item.label}
                </Link>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3">
              <button
                type="button"
                aria-haspopup="dialog"
                className="flex min-h-11 items-center justify-center rounded-xl border border-border bg-surface text-sm font-semibold text-text"
                onClick={() => {
                  setMenuOpen(false);
                  setLoginOpen(true);
                }}
              >
                {t("auth.actions.login")}
              </button>
              <Link
                href="/demo"
                className="flex min-h-11 items-center justify-center rounded-xl bg-gradient-accent text-sm font-semibold text-white"
                onClick={() => setMenuOpen(false)}
              >
                {t("marketing.actions.demo")}
              </Link>
            </div>
          </div>
        )}
      </nav>
      </header>
      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
    </>
  );
}
