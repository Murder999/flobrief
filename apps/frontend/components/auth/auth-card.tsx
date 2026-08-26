"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { PostPiloterLogo } from "@/components/brand/PostPiloterLogo";
import { useLocale } from "@/context/locale-context";

export function AuthCard({
  children,
  wide = false,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  const { locale } = useLocale();
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative overflow-hidden">
      {/* Ambient glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[500px] bg-accent/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-[400px] h-[300px] bg-purple/4 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-1/2 left-0 w-[300px] h-[300px] bg-accent/3 rounded-full blur-3xl pointer-events-none" />

      <div className={`relative w-full ${wide ? "max-w-2xl" : "max-w-md"}`}>
        {/* Logo */}
        <div className="mb-8 text-center">
          <Link href="/" className="inline-flex items-center gap-2.5 group">
            <PostPiloterLogo className="h-10 w-auto transition-transform group-hover:scale-[1.02]" priority />
          </Link>
        </div>

        {/* Card */}
        <div className="relative bg-surface border border-border rounded-2xl shadow-modal p-8 overflow-hidden">
          {/* Top accent line */}
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
          {/* Subtle inner glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-24 bg-accent/3 rounded-full blur-2xl pointer-events-none" />
          <div className="relative">
            {children}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-text-muted">
          © {new Date().getFullYear()} PostPiloter. {locale === "tr" ? "Tüm hakları saklıdır." : "All rights reserved."}
        </p>
      </div>
    </div>
  );
}
