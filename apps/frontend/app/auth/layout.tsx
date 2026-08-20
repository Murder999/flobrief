import type { Metadata } from "next";
import { headers } from "next/headers";
import type { ReactNode } from "react";
import { LOCALE_HEADER_NAME, normalizeLocale } from "@/lib/i18n/config";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(headers().get(LOCALE_HEADER_NAME)) ?? "en";
  return { title: locale === "tr" ? "PostPiloter — Giriş" : "PostPiloter — Account access" };
}

export default function AuthLayout({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-background">{children}</div>;
}
