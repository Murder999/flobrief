"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, type BrandApprovalCard } from "@/lib/api-client";
import { Tabs, type TabItem } from "@/components/ui/tabs";
import { MessageSquare, ArrowRight } from "lucide-react";
import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { InfoTooltip } from "@/components/contextual-help/InfoTooltip";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

function isOverdue(dueDate: string | null, status: string): boolean {
  if (!dueDate) return false;
  if (status !== "pending") return false;
  return new Date(dueDate) < new Date();
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    pending:             { label: "Onay Bekliyor",    cls: "status-warning" },
    revision_requested:  { label: "Revizyon İstendi", cls: "status-danger" },
    approved:            { label: "Onaylandı",        cls: "status-success" },
    rejected:            { label: "Reddedildi",       cls: "status-danger" },
    cancelled:           { label: "İptal Edildi",     cls: "status-neutral" },
    expired:             { label: "Süresi Geçti",     cls: "status-neutral opacity-60" },
  };
  const cfg = map[status] ?? { label: status, cls: "status-neutral" };
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 p-5 border-b border-border last:border-0 animate-pulse">
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-surface-2 rounded w-56" />
        <div className="h-3 bg-surface-2 rounded w-32" />
      </div>
      <div className="h-6 bg-surface-2 rounded-lg w-28" />
      <div className="h-4 bg-surface-2 rounded w-20" />
    </div>
  );
}

// ── Filter tabs ───────────────────────────────────────────────────────────────

type FilterTab = "all" | "pending" | "approved" | "revision_requested" | "rejected" | "expired" | "assigned_to_me";

const TABS: TabItem[] = [
  { value: "all", label: "Tümü" },
  { value: "pending", label: "Bekleyen" },
  { value: "approved", label: "Onaylandı" },
  { value: "revision_requested", label: "Revizyon İstendi" },
  { value: "rejected", label: "Reddedildi" },
  { value: "expired", label: "Süresi Geçti" },
  { value: "assigned_to_me", label: "Bana Atananlar" },
];

// ── Main ──────────────────────────────────────────────────────────────────────

export default function BrandApprovalsPage() {
  const { accessToken } = useAuth();
  const [approvals, setApprovals] = useState<BrandApprovalCard[] | null>(null);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState<FilterTab>("pending");
  const approvalsRef = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async () => {
    if (!accessToken) return;
    try {
      const params =
        activeTab === "all"
          ? undefined
          : activeTab === "assigned_to_me"
          ? { assigned_to_me: true }
          : { status: activeTab };
      const res = await brandPortalApi.listApprovals(accessToken, params);
      setApprovals(res);
      setError(false);
    } catch {
      setError(true);
      setApprovals([]);
    }
  }, [accessToken, activeTab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const pendingCount = useMemo(
    () => approvals?.filter((a) => a.status === "pending").length ?? 0,
    [approvals]
  );

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-text">Onaylar</h1>
            <p className="mt-1 text-text-muted">Onay bekleyen ve geçmiş içerik onay durumlarınız.</p>
          </div>
          {activeTab === "pending" && pendingCount > 0 && (
            <div className="status-warning flex items-center gap-2 rounded-xl px-4 py-2">
              <div className="w-2 h-2 rounded-full bg-warning animate-pulse" />
              <span className="text-sm font-medium">{pendingCount} onay bekliyor</span>
            </div>
          )}
          <InfoTooltip
            targetRef={approvalsRef}
            text="Onay akışı: Brief'in teslim edilmesi → Inceleme → Onay veya Revizyon iste → Tamamlandı. Bekleyen onaylar renkle belirtilir. Reddetmek/revizyon istemek için brief'i seçin."
            title="Onak Akışı Hakkında"
          />
        </div>
      </div>

      <Tabs items={TABS} value={activeTab} onChange={(v) => setActiveTab(v as FilterTab)} className="mb-6" />

      {/* Content */}
      <div className="bg-surface border border-border rounded-xl">
        {error ? (
          <div className="p-10 text-center">
            <p className="text-sm text-danger mb-3">Veriler yüklenemedi.</p>
            <button onClick={loadData} className="text-xs text-accent hover:underline">Tekrar dene</button>
          </div>
        ) : approvals === null ? (
          <>
            <RowSkeleton /><RowSkeleton /><RowSkeleton /><RowSkeleton />
          </>
        ) : approvals.length === 0 ? (
          <div className="p-14 flex flex-col items-center text-center">
            <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-text mb-1">
              {activeTab === "pending" ? "Bekleyen onay yok" : "Kayıt bulunamadı"}
            </p>
            <p className="text-xs text-text-muted max-w-xs">
              {activeTab === "pending"
                ? "Şu an onay bekleyen içeriğiniz bulunmuyor."
                : "Seçili filtreye uygun onay bulunamadı."}
            </p>
          </div>
        ) : (
          <div>
            {approvals.map((a) => {
              const overdue = isOverdue(a.due_date, a.status);
              return (
                <Link
                  key={a.id}
                  href={`/brand/briefs/${a.brief_id}`}
                  className="flex items-center gap-4 p-5 border-b border-border last:border-0 hover:bg-surface-2 transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text group-hover:text-accent transition-colors truncate">
                      {a.brief_title}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      {a.agency_name && <span className="text-xs text-text-muted">{a.agency_name}</span>}
                      {a.content_types.length > 0 && (
                        <span className="text-xs text-text-muted/70">· {a.content_types.join(", ")}</span>
                      )}
                      {a.requested_by_name && (
                        <span className="text-xs text-text-muted/70">· {a.requested_by_name}</span>
                      )}
                      {a.due_date && (
                        <span className={`text-xs ${overdue ? "text-danger font-medium" : "text-text-muted"}`}>
                          · Son tarih: {formatDate(a.due_date)}
                        </span>
                      )}
                      {overdue && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-danger/10 text-danger">
                          Gecikti
                        </span>
                      )}
                      {a.comment_count > 0 && (
                        <span className="inline-flex items-center gap-1 text-xs text-text-muted/70">
                          <MessageSquare className="w-3 h-3" />
                          {a.comment_count}
                        </span>
                      )}
                    </div>
                  </div>
                  <StatusBadge status={a.status} />
                  <ArrowRight className="w-4 h-4 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
