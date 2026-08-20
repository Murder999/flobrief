import type { BrandKPIStats, BriefRead, NotificationRead } from "@/lib/api-client";
import { isOverdue as isBriefOverdue, fmtRelative, fmtShortDate } from "@/components/brief-detail/shared";
import { translateCurrent } from "@/lib/i18n/current";

export { fmtRelative, fmtShortDate };
export const isOverdue = isBriefOverdue;

// ── Greeting / time bounds ───────────────────────────────────────────────────

export function greetingFor(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return translateCurrent("dashboard.greeting.morning");
  if (hour < 18) return translateCurrent("dashboard.greeting.day");
  return translateCurrent("dashboard.greeting.evening");
}

export function startOfWeekISO(): string {
  const d = new Date();
  const day = d.getDay() === 0 ? 7 : d.getDay();
  d.setDate(d.getDate() - day + 1);
  d.setHours(0, 0, 0, 0);
  return d.toISOString().slice(0, 10);
}

export function endOfWeekISO(): string {
  const d = new Date();
  const day = d.getDay() === 0 ? 7 : d.getDay();
  d.setDate(d.getDate() + (7 - day));
  d.setHours(23, 59, 59, 0);
  return d.toISOString().slice(0, 10);
}

function daysAgo(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

// ── Action queue ──────────────────────────────────────────────────────────────
// Only "ready_for_review" (agency delivered, brand-portal flow) and "in_review"
// (legacy agency->brand flow, non brand-portal source) are actually the brand's
// turn to act — "revision_requested"/"accepted" mean the agency is acting next,
// so they are informational elsewhere on the dashboard, not action items here.

export interface ActionItem {
  brief: BriefRead;
  ctaLabel: string;
  reasonLabel: string;
  reasonCls: string;
  overdue: boolean;
  urgency: number;
}

function isBrandActionable(brief: BriefRead): boolean {
  if (brief.status === "ready_for_review") return true;
  if (brief.status === "in_review" && brief.source !== "brand_portal") return true;
  return false;
}

// kpis.pending_review (backend, accurate across all briefs) covers the
// brand-portal "ready_for_review" path; the legacy "in_review" path has no
// backend aggregate yet, so it's counted from the already-loaded brief page.
export function countPendingApproval(kpis: BrandKPIStats, briefs: BriefRead[]): number {
  return kpis.pending_review + briefs.filter((b) => b.status === "in_review" && b.source !== "brand_portal").length;
}

export function countOverdue(briefs: BriefRead[]): number {
  return briefs.filter((b) => isBriefOverdue(b.deadline, b.status)).length;
}

export function deriveActionItems(briefs: BriefRead[]): ActionItem[] {
  const items: ActionItem[] = [];

  for (const brief of briefs) {
    const actionable = isBrandActionable(brief);
    const overdue = isBriefOverdue(brief.deadline, brief.status);
    if (!actionable && !overdue) continue;
    items.push({
      brief,
      ctaLabel: actionable ? (brief.status === "ready_for_review" ? translateCurrent("dashboard.brand.approve") : translateCurrent("dashboard.brand.review")) : translateCurrent("dashboard.brand.review"),
      reasonLabel: overdue ? translateCurrent("dashboard.brand.overdueLabel") : translateCurrent("dashboard.brand.awaitingApproval"),
      reasonCls: overdue ? "text-danger" : "text-amber-400",
      overdue,
      urgency: overdue ? 0 : 1,
    });
  }

  return items.sort((a, b) => {
    if (a.urgency !== b.urgency) return a.urgency - b.urgency;
    const ad = a.brief.deadline ? new Date(a.brief.deadline).getTime() : Infinity;
    const bd = b.brief.deadline ? new Date(b.brief.deadline).getTime() : Infinity;
    return ad - bd;
  });
}

export function waitingSinceLabel(brief: BriefRead): string {
  const d = daysAgo(brief.updated_at);
  if (d <= 0) return translateCurrent("dashboard.brand.updatedToday");
  if (d === 1) return translateCurrent("dashboard.brand.waitingOneDay");
  return translateCurrent("dashboard.brand.waitingDays", { count: d });
}

// ── KPI sub-metrics derived client-side from the already-loaded brief list ──
// (kept off the backend since /brand-portal/dashboard/kpis already covers the
// primary counts; these are cheap client-side refinements, not new queries)

export function countDraft(briefs: BriefRead[]): number {
  return briefs.filter((b) => b.status === "draft").length;
}

export function countRevisionLast7Days(briefs: BriefRead[]): number {
  return briefs.filter((b) => b.status === "revision_requested" && daysAgo(b.updated_at) <= 7).length;
}

export function countCompletedThisWeek(briefs: BriefRead[]): number {
  const weekStart = new Date(startOfWeekISO()).getTime();
  return briefs.filter(
    (b) => (b.status === "approved" || b.status === "completed") && new Date(b.updated_at).getTime() >= weekStart
  ).length;
}

// ── Activity feed icon bucketing ─────────────────────────────────────────────
// event_type strings are richer than the frontend's NotificationEventType
// union (backend has deliverable.*/annotation.*/comment.* events not yet
// mirrored there) — bucket by prefix instead of an exhaustive switch so new
// event types degrade gracefully to a sensible default icon.

export type ActivityBucket = "deliverable" | "comment" | "approval" | "revision" | "calendar" | "brief" | "other";

export function bucketForEventType(eventType: string): ActivityBucket {
  if (eventType.startsWith("deliverable") || eventType.startsWith("annotation")) return "deliverable";
  if (eventType.startsWith("comment")) return "comment";
  if (eventType.includes("revision_requested")) return "revision";
  if (eventType.includes("approved")) return "approval";
  if (eventType.startsWith("calendar")) return "calendar";
  if (eventType.startsWith("brief")) return "brief";
  return "other";
}

export function activityDotCls(n: NotificationRead): string {
  return n.is_read ? "bg-text-muted/30" : "bg-accent";
}
