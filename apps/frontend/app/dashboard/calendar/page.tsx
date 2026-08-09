"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  calendarApi,
  agencyApi,
  deliverablePreviewApi,
  type AgencyCalendarEntry,
  type BrandRead,
  type CalendarItemCreate,
  type CalendarItemUpdate,
  type CalendarItemStatus,
  type CalendarItemType,
  type CalendarPlatform,
  type PreviewConfigRead,
  type PreviewSlotRead,
} from "@/lib/api-client";
import { Modal } from "@/components/ui/modal";
import { PlatformPreviewShell } from "@/components/preview/PlatformPreviewShell";
import { PreviewValidationPanel } from "@/components/preview/PreviewValidationPanel";
import { isSupportedCombo } from "@/components/preview/previewPlatformConfig";

// ── Types ─────────────────────────────────────────────────────────────────────

type ViewMode = "month" | "week" | "list";
type EventCategory = "brief" | "teslim" | "onay" | "revizyon" | "yayin" | "toplanti" | "ajans_gorevi";

// ── Status vocabulary (closed, user-facing — never raw enum values) ──────────
//
// Merges CalendarItem statuses, Brief statuses, and Deliverable statuses into
// the same 9-bucket vocabulary so a mixed agenda (manual items + brief
// milestones + deliverable events) reads consistently.

const STATUS_META: Record<string, { label: string; chipClass: string; dot: string }> = {
  // CalendarItem
  planned:            { label: "Planlandı",     chipClass: "status-info",    dot: "bg-info" },
  in_design:          { label: "Üretimde",      chipClass: "status-purple",  dot: "bg-purple" },
  waiting_approval:   { label: "Onay Bekliyor", chipClass: "status-warning", dot: "bg-warning" },
  approved:           { label: "Onaylandı",     chipClass: "status-success", dot: "bg-success" },
  scheduled:          { label: "Yayına Hazır",  chipClass: "status-info",    dot: "bg-info" },
  published:          { label: "Yayınlandı",    chipClass: "status-success", dot: "bg-success" },
  cancelled:          { label: "İptal",         chipClass: "status-neutral", dot: "bg-text-muted/40" },
  // Brief
  draft:              { label: "Planlandı",     chipClass: "status-info",    dot: "bg-info" },
  submitted:          { label: "Onay Bekliyor", chipClass: "status-warning", dot: "bg-warning" },
  accepted:           { label: "Üretimde",      chipClass: "status-purple",  dot: "bg-purple" },
  in_production:      { label: "Üretimde",      chipClass: "status-purple",  dot: "bg-purple" },
  ready_for_review:   { label: "Onay Bekliyor", chipClass: "status-warning", dot: "bg-warning" },
  revision_requested: { label: "Revizyon İstendi", chipClass: "status-warning", dot: "bg-warning" },
  rejected:           { label: "İptal",         chipClass: "status-neutral", dot: "bg-text-muted/40" },
  completed:          { label: "Yayınlandı",    chipClass: "status-success", dot: "bg-success" },
  archived:           { label: "İptal",         chipClass: "status-neutral", dot: "bg-text-muted/40" },
  in_review:          { label: "Onay Bekliyor", chipClass: "status-warning", dot: "bg-warning" },
};

function getStatusMeta(status: string): { label: string; chipClass: string; dot: string } {
  return STATUS_META[status] ?? { label: "Planlandı", chipClass: "status-info", dot: "bg-info" };
}

const STATUS_FILTER_OPTIONS = [
  { value: "planned", label: "Planlandı" },
  { value: "in_production", label: "Üretimde" },
  { value: "waiting_approval", label: "Onay Bekliyor" },
  { value: "revision_requested", label: "Revizyon İstendi" },
  { value: "approved", label: "Onaylandı" },
  { value: "scheduled", label: "Yayına Hazır" },
  { value: "published", label: "Yayınlandı" },
  { value: "cancelled", label: "İptal" },
];

const EVENT_CATEGORY_OPTIONS: { value: EventCategory; label: string }[] = [
  { value: "brief", label: "Brief" },
  { value: "teslim", label: "Teslim" },
  { value: "onay", label: "Onay" },
  { value: "revizyon", label: "Revizyon" },
  { value: "yayin", label: "Yayın" },
  { value: "toplanti", label: "Toplantı" },
  { value: "ajans_gorevi", label: "Ajans Görevi" },
];

function getEventCategory(entry: AgencyCalendarEntry): EventCategory {
  switch (entry.source_type) {
    case "brief_start":
    case "first_draft":
      return "brief";
    case "brand_feedback":
    case "approval_deadline":
      return "onay";
    case "publish_date":
      return "yayin";
    case "deliverable_submitted":
      return "teslim";
    case "revision_requested":
      return "revizyon";
    default:
      if (entry.item_type === "meeting") return "toplanti";
      return entry.brand_id ? "yayin" : "ajans_gorevi";
  }
}

const PLATFORM_CONFIG: Record<
  CalendarPlatform,
  { label: string; color: string; abbr: string }
> = {
  instagram: { label: "Instagram", color: "text-pink-500", abbr: "IG" },
  facebook: { label: "Facebook", color: "text-blue-600", abbr: "FB" },
  tiktok: { label: "TikTok", color: "text-slate-800", abbr: "TK" },
  linkedin: { label: "LinkedIn", color: "text-blue-700", abbr: "LI" },
  x: { label: "X", color: "text-slate-900", abbr: "X" },
  youtube: { label: "YouTube", color: "text-red-600", abbr: "YT" },
  website: { label: "Website", color: "text-indigo-600", abbr: "WB" },
  email: { label: "E-posta", color: "text-orange-500", abbr: "EM" },
  other: { label: "Diğer", color: "text-text-muted", abbr: "—" },
};

const ITEM_TYPE_OPTIONS: { value: CalendarItemType; label: string }[] = [
  { value: "post", label: "Post" },
  { value: "story", label: "Story" },
  { value: "reels", label: "Reels" },
  { value: "video", label: "Video" },
  { value: "campaign", label: "Kampanya" },
  { value: "blog", label: "Blog" },
  { value: "email", label: "E-posta" },
  { value: "ad_creative", label: "Reklam Görseli" },
  { value: "meeting", label: "Toplantı" },
  { value: "custom", label: "Ajans İçi Görev" },
];

const PRIORITY_OPTIONS: { value: string; label: string }[] = [
  { value: "low", label: "Düşük" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "Yüksek" },
  { value: "urgent", label: "Acil" },
];

const PLATFORM_OPTIONS: { value: CalendarPlatform; label: string }[] = (
  Object.entries(PLATFORM_CONFIG) as [CalendarPlatform, { label: string; color: string; abbr: string }][]
).map(([value, cfg]) => ({ value, label: cfg.label }));

const WEEKDAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

// ── Helpers ───────────────────────────────────────────────────────────────────

function getMonthGrid(year: number, month: number): Date[][] {
  const firstDay = new Date(year, month - 1, 1);
  const lastDay = new Date(year, month, 0);

  let startDow = firstDay.getDay() - 1;
  if (startDow < 0) startDow = 6;

  const cells: Date[] = [];
  for (let i = startDow; i > 0; i--) {
    cells.push(new Date(year, month - 1, 1 - i));
  }
  for (let d = 1; d <= lastDay.getDate(); d++) {
    cells.push(new Date(year, month - 1, d));
  }
  while (cells.length < 42) {
    const extra = cells.length - lastDay.getDate() - startDow + 1;
    cells.push(new Date(year, month, extra));
  }

  const weeks: Date[][] = [];
  for (let i = 0; i < 42; i += 7) {
    weeks.push(cells.slice(i, i + 7));
  }
  return weeks;
}

function getWeekDays(year: number, week: number): Date[] {
  const jan1 = new Date(year, 0, 1);
  const jan1Dow = jan1.getDay() || 7;
  const monday = new Date(year, 0, 1 + (week - 1) * 7 - (jan1Dow - 1));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function formatDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Converts a UTC ISO timestamp to the local wall-clock value a
// `datetime-local` input expects. Slicing the raw ISO string instead would
// treat the UTC time as if it were already local, shifting it by the
// timezone offset (e.g. 3 hours in Turkey) on every read-and-resave.
function toLocalDateTimeInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Uses the browser's local calendar day, not the raw UTC date substring —
// an evening UTC timestamp (e.g. 22:13 UTC) falls on the next local day in
// Turkey (UTC+3), so slicing the ISO string would place it in the wrong cell.
function getItemDateKey(item: AgencyCalendarEntry): string | null {
  const raw = item.publish_at ?? item.due_at;
  if (!raw) return null;
  return formatDateKey(new Date(raw));
}

function getCurrentISOWeek(now = new Date()): { year: number; week: number } {
  const jan1 = new Date(now.getFullYear(), 0, 1);
  const dayOfYear = Math.floor((now.getTime() - jan1.getTime()) / 86400000) + 1;
  const jan1Dow = jan1.getDay() || 7;
  const week = Math.ceil((dayOfYear + jan1Dow - 1) / 7);
  return { year: now.getFullYear(), week };
}

// Deterministic pastel color per brand, used only as a small accent (left
// bar / dot) — never as a full-card fill — per the design rule that brand
// color must stay a minor accent, not dominate the status color.
function brandAccent(brandId: string | null): string {
  if (!brandId) return "hsl(220 10% 55%)"; // agency-internal: neutral slate
  let hash = 0;
  for (let i = 0; i < brandId.length; i++) hash = (hash * 31 + brandId.charCodeAt(i)) >>> 0;
  return `hsl(${hash % 360} 65% 55%)`;
}

// ── Status & platform badges ──────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cfg = getStatusMeta(status);
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${cfg.chipClass}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function PlatformAbbr({ platform }: { platform: string | null }) {
  if (!platform) return null;
  const cfg = PLATFORM_CONFIG[platform as CalendarPlatform] ?? PLATFORM_CONFIG.other;
  return (
    <span className={`text-[10px] font-bold leading-none ${cfg.color}`}>{cfg.abbr}</span>
  );
}

// ── Calendar chip ─────────────────────────────────────────────────────────────

function CalendarChip({
  item,
  onClick,
}: {
  item: AgencyCalendarEntry;
  onClick: (item: AgencyCalendarEntry) => void;
}) {
  const cfg = getStatusMeta(item.status);
  const brandLabel = item.brand_name ?? "Ajans İçi";
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick(item);
      }}
      style={{ borderLeftColor: brandAccent(item.brand_id) }}
      className={`w-full text-left pl-1.5 pr-1.5 py-[3px] rounded text-[11px] font-medium truncate leading-tight transition-opacity hover:opacity-75 flex items-center gap-1 border-l-2 ${cfg.chipClass} ${item.is_overdue ? "ring-1 ring-inset ring-danger/50" : ""}`}
      title={`${brandLabel} — ${item.title}`}
    >
      {!item.editable ? (
        <span className="text-[9px] font-bold opacity-70 flex-shrink-0">
          {item.item_type === "brief" ? "B" : item.item_type === "deliverable" ? "T" : "•"}
        </span>
      ) : (
        <PlatformAbbr platform={item.platform} />
      )}
      <span className="truncate">{item.title}</span>
      {item.is_overdue && <span className="w-1.5 h-1.5 rounded-full bg-danger flex-shrink-0" />}
    </button>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function CalendarSkeleton() {
  return (
    <div className="animate-pulse flex flex-col gap-px flex-1">
      <div className="grid grid-cols-7 gap-px mb-1">
        {WEEKDAYS.map((d) => (
          <div key={d} className="h-9 bg-surface-2 rounded-lg" />
        ))}
      </div>
      {Array.from({ length: 5 }).map((_, ri) => (
        <div key={ri} className="grid grid-cols-7 gap-px">
          {Array.from({ length: 7 }).map((_, ci) => (
            <div key={ci} className="h-28 bg-surface-2 rounded-xl" />
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Month view ────────────────────────────────────────────────────────────────

function MonthView({
  year,
  month,
  items,
  onItemClick,
}: {
  year: number;
  month: number;
  items: AgencyCalendarEntry[];
  onItemClick: (item: AgencyCalendarEntry) => void;
}) {
  const todayKey = formatDateKey(new Date());
  const weeks = useMemo(() => getMonthGrid(year, month), [year, month]);

  const itemsByDate = useMemo(() => {
    const map = new Map<string, AgencyCalendarEntry[]>();
    for (const item of items) {
      const key = getItemDateKey(item);
      if (!key) continue;
      const arr = map.get(key) ?? [];
      arr.push(item);
      map.set(key, arr);
    }
    return map;
  }, [items]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden border border-border rounded-xl">
      <div className="grid grid-cols-7 border-b border-border bg-surface-2">
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className="py-2.5 text-center text-[11px] font-semibold text-text-muted tracking-wider uppercase"
          >
            {d}
          </div>
        ))}
      </div>

      <div className="flex-1 grid grid-rows-6 overflow-hidden">
        {weeks.map((week, wi) => (
          <div
            key={wi}
            className="grid grid-cols-7 border-b border-border last:border-b-0"
          >
            {week.map((day, di) => {
              const key = formatDateKey(day);
              const isCurrentMonth = day.getMonth() === month - 1;
              const isToday = key === todayKey;
              const dayItems = itemsByDate.get(key) ?? [];

              return (
                <div
                  key={di}
                  className={`border-r border-border last:border-r-0 px-1.5 pt-1.5 pb-1 overflow-hidden ${
                    isCurrentMonth ? "bg-surface" : "bg-background/60"
                  } ${isToday ? "bg-accent-subtle/20" : ""}`}
                >
                  <span
                    className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] mb-1 font-medium ${
                      isToday
                        ? "bg-accent text-white"
                        : isCurrentMonth
                        ? "text-text"
                        : "text-text-muted/30"
                    }`}
                  >
                    {day.getDate()}
                  </span>
                  <div className="space-y-0.5">
                    {dayItems.slice(0, 4).map((item) => (
                      <CalendarChip key={item.id} item={item} onClick={onItemClick} />
                    ))}
                    {dayItems.length > 4 && (
                      <span className="block text-[10px] text-text-muted pl-1">
                        +{dayItems.length - 4} daha
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Week view ─────────────────────────────────────────────────────────────────

function WeekView({
  year,
  week,
  items,
  onItemClick,
}: {
  year: number;
  week: number;
  items: AgencyCalendarEntry[];
  onItemClick: (item: AgencyCalendarEntry) => void;
}) {
  const todayKey = formatDateKey(new Date());
  const days = useMemo(() => getWeekDays(year, week), [year, week]);

  const itemsByDate = useMemo(() => {
    const map = new Map<string, AgencyCalendarEntry[]>();
    for (const item of items) {
      const key = getItemDateKey(item);
      if (!key) continue;
      const arr = map.get(key) ?? [];
      arr.push(item);
      map.set(key, arr);
    }
    return map;
  }, [items]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden border border-border rounded-xl">
      <div className="grid grid-cols-7 border-b border-border bg-surface-2">
        {days.map((day, i) => {
          const key = formatDateKey(day);
          const isToday = key === todayKey;
          return (
            <div
              key={i}
              className={`py-3 text-center border-r border-border last:border-r-0 ${
                isToday ? "bg-accent-subtle/30" : ""
              }`}
            >
              <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">
                {WEEKDAYS[i]}
              </p>
              <p
                className={`text-xl font-bold mt-0.5 ${
                  isToday ? "text-accent" : "text-text"
                }`}
              >
                {day.getDate()}
              </p>
              <p className="text-[10px] text-text-muted">
                {day.toLocaleDateString("tr-TR", { month: "short" })}
              </p>
            </div>
          );
        })}
      </div>
      <div className="flex-1 grid grid-cols-7 overflow-auto">
        {days.map((day, i) => {
          const key = formatDateKey(day);
          const dayItems = itemsByDate.get(key) ?? [];
          const isToday = key === todayKey;
          return (
            <div
              key={i}
              className={`border-r border-border last:border-r-0 p-2 space-y-1 min-h-[320px] ${
                isToday ? "bg-accent-subtle/10" : "bg-surface"
              }`}
            >
              {dayItems.map((item) => (
                <CalendarChip key={item.id} item={item} onClick={onItemClick} />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── List view ─────────────────────────────────────────────────────────────────

function ListView({
  items,
  onItemClick,
}: {
  items: AgencyCalendarEntry[];
  onItemClick: (item: AgencyCalendarEntry) => void;
}) {
  const sorted = useMemo(
    () =>
      [...items].sort((a, b) => {
        const da = a.publish_at ?? a.due_at ?? a.created_at ?? "";
        const db = b.publish_at ?? b.due_at ?? b.created_at ?? "";
        return da.localeCompare(db);
      }),
    [items]
  );

  const groups = useMemo(() => {
    const map = new Map<string, AgencyCalendarEntry[]>();
    for (const item of sorted) {
      const key = getItemDateKey(item) ?? "tarihsiz";
      const arr = map.get(key) ?? [];
      arr.push(item);
      map.set(key, arr);
    }
    return Array.from(map.entries());
  }, [sorted]);

  return (
    <div className="flex-1 overflow-auto space-y-6">
      {groups.map(([dateKey, groupItems]) => (
        <div key={dateKey}>
          <div className="flex items-center gap-3 mb-2 sticky top-0 bg-background py-1 z-10">
            <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider whitespace-nowrap">
              {dateKey === "tarihsiz"
                ? "Tarihi Belirsiz"
                : new Date(dateKey + "T12:00:00").toLocaleDateString("tr-TR", {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}
            </span>
            <div className="flex-1 h-px bg-border" />
            <span className="text-[11px] text-text-muted">{groupItems.length}</span>
          </div>
          <div className="space-y-2">
            {groupItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onItemClick(item)}
                style={{ borderLeftColor: brandAccent(item.brand_id) }}
                className="w-full text-left bg-surface border border-border border-l-2 rounded-xl px-4 py-3 hover:border-accent/40 hover:shadow-sm transition-all group"
              >
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wide">
                        {item.brand_name ?? "Ajans İçi"}
                      </span>
                      <span className="text-sm font-medium text-text group-hover:text-accent transition-colors">
                        {item.title}
                      </span>
                      <StatusBadge status={item.status} />
                      {item.is_overdue && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-danger/10 text-danger">
                          Geciken
                        </span>
                      )}
                    </div>
                    {item.description && (
                      <p className="text-xs text-text-muted mt-0.5 line-clamp-1">
                        {item.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {item.platform && (
                      <span
                        className={`text-xs font-semibold ${
                          PLATFORM_CONFIG[item.platform as CalendarPlatform]?.color ??
                          "text-text-muted"
                        }`}
                      >
                        {PLATFORM_CONFIG[item.platform as CalendarPlatform]?.label ??
                          item.platform}
                      </span>
                    )}
                    {item.publish_at && (
                      <span className="text-xs text-text-muted tabular-nums">
                        {new Date(item.publish_at).toLocaleTimeString("tr-TR", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                    <svg
                      className="w-4 h-4 text-text-muted/40 group-hover:text-accent/60 transition-colors"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyCalendar({ onAdd, noBrands, hasFilters, onClearFilters }: {
  onAdd: () => void;
  noBrands: boolean;
  hasFilters: boolean;
  onClearFilters: () => void;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-20">
      <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
        <svg
          className="w-8 h-8 text-text-muted/40"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-text mb-1">
        {noBrands ? "Henüz marka yok" : "Bu dönemde planlanmış kayıt bulunmuyor"}
      </h3>
      <p className="text-sm text-text-muted mb-5 text-center max-w-xs">
        {noBrands
          ? "Takvime başlayabilmek için önce bir marka ekleyin."
          : "Brief tarihlerini, teslimleri ve ajans içi görevleri tek takvimde yönetin."}
      </p>
      <div className="flex items-center gap-2">
        {hasFilters && (
          <button
            onClick={onClearFilters}
            className="inline-flex items-center gap-2 px-4 py-2.5 border border-border text-text rounded-lg text-sm font-medium hover:bg-surface-2 transition-colors"
          >
            Filtreleri Temizle
          </button>
        )}
        {!noBrands && (
          <button
            onClick={onAdd}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Yeni Kayıt Oluştur
          </button>
        )}
      </div>
    </div>
  );
}

// ── Item form modal (manual, editable entries only) ──────────────────────────

interface ItemFormProps {
  isOpen: boolean;
  onClose: () => void;
  initialItem: AgencyCalendarEntry | null;
  agencyId: string;
  accessToken: string;
  brands: BrandRead[];
  defaultBrandId?: string;
  onSaved: () => void;
}

function ItemFormModal({
  isOpen,
  onClose,
  initialItem,
  agencyId,
  accessToken,
  brands,
  defaultBrandId,
  onSaved,
}: ItemFormProps) {
  const isEdit = !!initialItem;
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [brandId, setBrandId] = useState<string>("");
  const [itemType, setItemType] = useState<CalendarItemType>("post");
  const [platform, setPlatform] = useState<CalendarPlatform>("other");
  const [status, setStatus] = useState<CalendarItemStatus>("planned");
  const [priority, setPriority] = useState<string>("normal");
  const [allDay, setAllDay] = useState(false);
  const [publishAt, setPublishAt] = useState("");
  const [dueAt, setDueAt] = useState("");

  // ── Platform preview (Social Media Preview Center) — read-only, only shown
  // when this calendar entry is linked back to a real Deliverable that has a
  // preview config already configured on the brief detail workspace. ─────────
  const [previewConfig, setPreviewConfig] = useState<PreviewConfigRead | null>(null);
  const [previewSlots, setPreviewSlots] = useState<PreviewSlotRead[]>([]);
  const [previewAvailable, setPreviewAvailable] = useState(false);

  useEffect(() => {
    setPreviewConfig(null);
    setPreviewSlots([]);
    setPreviewAvailable(false);
    if (!isOpen || !initialItem?.deliverable_id || !initialItem?.brief_id) return;
    let cancelled = false;
    deliverablePreviewApi.getConfig(initialItem.brief_id, initialItem.deliverable_id, accessToken, agencyId)
      .then(async (cfg) => {
        if (cancelled) return;
        const slots = await deliverablePreviewApi.listSlots(
          initialItem.brief_id!, initialItem.deliverable_id!, accessToken, agencyId,
        );
        if (cancelled) return;
        setPreviewConfig(cfg);
        setPreviewSlots(slots);
        setPreviewAvailable(isSupportedCombo(cfg.platform, cfg.preview_format));
      })
      .catch(() => { /* no preview configured for this deliverable yet — tab stays hidden */ });
    return () => { cancelled = true; };
  }, [isOpen, initialItem, accessToken, agencyId]);

  useEffect(() => {
    if (!isOpen) return;
    if (initialItem) {
      setTitle(initialItem.title);
      setDescription(initialItem.description ?? "");
      setBrandId(initialItem.brand_id ?? "");
      setItemType(initialItem.item_type as CalendarItemType);
      setPlatform((initialItem.platform as CalendarPlatform) ?? "other");
      setStatus(initialItem.status as CalendarItemStatus);
      setPriority(initialItem.priority || "normal");
      const localPublish = toLocalDateTimeInput(initialItem.publish_at);
      const localDue = toLocalDateTimeInput(initialItem.due_at);
      setPublishAt(localPublish);
      setDueAt(localDue);
      // Best-effort guess: a record whose only set time(s) land exactly on
      // local midnight was most likely created as an all-day entry.
      const isMidnight = (v: string) => v !== "" && v.endsWith("T00:00");
      setAllDay(
        (localPublish === "" || isMidnight(localPublish)) &&
          (localDue === "" || isMidnight(localDue)) &&
          (localPublish !== "" || localDue !== "")
      );
    } else {
      setTitle("");
      setDescription("");
      setBrandId(defaultBrandId ?? "");
      setItemType("post");
      setPlatform("other");
      setStatus("planned");
      setPriority("normal");
      setAllDay(false);
      setPublishAt("");
      setDueAt("");
    }
    setFormError(null);
    setSaving(false);
    setDeleting(false);
  }, [isOpen, initialItem, defaultBrandId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        title: title.trim(),
        description: description.trim() || null,
        brand_id: brandId || null,
        item_type: itemType,
        platform,
        status,
        priority,
        publish_at: publishAt ? new Date(publishAt).toISOString() : null,
        due_at: dueAt ? new Date(dueAt).toISOString() : null,
      };
      if (isEdit && initialItem?.calendar_item_id) {
        await calendarApi.update(
          initialItem.calendar_item_id,
          payload as CalendarItemUpdate,
          agencyId,
          accessToken
        );
      } else {
        await calendarApi.create(payload as CalendarItemCreate, agencyId, accessToken);
      }
      onSaved();
      onClose();
    } catch {
      setFormError("Kaydedilemedi. Lütfen tekrar deneyin.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!initialItem?.calendar_item_id) return;
    setDeleting(true);
    setFormError(null);
    try {
      await calendarApi.delete(initialItem.calendar_item_id, agencyId, accessToken);
      onSaved();
      onClose();
    } catch {
      setFormError("Silinemedi. Lütfen tekrar deneyin.");
    } finally {
      setDeleting(false);
    }
  };

  const handleQuickStatus = async (newStatus: CalendarItemStatus) => {
    if (!initialItem?.calendar_item_id) return;
    setFormError(null);
    try {
      await calendarApi.changeStatus(
        initialItem.calendar_item_id,
        { new_status: newStatus },
        agencyId,
        accessToken
      );
      setStatus(newStatus);
      onSaved();
    } catch {
      setFormError("Durum güncellenemedi.");
    }
  };

  // Switching to all-day snaps existing date/time values to local midnight,
  // keeping the date portion; switching back leaves the time at 00:00 for
  // the user to adjust rather than guessing a time.
  const handleAllDayToggle = (checked: boolean) => {
    setAllDay(checked);
    if (checked) {
      if (publishAt) setPublishAt(`${publishAt.slice(0, 10)}T00:00`);
      if (dueAt) setDueAt(`${dueAt.slice(0, 10)}T00:00`);
    }
  };

  const STATUS_QUICK: CalendarItemStatus[] = [
    "planned", "in_design", "waiting_approval", "approved", "scheduled", "published", "cancelled",
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? "Kaydı Düzenle" : "Yeni Kayıt"}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Title */}
        <div>
          <label htmlFor="cal-item-title" className="block text-xs font-medium text-text-muted mb-1">
            Başlık <span className="text-red-500">*</span>
          </label>
          <input
            id="cal-item-title"
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Kayıt başlığı…"
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="cal-item-description" className="block text-xs font-medium text-text-muted mb-1">
            Açıklama
          </label>
          <textarea
            id="cal-item-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Kısa açıklama veya not…"
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors resize-none"
          />
        </div>

        {/* Brand */}
        <div>
          <label htmlFor="cal-item-brand" className="block text-xs font-medium text-text-muted mb-1">
            Marka
          </label>
          <select
            id="cal-item-brand"
            value={brandId}
            onChange={(e) => setBrandId(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
          >
            <option value="">Ajans İçi</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </div>

        {/* Type + Platform + Priority */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label htmlFor="cal-item-type" className="block text-xs font-medium text-text-muted mb-1">
              Kayıt Tipi
            </label>
            <select
              id="cal-item-type"
              value={itemType}
              onChange={(e) => setItemType(e.target.value as CalendarItemType)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            >
              {ITEM_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="cal-item-platform" className="block text-xs font-medium text-text-muted mb-1">
              Platform
            </label>
            <select
              id="cal-item-platform"
              value={platform}
              onChange={(e) => setPlatform(e.target.value as CalendarPlatform)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            >
              {PLATFORM_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="cal-item-priority" className="block text-xs font-medium text-text-muted mb-1">
              Öncelik
            </label>
            <select
              id="cal-item-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            >
              {PRIORITY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Status: quick-change pills when editing (audit-logged), plain select on create */}
        <div>
          <label className="block text-xs font-medium text-text-muted mb-2">
            Durum
          </label>
          {isEdit ? (
            <div className="flex flex-wrap gap-1.5">
              {STATUS_QUICK.map((s) => {
                const cfg = getStatusMeta(s);
                const isActive = status === s;
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleQuickStatus(s)}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all ${
                      isActive
                        ? `${cfg.chipClass} ring-2 ring-offset-1 ring-current/40`
                        : "bg-surface-2 text-text-muted hover:bg-surface-2/70"
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                    {cfg.label}
                  </button>
                );
              })}
            </div>
          ) : (
            <select
              id="cal-item-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as CalendarItemStatus)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            >
              {STATUS_QUICK.map((s) => (
                <option key={s} value={s}>
                  {getStatusMeta(s).label}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* All-day toggle */}
        <label htmlFor="cal-item-all-day" className="flex items-center gap-2 text-sm text-text cursor-pointer w-fit">
          <input
            id="cal-item-all-day"
            type="checkbox"
            checked={allDay}
            onChange={(e) => handleAllDayToggle(e.target.checked)}
            className="w-4 h-4 rounded border-border text-accent focus:ring-accent/30"
          />
          Tüm gün
        </label>

        {/* Dates */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="cal-item-publish-at" className="block text-xs font-medium text-text-muted mb-1">
              Yayın Tarihi
            </label>
            <input
              id="cal-item-publish-at"
              type={allDay ? "date" : "datetime-local"}
              value={allDay ? publishAt.slice(0, 10) : publishAt}
              onChange={(e) =>
                setPublishAt(allDay ? (e.target.value ? `${e.target.value}T00:00` : "") : e.target.value)
              }
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            />
          </div>
          <div>
            <label htmlFor="cal-item-due-at" className="block text-xs font-medium text-text-muted mb-1">
              Teslim Tarihi
            </label>
            <input
              id="cal-item-due-at"
              type={allDay ? "date" : "datetime-local"}
              value={allDay ? dueAt.slice(0, 10) : dueAt}
              onChange={(e) =>
                setDueAt(allDay ? (e.target.value ? `${e.target.value}T00:00` : "") : e.target.value)
              }
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            />
          </div>
        </div>

        {previewAvailable && previewConfig && (
          <div className="space-y-2 border-t border-border pt-4">
            <p className="text-xs font-medium text-text-muted">Platform Önizlemesi</p>
            <PlatformPreviewShell
              config={previewConfig}
              slots={previewSlots}
              accessToken={accessToken}
              annotations={[]}
              readOnly
            />
            <PreviewValidationPanel warnings={previewConfig.warnings} />
          </div>
        )}

        {formError && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
            {formError}
          </p>
        )}

        <div className="flex items-center gap-2 pt-1 border-t border-border">
          {isEdit && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting || saving}
              className="px-3 py-2 rounded-lg text-sm text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors disabled:opacity-40"
            >
              {deleting ? "Siliniyor…" : "Sil"}
            </button>
          )}
          <div className="flex-1" />
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
          >
            İptal
          </button>
          <button
            type="submit"
            disabled={saving || !title.trim()}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {saving ? "Kaydediliyor…" : isEdit ? "Kaydet" : "Oluştur"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const router = useRouter();

  const now = new Date();
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [week, setWeek] = useState(getCurrentISOWeek().week);

  const [filterBrand, setFilterBrand] = useState(""); // "" | "internal" | brandId
  const [filterPlatform, setFilterPlatform] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterEventCategory, setFilterEventCategory] = useState<EventCategory | "">("");

  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [items, setItems] = useState<AgencyCalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<AgencyCalendarEntry | null>(null);

  // The month grid needs real horizontal room per day cell; below that it
  // degrades to unreadable dots. List view has no such constraint, so it's
  // the usable default on narrow (mobile) viewports.
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setViewMode("list");
    }
  }, []);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi.listBrands(agencyId, accessToken).then(setBrands).catch(() => setBrands([]));
  }, [accessToken, agencyId]);

  // Fetch window: month/week views bound to the visible grid (incl. spillover
  // days from adjacent months) so only the visible range is requested; list
  // view uses a wider rolling window since it isn't tied to a single grid.
  const dateRange = useMemo(() => {
    if (viewMode === "month") {
      const weeks = getMonthGrid(year, month);
      return { from: formatDateKey(weeks[0][0]), to: formatDateKey(weeks[5][6]) };
    }
    if (viewMode === "week") {
      const days = getWeekDays(year, week);
      return { from: formatDateKey(days[0]), to: formatDateKey(days[6]) };
    }
    const start = new Date(now.getFullYear(), now.getMonth() - 3, 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 6, 0);
    return { from: formatDateKey(start), to: formatDateKey(end) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, year, month, week]);

  const serverFilters = useMemo(
    () => ({
      from: dateRange.from,
      to: dateRange.to,
      ...(filterBrand ? { brand_id: filterBrand } : {}),
    }),
    [dateRange, filterBrand]
  );

  const fetchItems = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setFetchError(null);
    try {
      const data = await calendarApi.agenda(agencyId, accessToken, serverFilters);
      setItems(data);
    } catch {
      setFetchError("Takvim yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, serverFilters]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !agencyId) {
      setLoading(false);
    }
  }, [workspaceReady, workspaceLoading, agencyId]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Client-side filters not supported server-side as an exact match: event
  // category (a many-to-one grouping over source_type), platform (only
  // meaningful for manual entries), and status — Brief/Deliverable sources
  // carry their own status enums (e.g. "in_review") that are distinct from
  // CalendarItem's (e.g. "waiting_approval") but render as the same visible
  // bucket ("Onay Bekliyor"), so the filter has to match on that bucket
  // rather than the raw value an exact server-side match would require.
  const visibleItems = useMemo(() => {
    const statusLabel = filterStatus ? getStatusMeta(filterStatus).label : null;
    return items.filter((item) => {
      if (statusLabel && getStatusMeta(item.status).label !== statusLabel) return false;
      if (filterEventCategory && getEventCategory(item) !== filterEventCategory) return false;
      if (filterPlatform && item.platform !== filterPlatform) return false;
      return true;
    });
  }, [items, filterStatus, filterEventCategory, filterPlatform]);

  const handlePrev = () => {
    if (viewMode === "month") {
      if (month === 1) {
        setMonth(12);
        setYear((y) => y - 1);
      } else {
        setMonth((m) => m - 1);
      }
    } else if (viewMode === "week") {
      if (week === 1) {
        setWeek(52);
        setYear((y) => y - 1);
      } else {
        setWeek((w) => w - 1);
      }
    }
  };

  const handleNext = () => {
    if (viewMode === "month") {
      if (month === 12) {
        setMonth(1);
        setYear((y) => y + 1);
      } else {
        setMonth((m) => m + 1);
      }
    } else if (viewMode === "week") {
      if (week === 52) {
        setWeek(1);
        setYear((y) => y + 1);
      } else {
        setWeek((w) => w + 1);
      }
    }
  };

  const handleToday = () => {
    const n = new Date();
    setYear(n.getFullYear());
    setMonth(n.getMonth() + 1);
    setWeek(getCurrentISOWeek(n).week);
  };

  const periodLabel = useMemo(() => {
    if (viewMode === "month") {
      return new Date(year, month - 1, 1).toLocaleDateString("tr-TR", {
        month: "long",
        year: "numeric",
      });
    }
    if (viewMode === "week") {
      const days = getWeekDays(year, week);
      const start = days[0].toLocaleDateString("tr-TR", {
        day: "numeric",
        month: "short",
      });
      const end = days[6].toLocaleDateString("tr-TR", {
        day: "numeric",
        month: "short",
      });
      return `${start} – ${end}, ${year}`;
    }
    return "Tüm Kayıtlar";
  }, [viewMode, year, month, week]);

  const hasFilters = !!(filterBrand || filterPlatform || filterStatus || filterEventCategory);
  const noBrands = brands.length === 0;

  const clearFilters = () => {
    setFilterBrand("");
    setFilterPlatform("");
    setFilterStatus("");
    setFilterEventCategory("");
  };

  const openCreate = () => {
    setEditingItem(null);
    setModalOpen(true);
  };

  const openEdit = (item: AgencyCalendarEntry) => {
    if (item.editable && item.calendar_item_id) {
      setEditingItem(item);
      setModalOpen(true);
      return;
    }
    if (item.action_url) {
      router.push(item.action_url);
    }
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background">
      {/* ── Header ── */}
      <div className="flex-shrink-0 bg-surface border-b border-border px-8 pt-6 pb-4">
        <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
          <div>
            <h1 className="text-xl font-semibold text-text">İçerik ve Operasyon Takvimi</h1>
            <p className="text-sm text-text-muted mt-0.5">
              {loading ? "Yükleniyor…" : `${visibleItems.length} kayıt`}
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* View mode */}
            <div className="flex items-center bg-surface-2 rounded-lg p-0.5">
              {(["month", "week", "list"] as ViewMode[]).map((v) => {
                const labels: Record<ViewMode, string> = {
                  month: "Ay",
                  week: "Hafta",
                  list: "Liste",
                };
                return (
                  <button
                    key={v}
                    onClick={() => setViewMode(v)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      viewMode === v
                        ? "bg-surface text-text shadow-sm"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {labels[v]}
                  </button>
                );
              })}
            </div>

            {/* Brand filter */}
            <select
              value={filterBrand}
              onChange={(e) => setFilterBrand(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-surface text-xs text-text focus:outline-none focus:ring-2 focus:ring-accent/30"
            >
              <option value="">Tüm Markalar</option>
              <option value="internal">Ajans İçi</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>

            {/* Event category filter */}
            <select
              value={filterEventCategory}
              onChange={(e) => setFilterEventCategory(e.target.value as EventCategory | "")}
              className="px-3 py-1.5 rounded-lg border border-border bg-surface text-xs text-text focus:outline-none focus:ring-2 focus:ring-accent/30"
            >
              <option value="">Tüm Olay Tipleri</option>
              {EVENT_CATEGORY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            {/* Platform filter */}
            <select
              value={filterPlatform}
              onChange={(e) => setFilterPlatform(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-surface text-xs text-text focus:outline-none focus:ring-2 focus:ring-accent/30"
            >
              <option value="">Tüm Platformlar</option>
              {PLATFORM_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>

            {/* Status filter */}
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-surface text-xs text-text focus:outline-none focus:ring-2 focus:ring-accent/30"
            >
              <option value="">Tüm Durumlar</option>
              {STATUS_FILTER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>

            {hasFilters && (
              <button
                onClick={clearFilters}
                className="text-xs text-text-muted hover:text-accent transition-colors px-1"
              >
                Temizle
              </button>
            )}

            {/* Create */}
            {!noBrands && (
              <button
                onClick={openCreate}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors shadow-sm"
              >
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Yeni Kayıt
              </button>
            )}
          </div>
        </div>

        {/* Period nav */}
        {viewMode !== "list" && (
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrev}
              className="w-7 h-7 flex items-center justify-center rounded-lg border border-border text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
            <button
              onClick={handleToday}
              className="text-xs font-medium text-text-muted hover:text-accent transition-colors px-2 py-1 rounded-lg hover:bg-surface-2"
            >
              Bugün
            </button>
            <button
              onClick={handleNext}
              className="w-7 h-7 flex items-center justify-center rounded-lg border border-border text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
            <h2 className="text-sm font-semibold text-text capitalize ml-1">
              {periodLabel}
            </h2>
          </div>
        )}

        {/* Status legend */}
        <div className="flex items-center gap-4 mt-3 overflow-x-auto pb-0.5">
          {STATUS_FILTER_OPTIONS.map((o) => {
            const cfg = getStatusMeta(o.value);
            return (
              <span
                key={o.value}
                className="flex items-center gap-1.5 whitespace-nowrap"
              >
                <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                <span className="text-[11px] text-text-muted">{cfg.label}</span>
              </span>
            );
          })}
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-hidden flex flex-col px-8 py-5 min-h-0">
        {!loading && !agencyId ? (
          <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-text-muted/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-text mb-1">Ajans seçilmedi</h3>
            <p className="text-sm text-text-muted mb-5 max-w-xs">Takvimi görüntülemek için bir ajans seçin.</p>
            <a href="/onboarding/create-agency" className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors shadow-sm">Ajans Oluştur</a>
          </div>
        ) : fetchError ? (
          <div className="rounded-xl border border-danger/20 bg-danger/10 px-5 py-4 text-sm text-danger flex items-center gap-3">
            <span>{fetchError}</span>
            <button
              onClick={fetchItems}
              className="underline hover:no-underline"
            >
              Tekrar dene
            </button>
          </div>
        ) : loading ? (
          <CalendarSkeleton />
        ) : visibleItems.length === 0 ? (
          <EmptyCalendar
            onAdd={openCreate}
            noBrands={noBrands && !hasFilters}
            hasFilters={hasFilters}
            onClearFilters={clearFilters}
          />
        ) : (
          <>
            {viewMode === "month" && (
              <MonthView
                year={year}
                month={month}
                items={visibleItems}
                onItemClick={openEdit}
              />
            )}
            {viewMode === "week" && (
              <WeekView
                year={year}
                week={week}
                items={visibleItems}
                onItemClick={openEdit}
              />
            )}
            {viewMode === "list" && <ListView items={visibleItems} onItemClick={openEdit} />}
          </>
        )}
      </div>

      {/* ── Modal ── */}
      {agencyId && accessToken && (
        <ItemFormModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          initialItem={editingItem}
          agencyId={agencyId}
          accessToken={accessToken}
          brands={brands}
          defaultBrandId={filterBrand && filterBrand !== "internal" ? filterBrand : undefined}
          onSaved={fetchItems}
        />
      )}
    </div>
  );
}
