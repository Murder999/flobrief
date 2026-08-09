// Shared helpers for the capacity/resource-planning pages
// (`app/dashboard/capacity/**`, `components/capacity/**`). Status strings,
// reason strings, and threshold classification all come from
// `CapacityCalculationService` — see apps/backend/app/services/capacity_calculation_service.py
// `_status_for_pct` / `_net_capacity` for the source of truth these mirror.

export type CapacityStatus = "available" | "balanced" | "near_capacity" | "overloaded" | "unknown";
export type CapacityStatusReason = "ok" | "no_schedule" | "time_off" | "no_working_days";
export type CapacityScale = "daily" | "weekly" | "monthly";

export const CAPACITY_STATUS_LABEL: Record<CapacityStatus, string> = {
  available: "Müsait",
  balanced: "Dengeli",
  near_capacity: "Kapasiteye Yakın",
  overloaded: "Aşırı Yüklenmiş",
  unknown: "Bilinmiyor",
};

export const CAPACITY_STATUS_COLOR: Record<CapacityStatus, string> = {
  available: "text-success",
  balanced: "text-info",
  near_capacity: "text-warning",
  overloaded: "text-danger",
  unknown: "text-text-muted",
};

export const CAPACITY_REASON_LABEL: Record<CapacityStatusReason, string> = {
  ok: "",
  no_schedule: "Veri Eksik",
  time_off: "İzinli",
  no_working_days: "Çalışma Günü Yok",
};

export function minutesToHours(minutes: number): string {
  return (minutes / 60).toFixed(1);
}

export function formatMinutesAsHours(minutes: number): string {
  return `${minutesToHours(minutes)}s`;
}

// Local calendar date, not toISOString() — matches the convention already
// established in hooks/useDateRangeFilter.ts (toISOString() shifts the date
// across midnight for any user west of UTC).
function localISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Computes the [start, end] ISO date range for a capacity time-scale
 * toggle. "weekly" (the default) deliberately matches the backend's own
 * `_default_range()` — Monday..Sunday of the current week — so a page that
 * omits start/end params gets the exact same range the UI shows. */
export function getRangeForScale(
  scale: CapacityScale,
  anchor: Date = new Date()
): { start: string; end: string } {
  if (scale === "daily") {
    const iso = localISODate(anchor);
    return { start: iso, end: iso };
  }
  if (scale === "monthly") {
    const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    return { start: localISODate(start), end: localISODate(end) };
  }
  const day = anchor.getDay(); // 0=Sun..6=Sat
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const start = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate() + diffToMonday);
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
  return { start: localISODate(start), end: localISODate(end) };
}

// ── RBAC hints (frontend UX only) ───────────────────────────────────────────
// Mirrors the *actual* role → permission wiring in
// apps/backend/app/core/rbac.py `_AGENCY_ROLE_PERMISSIONS` for the capacity
// permission set. This is a convenience for hiding actions the user can't
// perform — the backend's `require_permission` dependency is the real gate,
// never this.

const CAPACITY_MANAGE_ROLES = new Set(["owner", "admin"]);
const CAPACITY_TEAM_VIEW_ROLES = new Set(["owner", "admin", "brand_manager"]);
// brand_manager has CAPACITY_VIEW_TEAM but not TIME_OFF_REQUEST in the real
// rbac.py wiring — do not add it here without updating the backend first.
const TIME_OFF_REQUEST_ROLES = new Set(["owner", "admin", "designer", "developer", "social_media_manager"]);

export function canViewTeamCapacity(role: string | null | undefined): boolean {
  return !!role && CAPACITY_TEAM_VIEW_ROLES.has(role);
}

export function canManageSchedule(role: string | null | undefined): boolean {
  return !!role && CAPACITY_MANAGE_ROLES.has(role);
}

export function canManageAllocation(role: string | null | undefined): boolean {
  return !!role && CAPACITY_MANAGE_ROLES.has(role);
}

export function canApproveTimeOff(role: string | null | undefined): boolean {
  return !!role && CAPACITY_MANAGE_ROLES.has(role);
}

export function canRequestTimeOff(role: string | null | undefined): boolean {
  return !!role && TIME_OFF_REQUEST_ROLES.has(role);
}

export const TIME_OFF_TYPE_LABEL: Record<string, string> = {
  vacation: "Yıllık İzin",
  sick: "Hastalık İzni",
  holiday: "Resmi Tatil",
  unpaid: "Ücretsiz İzin",
  other: "Diğer",
};

export const CAPACITY_EXCEPTION_TYPE_LABEL: Record<string, string> = {
  reduced: "Azaltılmış Kapasite",
  increased: "Artırılmış Kapasite",
  closure: "Kapalı",
};

// weekday: 0=Monday..6=Sunday (Python `date.weekday()` convention — matches
// `WorkScheduleDay.weekday`, see apps/backend/app/schemas/work_schedule.py).
export const WEEKDAY_LABELS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];

export const BRIEF_PRIORITY_LABEL: Record<string, string> = {
  urgent: "Acil",
  high: "Yüksek",
  normal: "Normal",
  low: "Düşük",
};

export const BRIEF_PRIORITY_BADGE_VARIANT: Record<string, string> = {
  urgent: "status-danger",
  high: "status-warning",
  normal: "status-info",
  low: "status-neutral",
};
