"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, platformApi, type PlatformAuditLogRead } from "@/lib/api-client";
import { platformAuthStorage } from "@/lib/platform-auth";
import { AlertTriangle, ChevronDown, ChevronUp, Shield } from "lucide-react";

const ACTION_CLASSES: Record<string, string> = {
  "impersonation.started":   "bg-warning/12 text-warning-text border-warning/20",
  "impersonation.ended":     "bg-warning/8  text-warning-text border-warning/15",
  "agency.suspended":        "bg-danger/12  text-danger-text  border-danger/20",
  "agency.reactivated":      "bg-success/12 text-success-text border-success/20",
  "user.deactivated":        "bg-danger/12  text-danger-text  border-danger/20",
  "user.reactivated":        "bg-success/12 text-success-text border-success/20",
  "subscription.overridden": "bg-info/12    text-info-text    border-info/20",
  "admin.login":             "bg-surface-3  text-text-muted   border-border",
};

const ACTION_FILTERS = [
  "impersonation.started",
  "impersonation.ended",
  "agency.suspended",
  "agency.reactivated",
  "user.deactivated",
  "user.reactivated",
  "subscription.overridden",
  "admin.login",
];

function ActionBadge({ action }: { action: string }) {
  const cls = ACTION_CLASSES[action] ?? "bg-surface-3 text-text-muted border-border";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono border ${cls}`}>
      {action}
    </span>
  );
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString("tr-TR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PlatformAuditLogPage() {
  const router = useRouter();
  const [logs,         setLogs]         = useState<PlatformAuditLogRead[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState("");
  const [expandedId,   setExpandedId]   = useState<string | null>(null);

  async function load(filter?: string) {
    const token = platformAuthStorage.getToken();
    if (!token) { router.replace("/platform/login"); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await platformApi.listAuditLogs(token, {
        action_filter: filter || undefined,
        limit: 100,
      });
      setLogs(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        platformAuthStorage.clearAll();
        router.replace("/platform/login");
      } else {
        setError(err instanceof ApiError ? err.message : "Veriler yüklenemedi");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(actionFilter); }, [actionFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <p className="text-xs font-semibold text-accent uppercase tracking-wider mb-1">
            Güvenlik
          </p>
          <h1 className="text-2xl font-bold text-text tracking-tight">Denetim Günlüğü</h1>
          <p className="text-sm text-text-muted mt-1">
            Platform admin aksiyonlarının değiştirilemez kaydı
          </p>
        </div>
        {/* Immutable indicator */}
        <div className="flex items-center gap-2 px-3 py-2 bg-surface border border-border rounded-lg text-xs text-text-muted">
          <Shield className="w-3.5 h-3.5 text-success" />
          <span>Değiştirilemez kayıtlar</span>
        </div>
      </div>

      {/* Filter */}
      <div className="mb-6">
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent transition-colors"
        >
          <option value="">Tüm aksiyonlar</option>
          {ACTION_FILTERS.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mb-6 flex items-start gap-2.5 bg-danger/8 border border-danger/20 rounded-xl px-4 py-3">
          <AlertTriangle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Log list */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        {loading && (
          <div className="divide-y divide-border">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="h-5 w-44 bg-surface-2 rounded animate-pulse" />
                  <div className="h-4 w-52 bg-surface-2 rounded animate-pulse" />
                  <div className="h-4 w-28 bg-surface-2 rounded animate-pulse ml-auto" />
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && logs.length === 0 && (
          <div className="px-5 py-16 text-center text-text-muted opacity-60">
            Denetim kaydı bulunamadı
          </div>
        )}

        {!loading && (
          <div className="divide-y divide-border">
            {logs.map((log) => (
              <div
                key={log.id}
                className="px-5 py-4 hover:bg-surface-2 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3 flex-wrap min-w-0">
                    <ActionBadge action={log.action} />
                    {log.target_type && (
                      <span className="text-xs text-text-muted">
                        {log.target_type}
                        {log.target_id ? ` ${log.target_id.slice(0, 8)}…` : ""}
                      </span>
                    )}
                    <span className="text-xs text-text-muted font-mono opacity-60">
                      admin:{log.admin_user_id.slice(0, 8)}…
                    </span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-xs text-text-muted">
                      {fmtDateTime(log.created_at)}
                    </span>
                    {log.meta && Object.keys(log.meta).length > 0 && (
                      <button
                        onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                        className="text-text-muted hover:text-text transition-colors"
                        aria-label={expandedId === log.id ? "Detayı kapat" : "Detayı göster"}
                      >
                        {expandedId === log.id
                          ? <ChevronUp className="w-3.5 h-3.5" />
                          : <ChevronDown className="w-3.5 h-3.5" />
                        }
                      </button>
                    )}
                  </div>
                </div>

                {expandedId === log.id && log.meta && (
                  <div className="mt-3 ml-1">
                    <pre className="text-xs text-text-muted bg-surface-2 border border-border rounded-lg p-3 overflow-x-auto font-mono whitespace-pre-wrap">
                      {JSON.stringify(log.meta, null, 2)}
                    </pre>
                    {log.ip_address && (
                      <p className="text-xs text-text-muted mt-2 opacity-70">
                        IP: {log.ip_address}
                        {log.user_agent ? ` · UA: ${log.user_agent.slice(0, 60)}…` : ""}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
