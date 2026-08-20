"use client";

import Link from "next/link";
import { useLocale } from "@/context/locale-context";

export default function NotFound() {
  const { t } = useLocale();
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="text-center max-w-sm">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-accent/10 rounded-2xl mb-6 border border-accent/20">
          <span className="text-3xl font-bold text-accent">404</span>
        </div>
        <h1 className="text-2xl font-bold text-text mb-2">{t("common.notFound.title")}</h1>
        <p className="text-sm text-text-muted mb-8 leading-relaxed">
          {t("common.notFound.description")}
        </p>
        <div className="flex flex-col gap-3">
          <Link
            href="/dashboard"
            className="w-full inline-flex items-center justify-center h-10 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            {t("common.navigation.dashboard")}
          </Link>
          <Link
            href="/"
            className="w-full inline-flex items-center justify-center h-10 rounded-lg border border-border text-text-muted text-sm font-medium hover:text-text hover:border-border-hover transition-colors"
          >
            {t("common.navigation.home")}
          </Link>
        </div>
      </div>
    </div>
  );
}
