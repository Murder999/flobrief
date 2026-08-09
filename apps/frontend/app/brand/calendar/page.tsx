"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import {
  brandPortalApi,
  type BrandCalendarEntry,
  type BriefRead,
} from "@/lib/api-client";
import { Select } from "@/components/ui/select";
import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Calendar,
  AlertCircle,
  Clock,
  List,
  Users,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { EVENT_TYPE_CFG, STATUS_CFG, PRIORITY_CFG } from "@/components/brand-calendar/labels";

const DAYS_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const MONTHS_TR = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildMonthGrid(year: number, month: number): (Date | null)[][] {
  const firstDay = new Date(year, month, 1);
  let startDow = firstDay.getDay();
  startDow = startDow === 0 ? 6 : startDow - 1;

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const grid: (Date | null)[][] = [];
  let row: (Date | null)[] = Array(startDow).fill(null);

  for (let d = 1; d <= daysInMonth; d++) {
    row.push(new Date(year, month, d));
    if (row.length === 7) { grid.push(row); row = []; }
  }
  if (row.length > 0) {
    while (row.length < 7) row.push(null);
    grid.push(row);
  }
  return grid;
}

function buildWeekGrid(anchor: Date): Date[] {
  const dow = anchor.getDay() === 0 ? 6 : anchor.getDay() - 1;
  const monday = new Date(anchor);
  monday.setDate(anchor.getDate() - dow);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function entryDate(entry: BrandCalendarEntry): Date {
  return new Date(`${entry.entry_date}T00:00:00`);
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function CalSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-surface-2 rounded w-48 mb-4" />
      <div className="grid grid-cols-7 gap-px bg-border rounded-xl overflow-hidden">
        {Array.from({ length: 35 }).map((_, i) => (
          <div key={i} className="bg-surface h-24" />
        ))}
      </div>
    </div>
  );
}

// ── Entry chip (day cell) ────────────────────────────────────────────────────

function EntryChip({ entry }: { entry: BrandCalendarEntry }) {
  const cfg = EVENT_TYPE_CFG[entry.event_type] ?? EVENT_TYPE_CFG.custom;
  const chip = (
    <div className={cn(
      "flex items-center gap-1 px-1.5 py-0.5 rounded-md border text-[10px] font-medium truncate cursor-pointer",
      "hover:ring-1 hover:ring-accent/30 transition-all",
      cfg.chip,
    )}>
      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", cfg.dot)} />
      <span className="truncate">{entry.title}</span>
    </div>
  );
  if (entry.brief_id) return <Link href={`/brand/briefs/${entry.brief_id}`}>{chip}</Link>;
  return chip;
}

// ── Day Cell ──────────────────────────────────────────────────────────────────

function DayCell({
  date,
  entries,
  isToday,
  isCurrentMonth,
  onSelect,
}: {
  date: Date | null;
  entries: BrandCalendarEntry[];
  isToday: boolean;
  isCurrentMonth: boolean;
  onSelect: (date: Date, entries: BrandCalendarEntry[]) => void;
}) {
  if (!date) return <div className="bg-surface/40 min-h-[88px]" />;

  const hasEntries = entries.length > 0;
  const visible = entries.slice(0, 2);
  const overflow = entries.length - visible.length;

  return (
    <div
      className={cn(
        "bg-surface min-h-[88px] p-1.5 transition-colors",
        hasEntries ? "cursor-pointer hover:bg-surface-2/50" : "",
        !isCurrentMonth && "opacity-40",
      )}
      onClick={() => hasEntries && onSelect(date, entries)}
    >
      <span className={cn(
        "inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium mb-1",
        isToday ? "bg-gradient-accent text-white text-[11px]" : "text-text-muted",
      )}>
        {date.getDate()}
      </span>
      <div className="space-y-0.5">
        {visible.map((entry) => (
          <EntryChip key={entry.id} entry={entry} />
        ))}
        {overflow > 0 && (
          <span className="text-[10px] text-text-muted pl-1">+{overflow} daha</span>
        )}
      </div>
    </div>
  );
}

// ── Day Drawer (grouped premium detail panel) ───────────────────────────────

function DayDrawer({
  date,
  entries,
  onClose,
}: {
  date: Date;
  entries: BrandCalendarEntry[];
  onClose: () => void;
}) {
  const dayLabel = date.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric", weekday: "long" });

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-96 bg-surface border-l border-border shadow-modal flex flex-col">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div>
          <p className="text-sm font-semibold text-text capitalize">{dayLabel}</p>
          <p className="text-xs text-text-muted mt-0.5">{entries.length} kayıt</p>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {entries.map((entry) => {
          const evCfg = EVENT_TYPE_CFG[entry.event_type] ?? EVENT_TYPE_CFG.custom;
          const stCfg = STATUS_CFG[entry.status] ?? STATUS_CFG.planned;
          const prCfg = PRIORITY_CFG[entry.priority] ?? PRIORITY_CFG.normal;
          return (
            <div key={entry.id} className="bg-surface-2 border border-border rounded-xl p-4">
              <div className="flex items-start gap-2.5 mb-2.5">
                <span className={cn("w-2 h-2 rounded-full mt-1.5 flex-shrink-0", evCfg.dot)} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text leading-tight">{entry.title}</p>
                  {entry.entry_time && (
                    <p className="text-xs text-text-muted mt-0.5 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(entry.entry_time).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-2.5">
                <span className={cn("text-[11px] px-2 py-0.5 rounded-md border", evCfg.chip)}>{evCfg.label}</span>
                <span className={cn("text-[11px] px-2 py-0.5 rounded-md border", stCfg.chip)}>{stCfg.label}</span>
                <span className={cn("text-[11px] px-2 py-0.5 rounded-md font-medium", prCfg.className)}>{prCfg.label}</span>
              </div>
              {entry.assignee_names.length > 0 && (
                <div className="flex items-center gap-1.5 text-[11px] text-text-muted mb-2.5">
                  <Users className="w-3 h-3" />
                  {entry.assignee_names.join(", ")}
                </div>
              )}
              {entry.brief_id && (
                <Link
                  href={`/brand/briefs/${entry.brief_id}`}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-accent hover:bg-accent/90 px-3 py-1.5 rounded-lg transition-colors"
                >
                  {entry.brief_title ? `${entry.brief_title} — Detaya git` : "Brief'e git"} →
                </Link>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── List / Agenda View ───────────────────────────────────────────────────────

function ListView({ entries }: { entries: BrandCalendarEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center py-16 text-center">
        <Calendar className="w-10 h-10 text-text-muted/30 mb-3" />
        <p className="text-sm font-medium text-text mb-1">Bu aralıkta içerik yok</p>
        <p className="text-xs text-text-muted">Ajans içerik planladığında burada görünecek.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => {
        const d = entryDate(entry);
        const evCfg = EVENT_TYPE_CFG[entry.event_type] ?? EVENT_TYPE_CFG.custom;
        const stCfg = STATUS_CFG[entry.status] ?? STATUS_CFG.planned;
        const row = (
          <div className="bg-surface border border-border rounded-xl p-4 flex items-center gap-4 hover:border-border-hover transition-colors group">
            <div className="text-center w-10 flex-shrink-0">
              <p className="text-lg font-bold text-text leading-none">{d.getDate()}</p>
              <p className="text-[10px] text-text-muted uppercase">{MONTHS_TR[d.getMonth()].slice(0, 3)}</p>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text truncate group-hover:text-accent transition-colors">{entry.title}</p>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                <span className={cn("inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded-md border", evCfg.chip)}>
                  <span className={cn("w-1 h-1 rounded-full", evCfg.dot)} />
                  {evCfg.label}
                </span>
                <span className={cn("inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded-md border", stCfg.chip)}>
                  {stCfg.label}
                </span>
              </div>
            </div>
            {entry.brief_id && (
              <ChevronRight className="w-4 h-4 text-text-muted group-hover:text-accent transition-colors flex-shrink-0" />
            )}
          </div>
        );
        return entry.brief_id ? (
          <Link key={entry.id} href={`/brand/briefs/${entry.brief_id}`}>{row}</Link>
        ) : (
          <div key={entry.id}>{row}</div>
        );
      })}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

type ViewMode = "month" | "week" | "list";

export default function BrandCalendarPage() {
  const { accessToken } = useAuth();
  const [entries, setEntries] = useState<BrandCalendarEntry[] | null>(null);
  const [briefs, setBriefs] = useState<BriefRead[]>([]);
  const [error, setError] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [weekAnchor, setWeekAnchor] = useState(today);
  const [selectedDay, setSelectedDay] = useState<{ date: Date; entries: BrandCalendarEntry[] } | null>(null);

  // Filters
  const [fStatus, setFStatus] = useState("");
  const [fEventType, setFEventType] = useState("");
  const [fPriority, setFPriority] = useState("");
  const [fBriefId, setFBriefId] = useState("");
  const [fAssignee, setFAssignee] = useState("");

  const loadData = useCallback(async () => {
    if (!accessToken) return;
    try {
      const from = new Date(today.getFullYear(), today.getMonth() - 6, 1).toISOString().split("T")[0];
      const to = new Date(today.getFullYear(), today.getMonth() + 6, 31).toISOString().split("T")[0];
      const [calRes, briefRes] = await Promise.all([
        brandPortalApi.listCalendar(accessToken, { from, to }),
        brandPortalApi.listBriefs(accessToken, { limit: 200 }),
      ]);
      setEntries(Array.isArray(calRes) ? calRes : []);
      setBriefs(briefRes.items ?? []);
    } catch {
      setError(true);
      setEntries([]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  useEffect(() => { loadData(); }, [loadData]);

  const assigneeOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of entries ?? []) {
      e.assignee_ids.forEach((id, i) => map.set(id, e.assignee_names[i] ?? id));
    }
    return Array.from(map.entries());
  }, [entries]);

  const filteredEntries = useMemo(() => {
    return (entries ?? []).filter((e) => {
      if (fStatus && e.status !== fStatus) return false;
      if (fEventType && e.event_type !== fEventType) return false;
      if (fPriority && e.priority !== fPriority) return false;
      if (fBriefId && e.brief_id !== fBriefId) return false;
      if (fAssignee && !e.assignee_ids.includes(fAssignee)) return false;
      return true;
    });
  }, [entries, fStatus, fEventType, fPriority, fBriefId, fAssignee]);

  // Entries visible in the current month/week view
  const visibleEntries = useMemo(() => {
    if (viewMode === "week") {
      const days = buildWeekGrid(weekAnchor);
      const start = days[0], end = days[6];
      return filteredEntries.filter((e) => {
        const d = entryDate(e);
        return d >= new Date(start.getFullYear(), start.getMonth(), start.getDate())
          && d <= new Date(end.getFullYear(), end.getMonth(), end.getDate());
      });
    }
    if (viewMode === "list") {
      return filteredEntries;
    }
    return filteredEntries.filter((e) => {
      const d = entryDate(e);
      return d.getFullYear() === year && d.getMonth() === month;
    });
  }, [filteredEntries, viewMode, year, month, weekAnchor]);

  const byDay = useMemo(() => {
    const map = new Map<string, BrandCalendarEntry[]>();
    for (const e of visibleEntries) {
      const key = e.entry_date;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(e);
    }
    return map;
  }, [visibleEntries]);

  const grid = useMemo(() => buildMonthGrid(year, month), [year, month]);
  const weekDays = useMemo(() => buildWeekGrid(weekAnchor), [weekAnchor]);

  const prevMonth = () => {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
  };
  const goToday = () => { setYear(today.getFullYear()); setMonth(today.getMonth()); setWeekAnchor(today); };
  const prevWeek = () => setWeekAnchor((d) => { const nd = new Date(d); nd.setDate(d.getDate() - 7); return nd; });
  const nextWeek = () => setWeekAnchor((d) => { const nd = new Date(d); nd.setDate(d.getDate() + 7); return nd; });

  const monthGridEl = (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="grid grid-cols-7 border-b border-border">
        {DAYS_TR.map((d) => (
          <div key={d} className="py-2.5 text-center text-[11px] font-semibold text-text-muted uppercase tracking-wider">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 divide-x divide-y divide-border">
        {grid.flatMap((row, ri) =>
          row.map((date, ci) => {
            const key = date ? dateKey(date) : `empty-${ri}-${ci}`;
            const dayEntries = (date && byDay.get(key)) ?? [];
            const isToday = date !== null && dateKey(date) === dateKey(today);
            return (
              <DayCell
                key={key}
                date={date}
                entries={dayEntries}
                isToday={isToday}
                isCurrentMonth={date !== null && date.getMonth() === month}
                onSelect={(d, evs) => setSelectedDay({ date: d, entries: evs })}
              />
            );
          })
        )}
      </div>
    </div>
  );

  const weekGridEl = (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="grid grid-cols-7 divide-x divide-border">
        {weekDays.map((d) => {
          const key = dateKey(d);
          const dayEntries = byDay.get(key) ?? [];
          const isToday = key === dateKey(today);
          return (
            <div key={key} className="min-h-[220px] flex flex-col">
              <div className="py-2 text-center border-b border-border">
                <p className="text-[10px] text-text-muted uppercase">{DAYS_TR[d.getDay() === 0 ? 6 : d.getDay() - 1]}</p>
                <span className={cn(
                  "inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium mt-0.5",
                  isToday ? "bg-gradient-accent text-white" : "text-text",
                )}>
                  {d.getDate()}
                </span>
              </div>
              <div
                className={cn("p-1.5 space-y-1 flex-1", dayEntries.length > 0 && "cursor-pointer hover:bg-surface-2/50")}
                onClick={() => dayEntries.length > 0 && setSelectedDay({ date: d, entries: dayEntries })}
              >
                {dayEntries.map((entry) => (
                  <EntryChip key={entry.id} entry={entry} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  const eventTypeOptions = [
    { value: "", label: "Tüm olay türleri" },
    ...Object.entries(EVENT_TYPE_CFG).map(([value, cfg]) => ({ value, label: cfg.label })),
  ];
  const statusOptions = [
    { value: "", label: "Tüm durumlar" },
    ...Array.from(new Set((entries ?? []).map((e) => e.status))).map((s) => ({
      value: s, label: STATUS_CFG[s]?.label ?? s,
    })),
  ];
  const priorityOptions = [
    { value: "", label: "Tüm öncelikler" },
    ...Object.entries(PRIORITY_CFG).map(([value, cfg]) => ({ value, label: cfg.label })),
  ];
  const briefOptions = [
    { value: "", label: "Tüm briefler" },
    ...briefs.map((b) => ({ value: b.id, label: b.title })),
  ];
  const assigneeSelectOptions = [
    { value: "", label: "Tüm sorumlular" },
    ...assigneeOptions.map(([id, name]) => ({ value: id, label: name })),
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto relative">
      {selectedDay && (
        <>
          <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm" onClick={() => setSelectedDay(null)} />
          <DayDrawer date={selectedDay.date} entries={selectedDay.entries} onClose={() => setSelectedDay(null)} />
        </>
      )}

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-text tracking-tight">İçerik Takvimi</h1>
        <p className="text-sm text-text-muted mt-0.5">Brief kilometre taşları ve planlanan içerikler.</p>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-5">
        <Select options={statusOptions} value={fStatus} onChange={(e) => setFStatus(e.target.value)} />
        <Select options={eventTypeOptions} value={fEventType} onChange={(e) => setFEventType(e.target.value)} />
        <Select options={priorityOptions} value={fPriority} onChange={(e) => setFPriority(e.target.value)} />
        <Select options={briefOptions} value={fBriefId} onChange={(e) => setFBriefId(e.target.value)} />
        <Select options={assigneeSelectOptions} value={fAssignee} onChange={(e) => setFAssignee(e.target.value)} />
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          {viewMode === "week" ? (
            <>
              <button onClick={prevWeek} className="p-2 rounded-lg hover:bg-surface-2 border border-border text-text-muted hover:text-text transition-colors">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <h2 className="text-sm font-semibold text-text min-w-[180px] text-center">
                {weekDays[0].toLocaleDateString("tr-TR", { day: "numeric", month: "short" })} – {weekDays[6].toLocaleDateString("tr-TR", { day: "numeric", month: "short" })}
              </h2>
              <button onClick={nextWeek} className="p-2 rounded-lg hover:bg-surface-2 border border-border text-text-muted hover:text-text transition-colors">
                <ChevronRight className="w-4 h-4" />
              </button>
            </>
          ) : viewMode === "month" ? (
            <>
              <button onClick={prevMonth} className="p-2 rounded-lg hover:bg-surface-2 border border-border text-text-muted hover:text-text transition-colors">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <h2 className="text-lg font-semibold text-text min-w-[160px] text-center">
                {MONTHS_TR[month]} {year}
              </h2>
              <button onClick={nextMonth} className="p-2 rounded-lg hover:bg-surface-2 border border-border text-text-muted hover:text-text transition-colors">
                <ChevronRight className="w-4 h-4" />
              </button>
            </>
          ) : (
            <h2 className="text-lg font-semibold text-text">Tüm Kayıtlar</h2>
          )}
          <button onClick={goToday} className="ml-1 px-3 py-1.5 text-xs font-medium text-text-muted hover:text-text border border-border rounded-lg hover:bg-surface-2 transition-colors">
            Bugün
          </button>
        </div>

        <div className="flex items-center gap-1 bg-surface-2 border border-border p-1 rounded-lg self-start">
          <button
            onClick={() => setViewMode("month")}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors", viewMode === "month" ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text")}
          >
            <Calendar className="w-3 h-3" />Ay
          </button>
          <button
            onClick={() => setViewMode("week")}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors", viewMode === "week" ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text")}
          >
            <Calendar className="w-3 h-3" />Hafta
          </button>
          <button
            onClick={() => setViewMode("list")}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors", viewMode === "list" ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text")}
          >
            <List className="w-3 h-3" />Liste
          </button>
        </div>
      </div>

      {/* Content */}
      {error ? (
        <div className="flex items-center gap-3 px-5 py-4 rounded-xl bg-danger/8 border border-danger/20">
          <AlertCircle className="w-4 h-4 text-danger flex-shrink-0" />
          <p className="text-sm text-danger">Takvim verisi yüklenemedi.</p>
          <button onClick={loadData} className="text-xs text-danger/70 hover:text-danger underline ml-auto">Tekrar dene</button>
        </div>
      ) : entries === null ? (
        <CalSkeleton />
      ) : viewMode === "list" ? (
        <ListView entries={[...visibleEntries].sort((a, b) => a.entry_date.localeCompare(b.entry_date))} />
      ) : (
        <>
          {/* Mobile: always show agenda list, regardless of selected desktop view */}
          <div className="md:hidden">
            <ListView entries={[...visibleEntries].sort((a, b) => a.entry_date.localeCompare(b.entry_date))} />
          </div>
          <div className="hidden md:block">
            {viewMode === "week" ? weekGridEl : monthGridEl}
          </div>
        </>
      )}

      {/* Legend */}
      {entries !== null && (
        <div className="flex flex-wrap items-center gap-4 mt-4">
          {(Object.entries(EVENT_TYPE_CFG) as [string, typeof EVENT_TYPE_CFG[string]][]).map(
            ([key, cfg]) => (
              <span key={key} className="flex items-center gap-1.5 text-[11px] text-text-muted">
                <span className={cn("w-2 h-2 rounded-full", cfg.dot)} />
                {cfg.label}
              </span>
            )
          )}
        </div>
      )}
    </div>
  );
}
