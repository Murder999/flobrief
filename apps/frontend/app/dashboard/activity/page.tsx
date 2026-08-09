"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { activityApi, type ActivityLogRead } from "@/lib/api-client";
import { useEffect, useState, useCallback } from "react";

const ENTITY_TYPES = [
  { value: "", label: "Tümü" },
  { value: "brief", label: "Brief" },
  { value: "calendar_item", label: "Takvim" },
  { value: "agency", label: "Ajans" },
  { value: "brand", label: "Marka" },
  { value: "user", label: "Kullanıcı" },
  { value: "approval", label: "Onay" },
  { value: "asset", label: "Dosya" },
  { value: "subscription", label: "Abonelik" },
];

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    created: "oluşturdu",
    updated: "güncelledi",
    deleted: "sildi",
    archived: "arşivledi",
    submitted: "gönderdi",
    approved: "onayladı",
    rejected: "reddetti",
    invited: "davet etti",
    joined: "katıldı",
    published: "yayınladı",
  };
  const parts = action.split(".");
  const verb = parts[parts.length - 1];
  return map[verb] ?? action;
}

function EntityIcon({ entityType }: { entityType: string }) {
  const cls = "w-4 h-4";
  switch (entityType) {
    case "brief":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
    case "calendar_item":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      );
    case "agency":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      );
    case "brand":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
        </svg>
      );
    case "user":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      );
    case "approval":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case "asset":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      );
    case "subscription":
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
        </svg>
      );
    default:
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 12m-3 0a3 3 0 106 0 3 3 0 00-6 0" />
        </svg>
      );
  }
}

function entityColor(entityType: string): string {
  const map: Record<string, string> = {
    brief: "bg-indigo-500/15 text-indigo-400",
    calendar_item: "bg-cyan-500/15 text-cyan-400",
    agency: "bg-violet-500/15 text-violet-400",
    brand: "bg-amber-500/15 text-amber-400",
    user: "bg-emerald-500/15 text-emerald-400",
    approval: "bg-rose-500/15 text-rose-400",
    asset: "bg-blue-500/15 text-blue-400",
    subscription: "bg-purple-500/15 text-purple-400",
  };
  return map[entityType] ?? "bg-surface-2 text-text-muted";
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "şimdi";
  if (mins < 60) return `${mins}dk önce`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}s önce`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}g önce`;
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

function ActivitySkeleton() {
  return (
    <div className="flex gap-4 py-4 animate-pulse">
      <div className="w-8 h-8 rounded-lg bg-surface-2 flex-shrink-0" />
      <div className="flex-1 space-y-2 pt-1">
        <div className="h-3.5 bg-surface-2 rounded w-64" />
        <div className="h-3 bg-surface-2 rounded w-32" />
      </div>
    </div>
  );
}

export default function ActivityPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [items, setItems] = useState<ActivityLogRead[]>([]);
  const [total, setTotal] = useState(0);
  const [entityType, setEntityType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const LIMIT = 30;

  const fetch = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await activityApi.list(agencyId, accessToken, {
        entity_type: entityType || undefined,
        limit: LIMIT,
        offset,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, entityType, offset]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !agencyId) {
      setLoading(false);
    }
  }, [workspaceReady, workspaceLoading, agencyId]);

  useEffect(() => {
    setOffset(0);
  }, [entityType]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-text">Aktivite Günlüğü</h1>
          <p className="text-sm text-text-muted mt-1">Ajans genelindeki tüm işlemler</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        {ENTITY_TYPES.map((et) => (
          <button
            key={et.value}
            onClick={() => setEntityType(et.value)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              entityType === et.value
                ? "bg-accent text-white"
                : "bg-surface-2 text-text-muted hover:text-text hover:bg-surface-2/80"
            }`}
          >
            {et.label}
          </button>
        ))}
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        {!loading && items.length > 0 && (
          <div className="absolute left-4 top-4 bottom-4 w-px bg-border" />
        )}

        {!loading && !agencyId ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <p className="text-base font-medium text-text">Ajans seçilmedi</p>
            <p className="text-sm text-text-muted mt-1 mb-4">Aktivite günlüğünü görüntülemek için bir ajans seçin.</p>
            <a href="/onboarding/create-agency" className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors">Ajans Oluştur</a>
          </div>
        ) : error ? (
          <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
            {error}
          </div>
        ) : loading ? (
          <div className="space-y-1">
            {Array.from({ length: 8 }).map((_, i) => (
              <ActivitySkeleton key={i} />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <p className="text-base font-medium text-text">Aktivite yok</p>
            <p className="text-sm text-text-muted mt-1">
              {entityType ? "Bu kategoride kayıt bulunamadı." : "Henüz aktivite kaydı yok."}
            </p>
          </div>
        ) : (
          <div className="space-y-0">
            {items.map((log) => (
              <div key={log.id} className="flex gap-4 py-3 relative">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 relative z-10 ${entityColor(log.entity_type)}`}
                >
                  <EntityIcon entityType={log.entity_type} />
                </div>
                <div className="flex-1 min-w-0 pt-1">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <span className="text-sm text-text">
                        <span className="font-medium capitalize">{log.entity_type}</span>{" "}
                        <span className="text-text-muted">{actionLabel(log.action)}</span>
                      </span>
                      {log.meta && Object.keys(log.meta).length > 0 && (
                        <p className="text-xs text-text-muted mt-0.5 truncate max-w-xs">
                          {Object.entries(log.meta)
                            .slice(0, 2)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(" · ")}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-text-muted whitespace-nowrap flex-shrink-0">
                      {timeAgo(log.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {!loading && total > LIMIT && (
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
          <button
            onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
            disabled={offset === 0}
            className="text-sm text-text-muted hover:text-text disabled:opacity-40 transition-colors"
          >
            ← Önceki
          </button>
          <span className="text-sm text-text-muted">
            {offset + 1}–{Math.min(offset + LIMIT, total)} / {total}
          </span>
          <button
            onClick={() => setOffset((o) => o + LIMIT)}
            disabled={offset + LIMIT >= total}
            className="text-sm text-text-muted hover:text-text disabled:opacity-40 transition-colors"
          >
            Sonraki →
          </button>
        </div>
      )}
    </div>
  );
}
