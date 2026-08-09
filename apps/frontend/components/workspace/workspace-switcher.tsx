"use client";

import { useState } from "react";
import { useWorkspace } from "@/context/workspace-context";
import { ROLE_LABELS } from "@/lib/workspace";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function AgencyAvatar({ name, logoUrl, size = 6 }: { name: string; logoUrl?: string | null; size?: number }) {
  const sz = `w-${size} h-${size}`;
  if (logoUrl) {
    return (
      <div className={`${sz} rounded overflow-hidden flex-shrink-0 bg-surface-2`}>
        <img src={API_BASE + logoUrl} alt={name} className="w-full h-full object-contain" />
      </div>
    );
  }
  return (
    <div className={`${sz} bg-accent/20 rounded flex items-center justify-center flex-shrink-0`}>
      <span className="text-xs font-bold text-accent uppercase">{name.charAt(0)}</span>
    </div>
  );
}

function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

export function WorkspaceSwitcher() {
  const { agencies, activeAgency, switchAgency, isLoading } = useWorkspace();
  const [open, setOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="px-3 py-2 animate-pulse">
        <div className="h-4 bg-surface-2 rounded w-24" />
      </div>
    );
  }

  if (!activeAgency) {
    return (
      <a
        href="/onboarding/create-agency"
        className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-2 transition-colors text-left"
      >
        <div className="w-6 h-6 border-2 border-dashed border-border rounded flex items-center justify-center flex-shrink-0">
          <span className="text-text-muted text-xs font-bold">+</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text-muted">Ajans seçilmedi</p>
          <p className="text-[11px] text-accent">Ajans oluştur →</p>
        </div>
      </a>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-2
          transition-colors text-left group"
      >
        <AgencyAvatar name={activeAgency.name} logoUrl={activeAgency.logo_url} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text truncate">{activeAgency.name}</p>
          <p className="text-xs text-text-muted truncate">{roleLabel(activeAgency.member_role)}</p>
        </div>
        <svg
          className={`w-3.5 h-3.5 text-text-muted flex-shrink-0 transition-transform ${
            open ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && agencies.length > 1 && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-0 right-0 top-full mt-1 z-20 bg-surface border border-border rounded-xl shadow-xl overflow-hidden">
            {agencies.map((agency) => (
              <button
                key={agency.id}
                onClick={() => {
                  switchAgency(agency.id);
                  setOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-surface-2
                  transition-colors text-left ${
                    agency.id === activeAgency.id ? "bg-accent-subtle" : ""
                  }`}
              >
                <AgencyAvatar name={agency.name} logoUrl={agency.logo_url} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text truncate">{agency.name}</p>
                  <p className="text-xs text-text-muted">{roleLabel(agency.member_role)}</p>
                </div>
                {agency.id === activeAgency.id && (
                  <svg
                    className="w-4 h-4 text-accent flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
