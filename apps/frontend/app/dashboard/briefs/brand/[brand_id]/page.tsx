"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  dashboardApi,
  type BrandWorkspaceData, type BrandBriefSummary,
  type BrandDeliverableSummary, type BrandCalendarItemSummary,
  type BrandWorkspaceDNA,
} from "@/lib/api-client";
import { BriefStatusBadge, BriefPriorityBadge } from "@/components/briefs/brief-status-badge";
import { cn } from "@/lib/utils";
import {
  ArrowLeft, Plus, AlertTriangle, RefreshCw, Calendar, FileText,
  CheckCircle2, Clock, Layers, Package, Dna, Activity, ChevronRight,
  ExternalLink, Video, Image as ImageIcon, Type, FileArchive, Building2,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

type Tab = "overview" | "briefs" | "deliverables" | "calendar" | "dna";

const TABS: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "overview",     label: "Genel Bakış",   icon: Layers      },
  { id: "briefs",       label: "Briefler",       icon: FileText    },
  { id: "deliverables", label: "Teslimler",      icon: Package     },
  { id: "calendar",     label: "Takvim Planı",   icon: Calendar    },
  { id: "dna",          label: "Marka DNA",      icon: Dna         },
];

// ── Skeleton ──────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="min-h-full bg-background">
      <div className="border-b border-border bg-surface px-4 sm:px-8 py-6">
        <div className="max-w-7xl mx-auto">
          <div className="h-3 shimmer rounded-lg w-32 mb-4" />
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 shimmer rounded-xl" />
            <div className="space-y-2">
              <div className="h-5 shimmer rounded-lg w-36" />
              <div className="h-3 shimmer rounded-lg w-24" />
            </div>
          </div>
        </div>
      </div>
      <div className="px-4 sm:px-8 py-6 max-w-7xl mx-auto">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-6">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-2xl p-5">
              <div className="h-3 shimmer rounded-lg w-16 mb-3" />
              <div className="h-6 shimmer rounded-lg w-10" />
            </div>
          ))}
        </div>
        <div className="flex gap-2 mb-6">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-9 shimmer rounded-lg w-24" />)}
        </div>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 shimmer rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────────────

function KPICard({
  label, value, icon, variant = "default",
}: {
  label: string; value: number; icon: React.ReactNode; variant?: "default" | "danger" | "warning" | "info";
}) {
  const card = {
    default: "bg-surface border-border",
    danger:  "bg-danger-subtle border-danger-border",
    warning: "bg-warning-subtle border-warning-border",
    info:    "bg-info-subtle border-info-border",
  }[variant];
  const val = {
    default: "text-text",
    danger:  "text-danger-text",
    warning: "text-warning-text",
    info:    "text-info-text",
  }[variant];
  return (
    <div className={cn("rounded-2xl border p-5 shadow-card", card)}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{label}</span>
        <span className="text-text-muted">{icon}</span>
      </div>
      <div className={cn("text-2xl font-bold tabular-nums", val)}>{value}</div>
    </div>
  );
}

// ── Status badge helpers ──────────────────────────────────────────────────────

const STATUS_TR: Record<string, string> = {
  draft:              "Taslak",
  submitted:          "Talep Gönderildi",
  accepted:           "Kabul Edildi",
  in_production:      "Üretimde",
  ready_for_review:   "İncelemeye Hazır",
  revision_requested: "Revizyon İstendi",
  approved:           "Onaylandı",
  completed:          "Tamamlandı",
  scheduled:          "Takvime Alındı",
  archived:           "Arşivlendi",
  in_review:          "İncelemede",
};

const DELIVERABLE_STATUS_TR: Record<string, string> = {
  draft:              "Taslak",
  submitted:          "Teslim Edildi",
  revision_requested: "Revizyon İstendi",
  approved:           "Onaylandı",
  rejected:           "Reddedildi",
  archived:           "Arşivlendi",
};

const DELIVERABLE_TYPE_ICON: Record<string, React.ReactNode> = {
  image:    <ImageIcon className="w-4 h-4" />,
  video:    <Video    className="w-4 h-4" />,
  text:     <Type     className="w-4 h-4" />,
  document: <FileArchive className="w-4 h-4" />,
};

const CALENDAR_STATUS_TR: Record<string, string> = {
  planned:          "Planlandı",
  in_design:        "Tasarımda",
  waiting_approval: "Onay Bekliyor",
  approved:         "Onaylandı",
  scheduled:        "Zamanlandı",
  published:        "Yayınlandı",
  cancelled:        "İptal",
};

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab({ data }: { data: BrandWorkspaceData }) {
  return (
    <div className="space-y-6">
      {/* Recent briefs */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-text uppercase tracking-wider">Son Briefler</h3>
          <button
            onClick={() => {}}
            className="text-xs text-text-muted hover:text-text transition-colors"
          >
            Tümü →
          </button>
        </div>
        {data.recent_briefs.length === 0 ? (
          <p className="text-sm text-text-muted py-4 text-center">Brief bulunamadı.</p>
        ) : (
          <div className="space-y-2">
            {data.recent_briefs.slice(0, 5).map((b) => (
              <Link
                key={b.id}
                href={`/dashboard/briefs/${b.id}`}
                className="group flex items-center gap-3 p-3 bg-surface border border-border rounded-xl hover:border-border-hover hover:shadow-card-hover transition-all"
              >
                <FileText className="w-4 h-4 text-text-muted flex-shrink-0" />
                <span className="flex-1 text-sm text-text truncate group-hover:text-accent transition-colors">{b.title}</span>
                <BriefStatusBadge status={b.status as never} />
                <ChevronRight className="w-3.5 h-3.5 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Upcoming calendar */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-text uppercase tracking-wider">Yaklaşan Takvim</h3>
        </div>
        {data.upcoming_calendar.length === 0 ? (
          <p className="text-sm text-text-muted py-4 text-center">Planlanan içerik yok.</p>
        ) : (
          <div className="space-y-2">
            {data.upcoming_calendar.slice(0, 5).map((c) => (
              <div
                key={c.id}
                className="flex items-center gap-3 p-3 bg-surface border border-border rounded-xl"
              >
                <Calendar className="w-4 h-4 text-text-muted flex-shrink-0" />
                <span className="flex-1 text-sm text-text truncate">{c.title}</span>
                <span className="text-[10px] font-medium text-text-muted bg-surface-2 px-2 py-0.5 rounded-full capitalize">
                  {c.item_type}
                </span>
                {(c.publish_at ?? c.due_at) && (
                  <span className="text-xs text-text-muted flex-shrink-0">
                    {new Date(c.publish_at ?? c.due_at!).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* DNA summary */}
      {data.brand_dna.has_profile && (
        <div className="bg-gradient-to-br from-accent/5 to-accent/10 border border-accent/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Dna className="w-4 h-4 text-accent" />
            <h3 className="text-sm font-semibold text-text">Marka DNA</h3>
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-success-subtle text-success-text ml-auto capitalize">
              {data.brand_dna.status}
            </span>
          </div>
          {data.brand_dna.summary && (
            <p className="text-xs text-text-secondary leading-relaxed mb-3 line-clamp-3">{data.brand_dna.summary}</p>
          )}
          {data.brand_dna.primary_colors && data.brand_dna.primary_colors.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-text-muted">Renkler:</span>
              <div className="flex gap-1">
                {(data.brand_dna.primary_colors as string[]).slice(0, 5).map((color, i) => (
                  <div
                    key={i}
                    className="w-5 h-5 rounded-full border border-border shadow-xs"
                    style={{ backgroundColor: color }}
                    title={color}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Briefs Tab ────────────────────────────────────────────────────────────────

function BriefsTab({ data }: { data: BrandWorkspaceData }) {
  const [filter, setFilter] = useState("");

  const filtered = data.recent_briefs.filter(
    (b) => !filter || b.status === filter
  );

  const BRIEF_STATUS_FILTERS = [
    { value: "", label: "Tümü" },
    { value: "draft", label: "Taslak" },
    { value: "submitted", label: "Yeni Gelen" },
    { value: "accepted", label: "Kabul Edildi" },
    { value: "in_production", label: "Üretimde" },
    { value: "revision_requested", label: "Revizyon" },
    { value: "approved", label: "Onaylandı" },
  ];

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-4 flex-wrap">
        {BRIEF_STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
              filter === f.value
                ? "bg-accent text-white"
                : "bg-surface-2 border border-border text-text-secondary hover:text-text hover:border-border-hover"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center">
          <FileText className="w-8 h-8 text-text-muted mx-auto mb-3" />
          <p className="text-sm text-text-muted">Bu filtrede brief bulunamadı.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((b) => (
            <BriefRow key={b.id} brief={b} />
          ))}
        </div>
      )}
    </div>
  );
}

function BriefRow({ brief }: { brief: BrandBriefSummary }) {
  const isOverdue =
    brief.deadline &&
    new Date(brief.deadline) < new Date() &&
    !["approved", "completed", "archived", "scheduled"].includes(brief.status);

  return (
    <Link
      href={`/dashboard/briefs/${brief.id}`}
      className="group flex items-center gap-4 p-4 bg-surface border border-border rounded-xl hover:border-border-hover hover:shadow-card-hover transition-all"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="font-medium text-sm text-text truncate group-hover:text-accent transition-colors">
            {brief.title}
          </span>
          {brief.source === "brand_portal" && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md status-info flex-shrink-0">
              Marka Talebi
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <BriefStatusBadge status={brief.status as never} />
          <BriefPriorityBadge priority={brief.priority as never} />
          {brief.deadline && (
            <span className={cn(
              "text-xs flex items-center gap-1",
              isOverdue ? "text-danger-text font-medium" : "text-text-muted"
            )}>
              <Clock className="w-3 h-3" />
              {new Date(brief.deadline).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" })}
              {isOverdue && " — Gecikti"}
            </span>
          )}
        </div>
      </div>
      <div className="flex-shrink-0 text-xs text-text-muted">
        {new Date(brief.updated_at).toLocaleDateString("tr-TR")}
      </div>
      <ChevronRight className="w-4 h-4 text-text-muted opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
    </Link>
  );
}

// ── Deliverables Tab ──────────────────────────────────────────────────────────

function DeliverablesTab({ data }: { data: BrandWorkspaceData }) {
  const [filter, setFilter] = useState("");

  const DELIV_FILTERS = [
    { value: "", label: "Tümü" },
    { value: "draft", label: "Taslak" },
    { value: "submitted", label: "Teslim Edildi" },
    { value: "revision_requested", label: "Revizyon" },
    { value: "approved", label: "Onaylandı" },
  ];

  const filtered = data.recent_deliverables.filter(
    (d) => !filter || d.status === filter
  );

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-4 flex-wrap">
        {DELIV_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
              filter === f.value
                ? "bg-accent text-white"
                : "bg-surface-2 border border-border text-text-secondary hover:text-text hover:border-border-hover"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center">
          <Package className="w-8 h-8 text-text-muted mx-auto mb-3" />
          <p className="text-sm text-text-muted">Bu filtrede teslim bulunamadı.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((d) => <DeliverableRow key={d.id} deliverable={d} />)}
        </div>
      )}
    </div>
  );
}

function DeliverableRow({ deliverable: d }: { deliverable: BrandDeliverableSummary }) {
  const statusCls: Record<string, string> = {
    draft:              "status-default",
    submitted:          "status-info",
    revision_requested: "status-warning",
    approved:           "status-success",
    rejected:           "status-danger",
    archived:           "status-default",
  };

  return (
    <Link
      href={`/dashboard/briefs/${d.brief_id}`}
      className="group flex items-center gap-4 p-4 bg-surface border border-border rounded-xl hover:border-border-hover hover:shadow-card-hover transition-all"
    >
      <div className="w-9 h-9 bg-surface-2 border border-border rounded-xl flex items-center justify-center flex-shrink-0 text-text-muted">
        {DELIVERABLE_TYPE_ICON[d.deliverable_type] ?? <Package className="w-4 h-4" />}
      </div>
      <div className="flex-1 min-w-0">
        <span className="font-medium text-sm text-text truncate block group-hover:text-accent transition-colors">
          {d.title}
        </span>
        <div className="flex items-center gap-2 mt-1">
          <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full", statusCls[d.status] ?? "status-default")}>
            {DELIVERABLE_STATUS_TR[d.status] ?? d.status}
          </span>
          <span className="text-[10px] text-text-muted">v{d.version_number}</span>
          {d.revision_count > 0 && (
            <span className="text-[10px] text-warning-text">{d.revision_count} revizyon</span>
          )}
        </div>
      </div>
      <div className="flex-shrink-0 text-xs text-text-muted">
        {new Date(d.updated_at).toLocaleDateString("tr-TR")}
      </div>
      <ChevronRight className="w-4 h-4 text-text-muted opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
    </Link>
  );
}

// ── Calendar Tab ──────────────────────────────────────────────────────────────

function CalendarTab({ data }: { data: BrandWorkspaceData }) {
  return (
    <div>
      {data.upcoming_calendar.length === 0 ? (
        <div className="py-16 text-center">
          <Calendar className="w-8 h-8 text-text-muted mx-auto mb-3" />
          <p className="text-sm text-text-secondary mb-1">Yaklaşan içerik planı yok.</p>
          <Link
            href="/dashboard/calendar"
            className="text-xs text-accent hover:underline"
          >
            Takvime Git →
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {data.upcoming_calendar.map((c) => <CalendarItemRow key={c.id} item={c} />)}
        </div>
      )}
      <div className="mt-6 text-center">
        <Link
          href="/dashboard/calendar"
          className="inline-flex items-center gap-2 px-4 py-2 bg-surface-2 border border-border rounded-xl text-sm font-medium text-text-secondary hover:text-text hover:border-border-hover transition-all"
        >
          <Calendar className="w-4 h-4" />
          Tam Takvimi Aç
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}

function CalendarItemRow({ item: c }: { item: BrandCalendarItemSummary }) {
  const displayDate = c.publish_at ?? c.due_at;
  const isPast = displayDate && new Date(displayDate) < new Date();

  const statusCls: Record<string, string> = {
    planned:          "status-default",
    in_design:        "status-info",
    waiting_approval: "status-warning",
    approved:         "status-success",
    scheduled:        "status-info",
    published:        "status-success",
    cancelled:        "status-default",
  };

  const typeColors: Record<string, string> = {
    post: "bg-blue-500/10 text-blue-600",
    story: "bg-purple-500/10 text-purple-600",
    reels: "bg-pink-500/10 text-pink-600",
    video: "bg-red-500/10 text-red-600",
    campaign: "bg-orange-500/10 text-orange-600",
    email: "bg-green-500/10 text-green-600",
  };

  return (
    <div className={cn(
      "flex items-center gap-4 p-4 bg-surface border rounded-xl transition-all",
      isPast ? "border-border opacity-60" : "border-border hover:border-border-hover hover:shadow-card-hover"
    )}>
      <div className="flex-shrink-0 w-10 text-center">
        {displayDate && (
          <>
            <div className="text-lg font-bold text-text tabular-nums leading-none">
              {new Date(displayDate).getDate()}
            </div>
            <div className="text-[10px] text-text-muted">
              {new Date(displayDate).toLocaleDateString("tr-TR", { month: "short" })}
            </div>
          </>
        )}
      </div>
      <div className="w-px h-10 bg-border flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={cn("text-[10px] font-semibold px-1.5 py-0.5 rounded-md capitalize", typeColors[c.item_type] ?? "bg-surface-2 text-text-muted")}>
            {c.item_type}
          </span>
          <span className="text-xs font-medium text-text-muted capitalize">{c.platform}</span>
        </div>
        <span className="text-sm font-medium text-text truncate block">{c.title}</span>
      </div>
      <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full flex-shrink-0", statusCls[c.status] ?? "status-default")}>
        {CALENDAR_STATUS_TR[c.status] ?? c.status}
      </span>
    </div>
  );
}

// ── DNA Tab ───────────────────────────────────────────────────────────────────

function DNATab({ data, brandId }: { data: BrandWorkspaceData; brandId: string; }) {
  const dna: BrandWorkspaceDNA = data.brand_dna;
  if (!dna.has_profile) {
    return (
      <div className="py-16 flex flex-col items-center justify-center text-center">
        <div className="w-16 h-16 bg-surface-2 border border-border rounded-2xl flex items-center justify-center mb-5">
          <Dna className="w-7 h-7 text-text-muted" />
        </div>
        <h3 className="text-sm font-semibold text-text mb-2">Marka DNA Oluşturulmamış</h3>
        <p className="text-sm text-text-secondary mb-6 max-w-xs leading-relaxed">
          Bu marka için henüz kurumsal kimlik analizi yapılmamış. Kurumsal kimlik PDF&apos;ini yükleyerek Marka DNA profilini oluşturun.
        </p>
        <Link
          href={`/dashboard/brands/${brandId}/identity`}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-accent text-white rounded-xl text-sm font-semibold hover:opacity-90 transition-all shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Kurumsal Kimlik PDF&apos;i Yükle
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Status */}
      <div className="flex items-center gap-3 p-4 bg-success-subtle border border-success-border rounded-xl">
        <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-text">Marka DNA Mevcut</p>
          <p className="text-xs text-text-muted mt-0.5 capitalize">Durum: {dna.status}</p>
        </div>
        <Link
          href={`/dashboard/brands/${brandId}/identity`}
          className="ml-auto text-xs text-accent hover:underline flex items-center gap-1"
        >
          DNA Düzenle <ExternalLink className="w-3 h-3" />
        </Link>
      </div>

      {/* Summary */}
      {dna.summary && (
        <div>
          <h3 className="text-xs font-semibold text-text uppercase tracking-wider mb-2">Özet</h3>
          <p className="text-sm text-text-secondary leading-relaxed">{dna.summary}</p>
        </div>
      )}

      {/* Colors */}
      {dna.primary_colors && dna.primary_colors.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-text uppercase tracking-wider mb-3">Ana Renkler</h3>
          <div className="flex flex-wrap gap-3">
            {(dna.primary_colors as string[]).map((color, i) => (
              <div key={i} className="flex items-center gap-2">
                <div
                  className="w-8 h-8 rounded-lg border border-border shadow-xs"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs text-text-muted font-mono">{color}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Typography */}
      {dna.typography && (dna.typography as unknown[]).length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-text uppercase tracking-wider mb-3">Tipografi</h3>
          <div className="space-y-2">
            {(dna.typography as Record<string, string>[]).map((font, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="text-text">{font.family ?? font.name ?? String(font)}</span>
                {font.weight && <span className="text-xs text-text-muted">· {font.weight}</span>}
                {font.usage && <span className="text-xs text-text-muted">· {font.usage}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tone of Voice */}
      {dna.tone_of_voice && (
        <div>
          <h3 className="text-xs font-semibold text-text uppercase tracking-wider mb-3">Ton & Ses</h3>
          <div className="bg-surface-2 rounded-xl p-4 border border-border">
            {Object.entries(dna.tone_of_voice).map(([key, val]) => (
              <div key={key} className="flex gap-3 mb-2 last:mb-0">
                <span className="text-xs font-medium text-text-muted capitalize w-28 flex-shrink-0">{key}:</span>
                <span className="text-xs text-text-secondary">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Brand Logo ────────────────────────────────────────────────────────────────

function BrandLogoLarge({ data }: { data: BrandWorkspaceData }) {
  if (data.brand_logo_url) {
    return (
      <img
        src={`${API_BASE}${data.brand_logo_url}`}
        alt={data.brand_name}
        className="w-12 h-12 rounded-xl object-contain bg-surface border border-border p-0.5 shadow-sm"
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
    );
  }
  return (
    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent/20 to-accent/10 border border-accent/20 flex items-center justify-center shadow-sm">
      <span className="text-lg font-bold text-accent">{data.brand_name.charAt(0).toUpperCase()}</span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BrandWorkspacePage() {
  const params = useParams();
  const brandId = params.brand_id as string;
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();
  const currentAgencyId = activeAgency?.id ?? null;

  const [data,    setData]    = useState<BrandWorkspaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);
  const [tab,     setTab]     = useState<Tab>("overview");

  const fetchData = useCallback(async () => {
    if (!accessToken || !currentAgencyId || !brandId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await dashboardApi.brandWorkspace(brandId, currentAgencyId, accessToken);
      setData(result);
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 404) {
        setError("Bu marka bulunamadı veya erişim yetkiniz yok.");
      } else {
        setError("Marka iş akışı yüklenemedi.");
      }
    } finally {
      setLoading(false);
    }
  }, [accessToken, currentAgencyId, brandId]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !currentAgencyId) setLoading(false);
  }, [workspaceReady, workspaceLoading, currentAgencyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <PageSkeleton />;

  if (error || !data) {
    return (
      <div className="min-h-full bg-background px-8 py-12">
        <Link
          href="/dashboard/briefs"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Brief Merkezi
        </Link>
        <div className="max-w-md mx-auto flex flex-col items-center text-center py-16">
          <AlertTriangle className="w-10 h-10 text-danger mb-4" />
          <h2 className="text-sm font-semibold text-text mb-2">{error ?? "Bir hata oluştu"}</h2>
          <button
            onClick={fetchData}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-surface border border-border rounded-xl text-sm font-medium text-text hover:border-border-hover transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            Tekrar Dene
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-background">
      {/* Header */}
      <div className="border-b border-border bg-surface px-4 sm:px-8 py-6">
        <div className="max-w-7xl mx-auto">
          {/* Breadcrumb */}
          <Link
            href="/dashboard/briefs"
            className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text mb-4 transition-colors group"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
            Brief Merkezi
          </Link>

          {/* Brand info */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <BrandLogoLarge data={data} />
              <div>
                <div className="flex items-center gap-2.5 mb-0.5">
                  <h1 className="text-xl font-bold text-text">{data.brand_name}</h1>
                  <span className={cn(
                    "text-xs font-semibold px-2 py-0.5 rounded-full",
                    data.brand_status === "active"
                      ? "bg-success-subtle text-success-text"
                      : "bg-surface-2 text-text-muted"
                  )}>
                    {data.brand_status === "active" ? "Aktif" : data.brand_status}
                  </span>
                </div>
                <p className="text-sm text-text-muted">{data.brand_name} İş Akışı</p>
              </div>
            </div>
            <Link
              href={`/dashboard/briefs/new?brand_id=${brandId}`}
              className="flex-shrink-0 inline-flex items-center gap-2 px-4 py-2 bg-gradient-accent text-white rounded-xl text-sm font-semibold hover:opacity-90 transition-all shadow-sm hover:shadow-glow-sm"
            >
              <Plus className="w-4 h-4" />
              Yeni Brief
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Row */}
      <div className="border-b border-border bg-surface-2 px-4 sm:px-8 py-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <KPICard
              label="Aktif Brief"
              value={data.kpis.active_briefs}
              icon={<FileText className="w-4 h-4" />}
            />
            <KPICard
              label="Geciken"
              value={data.kpis.overdue_briefs}
              icon={<AlertTriangle className="w-4 h-4" />}
              variant={data.kpis.overdue_briefs > 0 ? "danger" : "default"}
            />
            <KPICard
              label="Revizyon"
              value={data.kpis.revision_requested}
              icon={<RefreshCw className="w-4 h-4" />}
              variant={data.kpis.revision_requested > 0 ? "warning" : "default"}
            />
            <KPICard
              label="Onay Bekleyen"
              value={data.kpis.pending_approvals}
              icon={<CheckCircle2 className="w-4 h-4" />}
              variant={data.kpis.pending_approvals > 0 ? "info" : "default"}
            />
            <KPICard
              label="Bu Hafta"
              value={data.kpis.this_week_calendar}
              icon={<Calendar className="w-4 h-4" />}
            />
          </div>
        </div>
      </div>

      {/* Tabs + Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-6">
        {/* Tab bar */}
        <div className="flex items-center gap-1 bg-surface-2 border border-border p-1 rounded-xl mb-7 w-full sm:w-fit overflow-x-auto shadow-xs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all flex-shrink-0",
                tab === id
                  ? "bg-surface text-text shadow-xs border border-border"
                  : "text-text-muted hover:text-text-secondary"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            {tab === "overview"     && <OverviewTab data={data} />}
            {tab === "briefs"       && <BriefsTab data={data} />}
            {tab === "deliverables" && <DeliverablesTab data={data} />}
            {tab === "calendar"     && <CalendarTab data={data} />}
            {tab === "dna"          && <DNATab data={data} brandId={brandId} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
