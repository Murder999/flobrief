"use client";

import Link from "next/link";
import type { BriefRead, BriefStatus } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle,
  RotateCcw,
  XCircle,
  Loader2,
  Clock,
  Send,
} from "lucide-react";
import { fmtDate, fmtRelative, STATUS_CFG, PRIORITY_CFG } from "./shared";

// ── Compact status banner config ─────────────────────────────────────────────
// Replaces the ten near-identical full-width callout cards from the old page
// with one config-driven, condensed banner.

const BANNER_CFG: Partial<Record<BriefStatus, { icon: typeof Send; tone: string; title: string; subtitle: string }>> = {
  submitted: { icon: Send, tone: "violet", title: "Brief ajansa gönderildi", subtitle: "Ajans talebinizi inceleyecek ve en kısa sürede geri dönecektir." },
  accepted: { icon: CheckCircle, tone: "teal", title: "Ajans talebinizi kabul etti", subtitle: "Brief üretime alındı. Ajans çalışmaya başlayacak." },
  in_production: { icon: Clock, tone: "indigo", title: "Üretim süreci devam ediyor", subtitle: "Ajans üzerinde çalışıyor. Hazır olduğunda incelemenize sunulacak." },
  ready_for_review: { icon: CheckCircle, tone: "cyan", title: "İncelemeniz bekleniyor", subtitle: "Ajans çalışmayı teslim etti. Onaylayın veya revizyon isteyin." },
  revision_requested: { icon: RotateCcw, tone: "orange", title: "Revizyon talebiniz iletildi", subtitle: "Ajans revize ettiğinde sizi bilgilendirecektir." },
  approved: { icon: CheckCircle, tone: "emerald", title: "Brief onaylandı", subtitle: "Ajans çalışmaya devam edecek." },
  completed: { icon: CheckCircle, tone: "green", title: "Brief tamamlandı", subtitle: "Bu iş teslim edildi ve tamamlandı." },
  scheduled: { icon: CalendarDays, tone: "sky", title: "Takvime alındı", subtitle: "Bu brief onaylandı ve yayın takvimine alındı." },
};

const TONE_CLASSES: Record<string, { bg: string; text: string; iconBg: string }> = {
  violet: { bg: "bg-violet-500/5 border-violet-500/20", text: "text-violet-500", iconBg: "bg-violet-500/10" },
  teal: { bg: "bg-teal-500/5 border-teal-500/20", text: "text-teal-500", iconBg: "bg-teal-500/10" },
  indigo: { bg: "bg-indigo-500/5 border-indigo-500/20", text: "text-indigo-500", iconBg: "bg-indigo-500/10" },
  cyan: { bg: "bg-cyan-500/5 border-cyan-500/20", text: "text-cyan-500", iconBg: "bg-cyan-500/10" },
  orange: { bg: "bg-orange-500/5 border-orange-500/20", text: "text-orange-500", iconBg: "bg-orange-500/10" },
  emerald: { bg: "bg-emerald-500/5 border-emerald-500/20", text: "text-emerald-500", iconBg: "bg-emerald-500/10" },
  green: { bg: "bg-green-500/5 border-green-500/20", text: "text-green-500", iconBg: "bg-green-500/10" },
  sky: { bg: "bg-sky-500/5 border-sky-500/20", text: "text-sky-500", iconBg: "bg-sky-500/10" },
  amber: { bg: "bg-amber-500/5 border-amber-500/20", text: "text-amber-500", iconBg: "bg-amber-500/10" },
  blue: { bg: "bg-blue-500/5 border-blue-500/20", text: "text-blue-500", iconBg: "bg-blue-500/10" },
};

function StatusBanner({ brief }: { brief: BriefRead }) {
  let cfg = BANNER_CFG[brief.status as BriefStatus];
  // in_review has two distinct copies depending on origin — keep that nuance.
  if (brief.status === "in_review") {
    cfg = brief.source === "brand_portal"
      ? { icon: Clock, tone: "blue", title: "Talebiniz ajans tarafından inceleniyor", subtitle: "Ajans talebi inceledikten sonra sizi bilgilendirecektir." }
      : { icon: Clock, tone: "amber", title: "Bu brief onayınızı bekliyor", subtitle: "Sağdaki paneli kullanarak onay verebilir veya revizyon isteyebilirsiniz." };
  }
  if (!cfg) return null;
  const tone = TONE_CLASSES[cfg.tone] ?? TONE_CLASSES.blue;
  const Icon = cfg.icon;

  return (
    <div className={cn("flex items-center gap-3 rounded-xl border px-4 py-3", tone.bg)}>
      <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0", tone.iconBg)}>
        <Icon className={cn("w-4 h-4", tone.text)} />
      </div>
      <div className="min-w-0">
        <p className={cn("text-[13px] font-semibold leading-tight", tone.text)}>{cfg.title}</p>
        <p className="text-[12px] text-text-muted leading-tight mt-0.5">{cfg.subtitle}</p>
      </div>
    </div>
  );
}

// ── Action panel (shared shape for approve/revise/reject) ──────────────────

interface ActionPanelState {
  open: boolean;
  value: string;
  setValue: (v: string) => void;
  submitting: boolean;
  error: string | null;
  onSubmit: () => void;
  onCancel: () => void;
}

function ActionPanel({
  state,
  tone,
  title,
  helper,
  placeholder,
  submitLabel,
  submittingLabel,
  icon: Icon,
  required,
}: {
  state: ActionPanelState;
  tone: "emerald" | "orange" | "danger";
  title: string;
  helper: string;
  placeholder: string;
  submitLabel: string;
  submittingLabel: string;
  icon: typeof CheckCircle;
  required?: boolean;
}) {
  if (!state.open) return null;
  const toneClasses: Record<string, { border: string; bg: string; text: string; btn: string; ring: string }> = {
    emerald: { border: "border-emerald-500/25", bg: "bg-emerald-500/5", text: "text-emerald-500", btn: "bg-emerald-500 hover:bg-emerald-600", ring: "focus:ring-emerald-500/25 focus:border-emerald-500/40" },
    orange: { border: "border-orange-500/25", bg: "bg-orange-500/5", text: "text-orange-500", btn: "bg-orange-500 hover:bg-orange-600", ring: "focus:ring-orange-500/25 focus:border-orange-500/40" },
    danger: { border: "border-danger/25", bg: "bg-danger/5", text: "text-danger", btn: "bg-danger hover:opacity-90", ring: "focus:ring-danger/25 focus:border-danger/40" },
  };
  const t = toneClasses[tone];

  return (
    <div className={cn("mt-3 p-4 rounded-xl border", t.border, t.bg)}>
      <p className={cn("text-sm font-semibold mb-1.5", t.text)}>{title}</p>
      <p className="text-xs text-text-muted mb-3">{helper}</p>
      <textarea
        rows={2}
        placeholder={placeholder}
        value={state.value}
        onChange={(e) => state.setValue(e.target.value)}
        className={cn(
          "w-full px-3 py-2.5 bg-surface border border-border rounded-lg text-sm text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-2 resize-none transition-all mb-3",
          t.ring
        )}
      />
      {state.error && <p className="text-xs text-danger mb-2">{state.error}</p>}
      <div className="flex gap-2">
        <button
          onClick={state.onSubmit}
          disabled={state.submitting || (required && !state.value.trim())}
          className={cn("flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50 transition-colors", t.btn)}
        >
          {state.submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
          {state.submitting ? submittingLabel : submitLabel}
        </button>
        <button
          onClick={state.onCancel}
          className="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
        >
          İptal
        </button>
      </div>
    </div>
  );
}

// ── Header ────────────────────────────────────────────────────────────────────

interface BriefDetailHeaderProps {
  brief: BriefRead;
  overdue: boolean;
  canAct: boolean;
  approve: ActionPanelState;
  revise: ActionPanelState;
  reject: ActionPanelState;
  onOpenApprove: () => void;
  onOpenRevise: () => void;
  onOpenReject: () => void;
}

export function BriefDetailHeader({
  brief,
  overdue,
  canAct,
  approve,
  revise,
  reject,
  onOpenApprove,
  onOpenRevise,
  onOpenReject,
}: BriefDetailHeaderProps) {
  const stCfg = STATUS_CFG[brief.status as BriefStatus] ?? STATUS_CFG.draft;
  const prCfg = PRIORITY_CFG[brief.priority] ?? PRIORITY_CFG.normal;

  return (
    <div className="border-b border-border bg-surface/40">
      <div className="px-6 lg:px-8 pt-4 pb-5">
        <div className="flex items-center gap-1.5 mb-3 text-xs text-text-muted">
          <Link href="/brand/briefs" className="hover:text-accent transition-colors flex items-center gap-1">
            <ArrowLeft className="w-3 h-3" />
            Brieflerim
          </Link>
          <span>/</span>
          <span className="text-text truncate max-w-xs">{brief.title}</span>
        </div>

        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap mb-1.5">
              <h1 className="text-xl font-bold text-text leading-tight">{brief.title}</h1>
              <span className={cn(
                "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[11px] font-medium flex-shrink-0",
                stCfg.bg, stCfg.text, stCfg.border,
              )}>
                <span className={cn("w-1.5 h-1.5 rounded-full", stCfg.dot)} />
                {stCfg.label}
              </span>
            </div>
            {brief.description && (
              <p className="text-[13px] text-text-muted leading-relaxed line-clamp-1 max-w-2xl mb-2">
                {brief.description}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-text-muted">
              <span className={cn("font-medium", prCfg.color)}>{prCfg.label} öncelik</span>
              <span className="text-border">·</span>
              <span className={cn("inline-flex items-center gap-1", overdue ? "text-danger font-medium" : "")}>
                <CalendarDays className="w-3 h-3" />
                {brief.deadline ? `Son tarih: ${fmtDate(brief.deadline)}${overdue ? " · Gecikti" : ""}` : "Son tarih yok"}
              </span>
              <span className="text-border">·</span>
              <span>Son güncelleme: {fmtRelative(brief.updated_at)}</span>
            </div>
          </div>

          {canAct && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={onOpenReject}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-danger/30 bg-danger/8 text-danger text-[13px] font-medium hover:bg-danger/15 transition-colors"
              >
                <XCircle className="w-3.5 h-3.5" />
                Reddet
              </button>
              <button
                onClick={onOpenRevise}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-orange-500/30 bg-orange-500/8 text-orange-500 text-[13px] font-medium hover:bg-orange-500/15 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Revize İste
              </button>
              <button
                onClick={onOpenApprove}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-gradient-accent text-white text-[13px] font-medium hover:opacity-90 transition-opacity shadow-sm"
              >
                <CheckCircle className="w-3.5 h-3.5" />
                Onayla
              </button>
            </div>
          )}
        </div>

        <ActionPanel
          state={approve}
          tone="emerald"
          title="Brief'i Onayla"
          helper="Onayınız ajansa iletilecektir."
          placeholder="Onay notu ekleyin (isteğe bağlı)..."
          submitLabel="Onayı Gönder"
          submittingLabel="Gönderiliyor…"
          icon={CheckCircle}
        />
        <ActionPanel
          state={revise}
          tone="orange"
          title="Revizyon Talep Et"
          helper="Neyi değiştirmek istediğinizi açıklayın."
          placeholder="Neyi değiştirmek istiyorsunuz?..."
          submitLabel="Revizyon Gönder"
          submittingLabel="Gönderiliyor…"
          icon={RotateCcw}
          required
        />
        <ActionPanel
          state={reject}
          tone="danger"
          title="Brief'i Reddet"
          helper="Red nedeni ajansa iletilecektir. Bu işlem geri alınamaz."
          placeholder="Red nedenini açıklayın (zorunlu)..."
          submitLabel="Reddi Gönder"
          submittingLabel="Gönderiliyor…"
          icon={XCircle}
          required
        />

        <div className="mt-3">
          <StatusBanner brief={brief} />
        </div>
      </div>
    </div>
  );
}
