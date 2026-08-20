import type { BriefStatus } from "@/lib/api-client";
import { formatLocalizedDate } from "@/lib/i18n/format";
import { currentLocale, translateCurrent } from "@/lib/i18n/current";

// ── Formatting helpers ───────────────────────────────────────────────────────

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return formatLocalizedDate(iso, currentLocale(), { day: "numeric", month: "long", year: "numeric" });
}

export function fmtShortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return formatLocalizedDate(iso, currentLocale(), { day: "numeric", month: "short" });
}

export function fmtRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return translateCurrent("briefs.time.justNow");
  if (m < 60) return translateCurrent("briefs.time.minutesAgo", { count: m });
  const h = Math.floor(m / 60);
  if (h < 24) return translateCurrent("briefs.time.hoursAgo", { count: h });
  const d = Math.floor(h / 24);
  if (d < 7) return translateCurrent("briefs.time.daysAgo", { count: d });
  return fmtDate(iso);
}

export function isOverdue(deadline: string | null, s: string): boolean {
  const doneStatuses = ["approved", "accepted", "completed", "scheduled", "archived"];
  if (!deadline || doneStatuses.includes(s)) return false;
  return new Date(deadline) < new Date();
}

// ── Config ────────────────────────────────────────────────────────────────────

export const STATUS_CFG: Record<BriefStatus, { label: string; bg: string; text: string; border: string; dot: string }> = {
  draft: {
    get label() { return translateCurrent("briefs.status.draft"); }, bg: "bg-surface-2", text: "text-text-muted",
    border: "border-border", dot: "bg-text-muted/40",
  },
  submitted: {
    get label() { return translateCurrent("briefs.status.submitted"); }, bg: "bg-violet-500/10", text: "text-violet-400",
    border: "border-violet-500/25", dot: "bg-violet-400",
  },
  in_review: {
    get label() { return translateCurrent("briefs.status.inReview"); }, bg: "bg-amber-500/10", text: "text-amber-400",
    border: "border-amber-500/25", dot: "bg-amber-400",
  },
  accepted: {
    get label() { return translateCurrent("briefs.status.accepted"); }, bg: "bg-teal-500/10", text: "text-teal-400",
    border: "border-teal-500/25", dot: "bg-teal-400",
  },
  in_production: {
    get label() { return translateCurrent("briefs.status.inProduction"); }, bg: "bg-indigo-500/10", text: "text-indigo-400",
    border: "border-indigo-500/25", dot: "bg-indigo-400",
  },
  ready_for_review: {
    get label() { return translateCurrent("briefs.status.readyForReview"); }, bg: "bg-cyan-500/10", text: "text-cyan-400",
    border: "border-cyan-500/25", dot: "bg-cyan-400",
  },
  revision_requested: {
    get label() { return translateCurrent("briefs.status.revisionRequested"); }, bg: "bg-orange-500/10", text: "text-orange-400",
    border: "border-orange-500/25", dot: "bg-orange-400",
  },
  approved: {
    get label() { return translateCurrent("briefs.status.approved"); }, bg: "bg-emerald-500/10", text: "text-emerald-400",
    border: "border-emerald-500/25", dot: "bg-emerald-400",
  },
  completed: {
    get label() { return translateCurrent("briefs.status.completed"); }, bg: "bg-green-500/10", text: "text-green-400",
    border: "border-green-500/25", dot: "bg-green-400",
  },
  scheduled: {
    get label() { return translateCurrent("briefs.status.scheduled"); }, bg: "bg-sky-500/10", text: "text-sky-400",
    border: "border-sky-500/25", dot: "bg-sky-400",
  },
  archived: {
    get label() { return translateCurrent("briefs.status.archived"); }, bg: "bg-surface-2", text: "text-text-muted",
    border: "border-border", dot: "bg-text-muted/20",
  },
};

export const PRIORITY_CFG: Record<string, { label: string; color: string }> = {
  urgent: { get label() { return translateCurrent("briefs.priority.urgent"); }, color: "text-danger" },
  high: { get label() { return translateCurrent("briefs.priority.high"); }, color: "text-amber-400" },
  normal: { get label() { return translateCurrent("briefs.priority.normal"); }, color: "text-blue-400" },
  low: { get label() { return translateCurrent("briefs.priority.low"); }, color: "text-text-muted" },
};

export const TIMELINE_CFG: Record<string, { color: string; ring: string }> = {
  muted: { color: "bg-text-muted/40", ring: "ring-text-muted/15" },
  amber: { color: "bg-amber-400", ring: "ring-amber-500/20" },
  emerald: { color: "bg-emerald-400", ring: "ring-emerald-500/20" },
  orange: { color: "bg-orange-400", ring: "ring-orange-500/20" },
  blue: { color: "bg-blue-400", ring: "ring-blue-500/20" },
};

export const COMMENT_TYPE_CFG = {
  general: { get label() { return translateCurrent("briefs.comment.general"); }, bg: "bg-accent/8", border: "border-accent/15", dot: "bg-accent" },
  revision_note: { get label() { return translateCurrent("briefs.comment.revision"); }, bg: "bg-orange-500/8", border: "border-orange-500/15", dot: "bg-orange-400" },
  approval_note: { get label() { return translateCurrent("briefs.comment.approval"); }, bg: "bg-emerald-500/8", border: "border-emerald-500/15", dot: "bg-emerald-400" },
};

export const DELIVERABLE_STATUS_CFG: Record<string, { label: string; className: string }> = {
  submitted: { get label() { return translateCurrent("briefs.deliverable.awaitingReview"); }, className: "bg-blue-50 text-blue-700 border-blue-200" },
  revision_requested: { get label() { return translateCurrent("briefs.status.revisionRequested"); }, className: "bg-amber-50 text-amber-700 border-amber-200" },
  approved: { get label() { return translateCurrent("briefs.status.approved"); }, className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  rejected: { get label() { return translateCurrent("briefs.status.rejected"); }, className: "bg-red-50 text-red-700 border-red-200" },
};

export const DELIVERABLE_TYPE_LABEL: Record<string, string> = {
  get image() { return translateCurrent("briefs.deliverable.image"); },
  get video() { return translateCurrent("briefs.deliverable.video"); },
  get text() { return translateCurrent("briefs.deliverable.text"); },
  get document() { return translateCurrent("briefs.deliverable.document"); },
  get link() { return translateCurrent("briefs.deliverable.link"); },
  get other() { return translateCurrent("briefs.deliverable.other"); },
};
