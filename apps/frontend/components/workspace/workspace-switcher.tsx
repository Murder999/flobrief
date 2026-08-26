"use client";

import { useState } from "react";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useWorkspace } from "@/context/workspace-context";
import { ROLE_LABELS } from "@/lib/workspace";
import { useLocale } from "@/context/locale-context";
import type { TranslationKey } from "@/messages";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function WorkspaceAvatar({ name, logoUrl }: { name: string; logoUrl?: string | null }) {
  if (logoUrl) {
    return (
      <div className="h-6 w-6 flex-shrink-0 overflow-hidden rounded bg-surface-2">
        <Image
          src={API_BASE + logoUrl}
          alt={name}
          width={24}
          height={24}
          unoptimized
          className="h-full w-full object-contain"
        />
      </div>
    );
  }
  return (
    <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded bg-accent/20">
      <span className="text-xs font-bold uppercase text-accent">{name.charAt(0)}</span>
    </div>
  );
}

const ROLE_KEYS: Record<string, TranslationKey> = {
  owner: "settings.role.owner",
  admin: "settings.role.admin",
  brand_manager: "settings.role.brandManager",
  designer: "settings.role.designer",
  developer: "settings.role.developer",
  social_media: "settings.role.socialMedia",
  viewer: "settings.role.viewer",
  brand_owner: "settings.role.brandOwner",
  brand_viewer: "settings.role.viewer",
  external_approver: "settings.role.externalApprover",
};

export function WorkspaceSwitcher() {
  const {
    agencies,
    brands,
    activeAgency,
    activeBrand,
    switchAgency,
    switchBrand,
    isLoading,
  } = useWorkspace();
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const inBrandPortal = pathname.startsWith("/brand");
  const activeWorkspace = inBrandPortal ? activeBrand : activeAgency;
  const roleLabel = (role: string) => (ROLE_KEYS[role] ? t(ROLE_KEYS[role]) : ROLE_LABELS[role] ?? role);

  if (isLoading) {
    return (
      <div className="animate-pulse px-3 py-2">
        <div className="h-4 w-24 rounded bg-surface-2" />
      </div>
    );
  }

  if (!activeWorkspace) {
    return (
      <a
        href="/auth/register"
        className="flex items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-surface-2"
      >
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded border-2 border-dashed border-border">
          <span className="text-xs font-bold text-text-muted">+</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-text-muted">{t("settings.workspace.none")}</p>
          <p className="text-[11px] text-accent">{t("settings.workspace.create")}</p>
        </div>
      </a>
    );
  }

  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-label={t("settings.workspace.switch")}
        onClick={() => setOpen((previous) => !previous)}
        className="group flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-surface-2"
      >
        <WorkspaceAvatar
          name={activeWorkspace.name}
          logoUrl={"logo_url" in activeWorkspace ? activeWorkspace.logo_url : null}
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-text">{activeWorkspace.name}</p>
          <p className="truncate text-xs text-text-muted">
            {inBrandPortal ? t("settings.workspace.brandPortal") : t("settings.workspace.agencyPortal")} · {roleLabel(activeWorkspace.member_role)}
          </p>
        </div>
        <svg
          className={`h-3.5 w-3.5 flex-shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && agencies.length + brands.length > 1 && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-10 cursor-default"
            aria-label={t("settings.workspace.close")}
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-80 overflow-y-auto rounded-xl border border-border bg-surface shadow-xl">
            {agencies.map((agency) => (
              <button
                type="button"
                key={agency.id}
                onClick={() => {
                  switchAgency(agency.id);
                  setOpen(false);
                  router.push("/dashboard");
                }}
                className={`flex min-h-11 w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-surface-2 ${
                  !inBrandPortal && agency.id === activeAgency?.id ? "bg-accent-subtle" : ""
                }`}
              >
                <WorkspaceAvatar name={agency.name} logoUrl={agency.logo_url} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text">{agency.name}</p>
                  <p className="text-xs text-text-muted">{t("settings.workspace.agencyPortal")} · {roleLabel(agency.member_role)}</p>
                </div>
              </button>
            ))}
            {brands.map((brand) => (
              <button
                type="button"
                key={brand.id}
                onClick={() => {
                  switchBrand(brand.id);
                  setOpen(false);
                  router.push("/brand/dashboard");
                }}
                className={`flex min-h-11 w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-surface-2 ${
                  inBrandPortal && brand.id === activeBrand?.id ? "bg-accent-subtle" : ""
                }`}
              >
                <WorkspaceAvatar name={brand.name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text">{brand.name}</p>
                  <p className="text-xs text-text-muted">{t("settings.workspace.brandPortal")} · {roleLabel(brand.member_role)}</p>
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
