"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import {
  brandPortalApi,
  type BriefRead,
  type BriefStatus,
} from "@/lib/api-client";
import { useEffect, useState, useCallback } from "react";
import {
  FileText,
  Search,
  Clock,
  CheckCircle,
  AlertCircle,
  RotateCcw,
  ChevronRight,
  CalendarDays,
  Zap,
  Plus,
  Building2,
  UserCircle2,
  SlidersHorizontal,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBreakpoint } from "@/hooks/useBreakpoint";
import { BottomSheet } from "@/components/ui/bottom-sheet";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function isOverdue(deadline: string | null, s: string): boolean {
  if (!deadline || s === "approved" || s === "accepted" || s === "archived") return false;
  return new Date(deadline) < new Date();
}

// ── Config ────────────────────────────────────────────────────────────────────

const STATUS_CFG: Record<BriefStatus, { label: string; bg: string; text: string; dot: string }> = {
  draft: { label: "Taslak", bg: "bg-surface-2", text: "text-text-muted", dot: "bg-text-muted/40" },
  submitted: { label: "Gönderildi", bg: "bg-violet-500/10", text: "text-violet-400", dot: "bg-violet-400" },
  in_review: { label: "Onay Bekliyor", bg: "bg-amber-500/10", text: "text-amber-400", dot: "bg-amber-400" },
  accepted: { label: "Kabul Edildi", bg: "bg-teal-500/10", text: "text-teal-400", dot: "bg-teal-400" },
  in_production: { label: "Üretimde", bg: "bg-indigo-500/10", text: "text-indigo-400", dot: "bg-indigo-400" },
  ready_for_review: { label: "İncelemeye Hazır", bg: "bg-cyan-500/10", text: "text-cyan-400", dot: "bg-cyan-400" },
  revision_requested: { label: "Revizyon İstendi", bg: "bg-orange-500/10", text: "text-orange-400", dot: "bg-orange-400" },
  approved: { label: "Onaylandı", bg: "bg-emerald-500/10", text: "text-emerald-400", dot: "bg-emerald-400" },
  completed: { label: "Tamamlandı", bg: "bg-green-500/10", text: "text-green-400", dot: "bg-green-400" },
  scheduled: { label: "Takvime Alındı", bg: "bg-sky-500/10", text: "text-sky-400", dot: "bg-sky-400" },
  archived: { label: "Arşivlendi", bg: "bg-surface-2", text: "text-text-muted", dot: "bg-text-muted/20" },
};

const PRIORITY_CFG: Record<string, { label: string; color: string; dot: string }> = {
  urgent: { label: "Acil", color: "text-danger", dot: "bg-danger" },
  high: { label: "Yüksek", color: "text-amber-400", dot: "bg-amber-400" },
  normal: { label: "Normal", color: "text-blue-400", dot: "bg-blue-400" },
  low: { label: "Düşük", color: "text-text-muted", dot: "bg-text-muted/30" },
};

const STATUS_FILTERS = [
  { value: "all", label: "Tümü" },
  { value: "in_review", label: "İncelemede" },
  { value: "revision_requested", label: "Revizyon" },
  { value: "approved", label: "Onaylandı" },
  { value: "draft", label: "Taslak" },
] as const;

function sourceBadge(brief: BriefRead) {
  if (brief.source === "brand_portal") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
        <UserCircle2 className="w-2.5 h-2.5" />
        Sizin Talebiniz
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-2 text-text-muted border border-border">
      <Building2 className="w-2.5 h-2.5" />
      Ajans
    </span>
  );
}

function statusLabel(brief: BriefRead): string {
  if (brief.source === "brand_portal") {
    const map: Record<string, string> = {
      draft: "Taslak",
      in_review: "Ajans İnceliyor",
      accepted: "Ajans Kabul Etti",
      revision_requested: "Ek Bilgi İstendi",
      approved: "Onaylandı",
      archived: "Arşivlendi",
    };
    return map[brief.status] ?? brief.status;
  }
  const map: Record<string, string> = {
    draft: "Taslak",
    in_review: "Onay Bekliyor",
    accepted: "Kabul Edildi",
    revision_requested: "Revizyon İstendi",
    approved: "Onaylandı",
    archived: "Arşivlendi",
  };
  return map[brief.status] ?? brief.status;
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 animate-pulse">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-surface-2 rounded w-3/4" />
          <div className="h-3 bg-surface-2 rounded w-1/2" />
        </div>
        <div className="h-6 bg-surface-2 rounded-full w-28 flex-shrink-0" />
      </div>
      <div className="flex items-center gap-3">
        <div className="h-5 bg-surface-2 rounded-full w-16" />
        <div className="h-4 bg-surface-2 rounded w-24" />
        <div className="h-4 bg-surface-2 rounded w-16 ml-auto" />
      </div>
    </div>
  );
}

// ── Brief Card ────────────────────────────────────────────────────────────────

function BriefCard({ brief }: { brief: BriefRead }) {
  const st = STATUS_CFG[brief.status as BriefStatus] ?? STATUS_CFG.draft;
  const pr = PRIORITY_CFG[brief.priority] ?? PRIORITY_CFG.normal;
  const overdue = isOverdue(brief.deadline, brief.status);
  const isFromBrand = brief.source === "brand_portal";
  const needsAction = brief.status === "in_review" && !isFromBrand;
  const label = statusLabel(brief);

  return (
    <Link
      href={`/brand/briefs/${brief.id}`}
      className={cn(
        "block bg-surface border rounded-xl p-5 transition-all duration-150 group relative overflow-hidden",
        needsAction
          ? "border-amber-500/30 shadow-[0_0_0_1px_rgba(245,158,11,0.08)] hover:border-amber-500/50"
          : isFromBrand
          ? "border-blue-500/20 hover:border-blue-500/40 hover:shadow-card-hover"
          : "border-border hover:border-accent/30 hover:shadow-card-hover",
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.008] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

      {needsAction && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-amber-500/60 to-transparent" />
      )}

      <div className="relative">
        {/* Top row */}
        <div className="flex items-start gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", pr.dot)} />
              <h3 className="text-sm font-semibold text-text truncate group-hover:text-accent transition-colors">
                {brief.title}
              </h3>
            </div>
            {brief.description && (
              <p className="text-xs text-text-muted line-clamp-2 ml-3.5">{brief.description}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <span className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium",
              st.bg, st.text
            )}>
              <span className={cn("w-1.5 h-1.5 rounded-full", st.dot)} />
              {label}
            </span>
            <ChevronRight className="w-4 h-4 text-text-muted/30 opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
          </div>
        </div>

        {/* Bottom row */}
        <div className="flex items-center gap-3 flex-wrap ml-3.5">
          {sourceBadge(brief)}
          <span className={cn("text-xs font-medium", pr.color)}>{pr.label}</span>

          {brief.deadline && (
            <span className={cn(
              "text-xs flex items-center gap-1",
              overdue ? "text-danger font-medium" : "text-text-muted"
            )}>
              <CalendarDays className="w-3 h-3" />
              {overdue ? "Gecikti — " : ""}{fmtDate(brief.deadline)}
            </span>
          )}

          <span className="text-xs text-text-muted ml-auto flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {fmtDate(brief.updated_at)}
          </span>
        </div>

        {/* Action nudge */}
        {needsAction && (
          <div className="mt-3 ml-3.5 flex items-center gap-1.5 text-amber-400">
            <Zap className="w-3 h-3" />
            <span className="text-[11px] font-medium">Onayınız bekleniyor</span>
          </div>
        )}
        {brief.status === "revision_requested" && !isFromBrand && (
          <div className="mt-3 ml-3.5 flex items-center gap-1.5 text-orange-400">
            <RotateCcw className="w-3 h-3" />
            <span className="text-[11px] font-medium">Revizyon ajansa iletildi</span>
          </div>
        )}
        {brief.status === "in_review" && isFromBrand && (
          <div className="mt-3 ml-3.5 flex items-center gap-1.5 text-blue-400">
            <Clock className="w-3 h-3" />
            <span className="text-[11px] font-medium">Ajans talebi inceliyor</span>
          </div>
        )}
        {brief.status === "accepted" && isFromBrand && (
          <div className="mt-3 ml-3.5 flex items-center gap-1.5 text-teal-400">
            <CheckCircle className="w-3 h-3" />
            <span className="text-[11px] font-medium">Ajans talebinizi kabul etti</span>
          </div>
        )}
      </div>
    </Link>
  );
}

// ── Hero Stats ────────────────────────────────────────────────────────────────

function HeroStats({ briefs }: { briefs: BriefRead[] }) {
  const now = new Date();
  const total = briefs.length;
  const pending = briefs.filter((b) => b.status === "in_review").length;
  const revision = briefs.filter((b) => b.status === "revision_requested").length;
  const approved = briefs.filter((b) => b.status === "approved").length;
  const overdue = briefs.filter((b) => isOverdue(b.deadline, b.status)).length;

  const stats = [
    { label: "Toplam Brief", value: total, icon: FileText, color: "text-text", bg: "bg-accent/10" },
    { label: "Onay Bekleyen", value: pending, icon: Clock, color: "text-amber-400", bg: "bg-amber-500/10" },
    { label: "Revizyon", value: revision, icon: RotateCcw, color: "text-orange-400", bg: "bg-orange-500/10" },
    { label: "Onaylanan", value: approved, icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "Geciken", value: overdue, icon: AlertCircle, color: "text-danger", bg: "bg-danger/10" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      {stats.map((s) => (
        <div key={s.label} className="bg-surface border border-border rounded-xl p-4">
          <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center mb-2.5", s.bg)}>
            <s.icon className={cn("w-4 h-4", s.color)} />
          </div>
          <p className={cn("text-2xl font-bold tracking-tight", s.color)}>{s.value}</p>
          <p className="text-xs text-text-muted mt-0.5">{s.label}</p>
        </div>
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function BrandBriefsPage() {
  const { accessToken } = useAuth();
  const searchParams = useSearchParams();
  const { isMobile } = useBreakpoint();
  const [briefs, setBriefs] = useState<BriefRead[] | null>(null);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>(() => searchParams.get("status") ?? "all");
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);

  const loadData = useCallback(async () => {
    if (!accessToken) return;
    try {
      const res = await brandPortalApi.listBriefs(accessToken, { limit: 200 });
      setBriefs(res.items);
    } catch {
      setError(true);
      setBriefs([]);
    }
  }, [accessToken]);

  useEffect(() => { loadData(); }, [loadData]);

  const filtered = briefs?.filter((b) => {
    const matchSearch = !search || b.title.toLowerCase().includes(search.toLowerCase()) ||
      (b.description ?? "").toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || b.status === statusFilter;
    return matchSearch && matchStatus;
  }) ?? [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-semibold text-text tracking-tight">Brieflerim</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Ajansınızın ilettiği briefler ve kendi talepleriniz.
          </p>
        </div>
        <Link
          href="/brand/briefs/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity shadow-sm flex-shrink-0"
        >
          <Plus className="w-3.5 h-3.5" />
          Yeni Brief Talebi
        </Link>
      </div>

      {/* Hero stats */}
      {briefs !== null && briefs.length > 0 && <HeroStats briefs={briefs} />}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-5">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
          <input
            type="text"
            placeholder="Brief ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 h-9 bg-surface border border-border rounded-lg text-sm text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/15 focus:border-accent/60 transition-all"
          />
        </div>

        {isMobile ? (
          <button
            onClick={() => setFilterSheetOpen(true)}
            className="inline-flex items-center gap-2 h-9 px-3.5 rounded-lg border border-border bg-surface-2 text-xs font-medium text-text"
          >
            <SlidersHorizontal className="w-3.5 h-3.5 text-text-muted" />
            {STATUS_FILTERS.find((f) => f.value === statusFilter)?.label ?? "Filtrele"}
          </button>
        ) : (
          <div className="flex items-center gap-1 bg-surface-2 border border-border p-1 rounded-lg">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  statusFilter === f.value
                    ? "bg-surface text-text shadow-sm ring-1 ring-border"
                    : "text-text-muted hover:text-text"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <BottomSheet
        isOpen={filterSheetOpen}
        onClose={() => setFilterSheetOpen(false)}
        title="Durumla Filtrele"
        description="Brieflerinizi duruma göre daraltın"
      >
        <div className="flex flex-col gap-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => {
                setStatusFilter(f.value);
                setFilterSheetOpen(false);
              }}
              className={cn(
                "flex items-center justify-between gap-3 px-3 py-3 rounded-lg text-sm font-medium text-left transition-colors min-h-[44px]",
                statusFilter === f.value ? "bg-accent/10 text-accent" : "text-text hover:bg-hover"
              )}
            >
              {f.label}
              {statusFilter === f.value && <Check className="w-4 h-4 flex-shrink-0" />}
            </button>
          ))}
        </div>
      </BottomSheet>

      {/* Content */}
      {error ? (
        <div className="flex items-center gap-3 px-5 py-4 rounded-xl bg-danger/8 border border-danger/20">
          <AlertCircle className="w-4 h-4 text-danger flex-shrink-0" />
          <p className="text-sm text-danger">Veriler yüklenemedi.</p>
          <button onClick={loadData} className="text-xs text-danger/70 hover:text-danger underline ml-auto">
            Tekrar dene
          </button>
        </div>
      ) : briefs === null ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => <CardSkeleton key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center py-20 text-center">
          <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <FileText className="w-8 h-8 text-text-muted/40" />
          </div>
          <h3 className="text-base font-semibold text-text mb-1">
            {search || statusFilter !== "all" ? "Eşleşen brief bulunamadı" : "Henüz brief yok"}
          </h3>
          <p className="text-sm text-text-muted max-w-xs">
            {search || statusFilter !== "all"
              ? "Filtrelerinizi değiştirerek tekrar deneyin."
              : "Ajansınız brief oluşturduğunda veya kendi talebinizi ilettiğinizde burada görünecek."}
          </p>
          {search || statusFilter !== "all" ? (
            <button
              onClick={() => { setSearch(""); setStatusFilter("all"); }}
              className="mt-4 text-xs text-accent hover:underline"
            >
              Filtreleri temizle
            </button>
          ) : (
            <Link
              href="/brand/briefs/new"
              className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-gradient-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Plus className="w-3.5 h-3.5" />
              Yeni Brief Talebi Oluştur
            </Link>
          )}
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {filtered.map((b) => <BriefCard key={b.id} brief={b} />)}
          </div>
          <p className="mt-4 text-xs text-text-muted text-right">
            {filtered.length} brief
            {briefs.length !== filtered.length && ` (toplam ${briefs.length})`}
          </p>
        </>
      )}
    </div>
  );
}
