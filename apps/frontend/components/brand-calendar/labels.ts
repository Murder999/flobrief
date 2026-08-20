import { translateCurrent } from "@/lib/i18n/current";

export const EVENT_TYPE_CFG: Record<string, { label: string; chip: string; dot: string }> = {
  // Real content calendar item types
  post: { get label() { return translateCurrent("dashboard.calendar.event.post"); }, chip: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20", dot: "bg-indigo-400" },
  story: { get label() { return translateCurrent("dashboard.calendar.event.story"); }, chip: "bg-purple-500/10 text-purple-400 border-purple-500/20", dot: "bg-purple-400" },
  reels: { get label() { return translateCurrent("dashboard.calendar.event.reels"); }, chip: "bg-pink-500/10 text-pink-400 border-pink-500/20", dot: "bg-pink-400" },
  video: { get label() { return translateCurrent("dashboard.calendar.event.video"); }, chip: "bg-rose-500/10 text-rose-400 border-rose-500/20", dot: "bg-rose-400" },
  campaign: { get label() { return translateCurrent("dashboard.calendar.event.campaign"); }, chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  blog: { get label() { return translateCurrent("dashboard.calendar.event.blog"); }, chip: "bg-teal-500/10 text-teal-400 border-teal-500/20", dot: "bg-teal-400" },
  email: { get label() { return translateCurrent("dashboard.calendar.event.email"); }, chip: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20", dot: "bg-cyan-400" },
  ad_creative: { get label() { return translateCurrent("dashboard.calendar.event.adCreative"); }, chip: "bg-orange-500/10 text-orange-400 border-orange-500/20", dot: "bg-orange-400" },
  meeting: { get label() { return translateCurrent("dashboard.calendar.event.meeting"); }, chip: "bg-blue-500/10 text-blue-400 border-blue-500/20", dot: "bg-blue-400" },
  custom: { get label() { return translateCurrent("dashboard.calendar.event.custom"); }, chip: "bg-slate-500/10 text-slate-400 border-slate-500/20", dot: "bg-slate-400" },
  // Brief-lifecycle milestones
  brief_start: { get label() { return translateCurrent("dashboard.calendar.event.briefStart"); }, chip: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", dot: "bg-emerald-400" },
  first_draft: { get label() { return translateCurrent("dashboard.calendar.event.firstDraft"); }, chip: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20", dot: "bg-indigo-400" },
  brand_feedback: { get label() { return translateCurrent("dashboard.calendar.event.brandFeedback"); }, chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  approval_deadline: { get label() { return translateCurrent("dashboard.calendar.event.approvalDeadline"); }, chip: "bg-red-500/10 text-red-400 border-red-500/20", dot: "bg-red-400" },
  final_delivery: { get label() { return translateCurrent("dashboard.calendar.event.finalDelivery"); }, chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
  publish_date: { get label() { return translateCurrent("dashboard.calendar.event.publishDate"); }, chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
};

export const STATUS_CFG: Record<string, { label: string; chip: string; dot: string }> = {
  planned: { get label() { return translateCurrent("dashboard.calendar.status.planned"); }, chip: "bg-surface-2 text-text-muted border-border", dot: "bg-text-muted/40" },
  in_design: { get label() { return translateCurrent("dashboard.calendar.status.inDesign"); }, chip: "bg-blue-500/10 text-blue-400 border-blue-500/20", dot: "bg-blue-400" },
  waiting_approval: { get label() { return translateCurrent("dashboard.calendar.status.waitingApproval"); }, chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  approved: { get label() { return translateCurrent("briefs.status.approved"); }, chip: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", dot: "bg-emerald-400" },
  scheduled: { get label() { return translateCurrent("dashboard.calendar.status.scheduled"); }, chip: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20", dot: "bg-indigo-400" },
  published: { get label() { return translateCurrent("dashboard.calendar.status.published"); }, chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
  cancelled: { get label() { return translateCurrent("dashboard.calendar.status.cancelled"); }, chip: "bg-danger/10 text-danger border-danger/20", dot: "bg-danger" },
  draft: { get label() { return translateCurrent("briefs.status.draft"); }, chip: "bg-surface-2 text-text-muted border-border", dot: "bg-text-muted/40" },
  submitted: { get label() { return translateCurrent("briefs.status.submitted"); }, chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  accepted: { get label() { return translateCurrent("briefs.status.accepted"); }, chip: "bg-teal-500/10 text-teal-400 border-teal-500/20", dot: "bg-teal-400" },
  in_production: { get label() { return translateCurrent("briefs.status.inProduction"); }, chip: "bg-blue-500/10 text-blue-400 border-blue-500/20", dot: "bg-blue-400" },
  ready_for_review: { get label() { return translateCurrent("briefs.status.readyForReview"); }, chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  revision_requested: { get label() { return translateCurrent("briefs.status.revisionRequested"); }, chip: "bg-orange-500/10 text-orange-400 border-orange-500/20", dot: "bg-orange-400" },
  rejected: { get label() { return translateCurrent("briefs.status.rejected"); }, chip: "bg-danger/10 text-danger border-danger/20", dot: "bg-danger" },
  completed: { get label() { return translateCurrent("briefs.status.completed"); }, chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
  archived: { get label() { return translateCurrent("briefs.status.archived"); }, chip: "bg-surface-2 text-text-muted/50 border-border", dot: "bg-text-muted/20" },
  in_review: { get label() { return translateCurrent("briefs.status.inReview"); }, chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
};

export const PRIORITY_CFG: Record<string, { label: string; className: string }> = {
  urgent: { get label() { return translateCurrent("briefs.priority.urgent"); }, className: "text-red-400 bg-red-400/10" },
  high: { get label() { return translateCurrent("briefs.priority.high"); }, className: "text-amber-400 bg-amber-400/10" },
  normal: { get label() { return translateCurrent("briefs.priority.normal"); }, className: "text-blue-400 bg-blue-400/10" },
  low: { get label() { return translateCurrent("briefs.priority.low"); }, className: "text-slate-400 bg-slate-400/10" },
};
