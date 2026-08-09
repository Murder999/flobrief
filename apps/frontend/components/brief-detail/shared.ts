import type { BriefStatus } from "@/lib/api-client";

// ── Formatting helpers ───────────────────────────────────────────────────────

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

export function fmtShortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

export function fmtRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "Az önce";
  if (m < 60) return `${m} dk önce`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} sa önce`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} gün önce`;
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
    label: "Taslak", bg: "bg-surface-2", text: "text-text-muted",
    border: "border-border", dot: "bg-text-muted/40",
  },
  submitted: {
    label: "Gönderildi", bg: "bg-violet-500/10", text: "text-violet-400",
    border: "border-violet-500/25", dot: "bg-violet-400",
  },
  in_review: {
    label: "Onay Bekliyor", bg: "bg-amber-500/10", text: "text-amber-400",
    border: "border-amber-500/25", dot: "bg-amber-400",
  },
  accepted: {
    label: "Kabul Edildi", bg: "bg-teal-500/10", text: "text-teal-400",
    border: "border-teal-500/25", dot: "bg-teal-400",
  },
  in_production: {
    label: "Üretimde", bg: "bg-indigo-500/10", text: "text-indigo-400",
    border: "border-indigo-500/25", dot: "bg-indigo-400",
  },
  ready_for_review: {
    label: "İncelemeye Hazır", bg: "bg-cyan-500/10", text: "text-cyan-400",
    border: "border-cyan-500/25", dot: "bg-cyan-400",
  },
  revision_requested: {
    label: "Revizyon İstendi", bg: "bg-orange-500/10", text: "text-orange-400",
    border: "border-orange-500/25", dot: "bg-orange-400",
  },
  approved: {
    label: "Onaylandı", bg: "bg-emerald-500/10", text: "text-emerald-400",
    border: "border-emerald-500/25", dot: "bg-emerald-400",
  },
  completed: {
    label: "Tamamlandı", bg: "bg-green-500/10", text: "text-green-400",
    border: "border-green-500/25", dot: "bg-green-400",
  },
  scheduled: {
    label: "Takvime Alındı", bg: "bg-sky-500/10", text: "text-sky-400",
    border: "border-sky-500/25", dot: "bg-sky-400",
  },
  archived: {
    label: "Arşivlendi", bg: "bg-surface-2", text: "text-text-muted",
    border: "border-border", dot: "bg-text-muted/20",
  },
};

export const PRIORITY_CFG: Record<string, { label: string; color: string }> = {
  urgent: { label: "Acil", color: "text-danger" },
  high: { label: "Yüksek", color: "text-amber-400" },
  normal: { label: "Normal", color: "text-blue-400" },
  low: { label: "Düşük", color: "text-text-muted" },
};

export const TIMELINE_CFG: Record<string, { color: string; ring: string }> = {
  muted: { color: "bg-text-muted/40", ring: "ring-text-muted/15" },
  amber: { color: "bg-amber-400", ring: "ring-amber-500/20" },
  emerald: { color: "bg-emerald-400", ring: "ring-emerald-500/20" },
  orange: { color: "bg-orange-400", ring: "ring-orange-500/20" },
  blue: { color: "bg-blue-400", ring: "ring-blue-500/20" },
};

export const COMMENT_TYPE_CFG = {
  general: { label: "Yorum", bg: "bg-accent/8", border: "border-accent/15", dot: "bg-accent" },
  revision_note: { label: "Revizyon", bg: "bg-orange-500/8", border: "border-orange-500/15", dot: "bg-orange-400" },
  approval_note: { label: "Onay Notu", bg: "bg-emerald-500/8", border: "border-emerald-500/15", dot: "bg-emerald-400" },
};

export const DELIVERABLE_STATUS_CFG: Record<string, { label: string; className: string }> = {
  submitted: { label: "İnceleme Bekliyor", className: "bg-blue-50 text-blue-700 border-blue-200" },
  revision_requested: { label: "Revizyon İstendi", className: "bg-amber-50 text-amber-700 border-amber-200" },
  approved: { label: "Onaylandı", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  rejected: { label: "Reddedildi", className: "bg-red-50 text-red-700 border-red-200" },
};

export const DELIVERABLE_TYPE_LABEL: Record<string, string> = {
  image: "Görsel", video: "Video", text: "Metin", document: "Doküman", link: "Link", other: "Diğer",
};
