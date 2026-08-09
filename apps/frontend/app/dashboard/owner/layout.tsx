"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

export default function OwnerLayout({ children }: { children: ReactNode }) {
  const { user, isInitialized: authInit } = useAuth();
  const { activeAgency, isInitialized: wsInit } = useWorkspace();
  const router = useRouter();

  const isPlatformAdmin = user?.user_type === "platform_admin";
  const isAgencyOwner = activeAgency?.member_role === "owner";

  useEffect(() => {
    if (!authInit) return;
    if (isPlatformAdmin) return; // platform_admin always allowed
    if (!wsInit) return; // wait for workspace to load
    if (!isAgencyOwner) {
      router.replace("/dashboard");
    }
  }, [authInit, wsInit, isPlatformAdmin, isAgencyOwner, router]);

  if (!authInit || (!isPlatformAdmin && !wsInit)) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex items-center gap-3 text-text-muted">
          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm">Yükleniyor…</span>
        </div>
      </div>
    );
  }

  if (!isPlatformAdmin && !isAgencyOwner) return null;

  return <>{children}</>;
}
