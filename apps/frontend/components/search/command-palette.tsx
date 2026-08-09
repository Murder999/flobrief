"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { briefApi, agencyApi, templateApi, type BriefRead, type BrandRead, type TemplateRead } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CommandItem {
  id: string;
  type: "action" | "brief" | "brand" | "template" | "page";
  label: string;
  sub?: string;
  href: string;
  icon: string;
  status?: string;
}

// ── Icons (path strings) ──────────────────────────────────────────────────────

const ICONS: Record<string, string> = {
  brief: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  brand: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
  template: "M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z",
  calendar: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  plus: "M12 4v16m8-8H4",
  dashboard: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  team: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
  reports: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  settings: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Taslak",
  in_review: "İncelemede",
  revision_requested: "Revizyon",
  approved: "Onaylandı",
  archived: "Arşiv",
};

const STATUS_COLORS: Record<string, string> = {
  draft:              "status-neutral",
  in_review:          "status-info",
  revision_requested: "status-danger",
  approved:           "status-success",
  archived:           "status-neutral opacity-60",
};

const QUICK_ACTIONS: CommandItem[] = [
  { id: "new-brief", type: "action", label: "Yeni Brief Oluştur", href: "/dashboard/briefs/new", icon: "plus" },
  { id: "calendar", type: "action", label: "Takvime Git", href: "/dashboard/calendar", icon: "calendar" },
  { id: "team", type: "action", label: "Ekip Üyeleri", href: "/dashboard/settings/members", icon: "team" },
  { id: "reports", type: "action", label: "Raporlar", href: "/dashboard/reports", icon: "reports" },
];

// ── Command Palette Component ──────────────────────────────────────────────────

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const [search, setSearch] = useState("");
  const [briefs, setBriefs] = useState<BriefRead[]>([]);
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [templates, setTemplates] = useState<TemplateRead[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);

  // Load data for search
  useEffect(() => {
    if (!open || !accessToken || !activeAgency?.id) return;
    const agencyId = activeAgency.id;

    briefApi.list({ limit: 50 }, agencyId, accessToken).then((r) => setBriefs(r.items)).catch(() => {});
    agencyApi.listBrands(agencyId, accessToken).then(setBrands).catch(() => {});
    templateApi.list(agencyId, accessToken).then(setTemplates).catch(() => {});
  }, [open, accessToken, activeAgency?.id]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setSearch("");
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Build results
  const results = useMemo(() => {
    const q = search.toLowerCase().trim();

    const quickActions: CommandItem[] = q
      ? QUICK_ACTIONS.filter((a) => a.label.toLowerCase().includes(q))
      : QUICK_ACTIONS;

    const briefItems: CommandItem[] = briefs
      .filter((b) => !q || b.title.toLowerCase().includes(q))
      .slice(0, 6)
      .map((b) => ({
        id: b.id,
        type: "brief" as const,
        label: b.title,
        sub: b.status,
        href: `/dashboard/briefs/${b.id}`,
        icon: "brief",
        status: b.status,
      }));

    const brandItems: CommandItem[] = brands
      .filter((b) => !q || b.name.toLowerCase().includes(q))
      .slice(0, 4)
      .map((b) => ({
        id: b.id,
        type: "brand" as const,
        label: b.name,
        href: `/dashboard/brands`,
        icon: "brand",
      }));

    const templateItems: CommandItem[] = templates
      .filter((t) => !q || t.name.toLowerCase().includes(q))
      .slice(0, 3)
      .map((t) => ({
        id: t.id,
        type: "template" as const,
        label: t.name,
        href: `/dashboard/templates/${t.id}`,
        icon: "template",
      }));

    return { quickActions, briefItems, brandItems, templateItems };
  }, [search, briefs, brands, templates]);

  const allItems = useMemo(() => {
    return [
      ...results.quickActions,
      ...results.briefItems,
      ...results.brandItems,
      ...results.templateItems,
    ];
  }, [results]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, allItems.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = allItems[activeIndex];
        if (item) {
          router.push(item.href);
          onClose();
        }
      }
    },
    [allItems, activeIndex, router, onClose]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div
        className="relative w-full max-w-xl bg-surface border border-border rounded-2xl shadow-2xl overflow-hidden"
        style={{ boxShadow: "0 25px 50px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)" }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
          <svg className="w-4 h-4 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setActiveIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Ara veya komut gir..."
            className="flex-1 bg-transparent text-sm text-text placeholder:text-text-muted outline-none"
          />
          <kbd className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono text-text-muted border border-border bg-surface-2">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-2">
          {allItems.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-text-muted">
              {search ? `"${search}" için sonuç bulunamadı.` : "Arama başlatmak için yazmaya başlayın."}
            </div>
          ) : (
            <>
              {/* Quick Actions */}
              {results.quickActions.length > 0 && (
                <Group label="HIZLI AKSIYONLAR">
                  {results.quickActions.map((item) => {
                    const globalIdx = allItems.indexOf(item);
                    return (
                      <ResultItem
                        key={item.id}
                        item={item}
                        isActive={globalIdx === activeIndex}
                        onSelect={() => { router.push(item.href); onClose(); }}
                        onHover={() => setActiveIndex(globalIdx)}
                      />
                    );
                  })}
                </Group>
              )}

              {/* Briefs */}
              {results.briefItems.length > 0 && (
                <Group label="BRIEFLER">
                  {results.briefItems.map((item) => {
                    const globalIdx = allItems.indexOf(item);
                    return (
                      <ResultItem
                        key={item.id}
                        item={item}
                        isActive={globalIdx === activeIndex}
                        onSelect={() => { router.push(item.href); onClose(); }}
                        onHover={() => setActiveIndex(globalIdx)}
                      />
                    );
                  })}
                </Group>
              )}

              {/* Brands */}
              {results.brandItems.length > 0 && (
                <Group label="MARKALAR">
                  {results.brandItems.map((item) => {
                    const globalIdx = allItems.indexOf(item);
                    return (
                      <ResultItem
                        key={item.id}
                        item={item}
                        isActive={globalIdx === activeIndex}
                        onSelect={() => { router.push(item.href); onClose(); }}
                        onHover={() => setActiveIndex(globalIdx)}
                      />
                    );
                  })}
                </Group>
              )}

              {/* Templates */}
              {results.templateItems.length > 0 && (
                <Group label="ŞABLONLAR">
                  {results.templateItems.map((item) => {
                    const globalIdx = allItems.indexOf(item);
                    return (
                      <ResultItem
                        key={item.id}
                        item={item}
                        isActive={globalIdx === activeIndex}
                        onSelect={() => { router.push(item.href); onClose(); }}
                        onHover={() => setActiveIndex(globalIdx)}
                      />
                    );
                  })}
                </Group>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 border-t border-border bg-surface-2/50 flex items-center gap-4">
          <span className="flex items-center gap-1 text-[10px] text-text-muted">
            <kbd className="inline-flex items-center px-1 py-0.5 rounded text-[9px] font-mono border border-border/60 bg-surface">↑↓</kbd>
            gezin
          </span>
          <span className="flex items-center gap-1 text-[10px] text-text-muted">
            <kbd className="inline-flex items-center px-1 py-0.5 rounded text-[9px] font-mono border border-border/60 bg-surface">↵</kbd>
            seç
          </span>
          <span className="flex items-center gap-1 text-[10px] text-text-muted">
            <kbd className="inline-flex items-center px-1 py-0.5 rounded text-[9px] font-mono border border-border/60 bg-surface">esc</kbd>
            kapat
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-1">
      <p className="px-4 py-1.5 text-[10px] font-semibold text-text-muted tracking-widest uppercase">
        {label}
      </p>
      {children}
    </div>
  );
}

function ResultItem({
  item,
  isActive,
  onSelect,
  onHover,
}: {
  item: CommandItem;
  isActive: boolean;
  onSelect: () => void;
  onHover: () => void;
}) {
  const iconPath = ICONS[item.icon] ?? ICONS.brief;
  const statusLabel = item.status ? STATUS_LABELS[item.status] : null;
  const statusColor = item.status ? STATUS_COLORS[item.status] : null;

  return (
    <button
      onMouseDown={(e) => e.preventDefault()}
      onClick={onSelect}
      onMouseEnter={onHover}
      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
        isActive ? "bg-accent/10" : "hover:bg-surface-2"
      }`}
    >
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
        isActive ? "bg-accent/20 text-accent" : "bg-surface-2 text-text-muted"
      }`}>
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={iconPath} />
        </svg>
      </div>
      <span className={`flex-1 text-sm truncate ${isActive ? "text-accent font-medium" : "text-text"}`}>
        {item.label}
      </span>
      {statusLabel && statusColor && (
        <span className={`flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${statusColor}`}>
          {statusLabel}
        </span>
      )}
    </button>
  );
}

