"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { notificationApi, type NotificationRead } from "@/lib/api-client";
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { isSafeInternalPath } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { useLocale } from "@/context/locale-context";
import { localizeNotification } from "@/lib/i18n/notification-presentation";
import { translate } from "@/lib/i18n/translate";
import type { Locale } from "@/lib/i18n/config";

function timeAgo(iso: string, locale: Locale): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return translate(locale, "briefs.time.justNow");
  if (mins < 60) return translate(locale, "briefs.time.minutesAgo", { count: mins });
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return translate(locale, "briefs.time.hoursAgo", { count: hrs });
  return translate(locale, "briefs.time.daysAgo", { count: Math.floor(hrs / 24) });
}

function eventColor(eventType: string): string {
  if (eventType.startsWith("brief.approved")) return "text-emerald-400";
  if (eventType.includes("revision") || eventType.includes("failed")) return "text-amber-400";
  if (eventType.startsWith("brief.")) return "text-indigo-400";
  if (eventType.startsWith("calendar.")) return "text-cyan-400";
  if (eventType.startsWith("subscription.")) return "text-violet-400";
  return "text-text-muted";
}

function eventDotColor(eventType: string): string {
  if (eventType.startsWith("brief.approved")) return "bg-emerald-500";
  if (eventType.includes("revision") || eventType.includes("failed")) return "bg-amber-500";
  if (eventType.startsWith("brief.")) return "bg-indigo-500";
  if (eventType.startsWith("calendar.")) return "bg-cyan-500";
  if (eventType.startsWith("subscription.")) return "bg-violet-500";
  return "bg-text-muted";
}

function NotificationIcon({ eventType }: { eventType: string }) {
  const cls = "w-4 h-4";
  if (eventType.startsWith("brief.approved")) {
    return (
      <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    );
  }
  if (eventType.startsWith("brief.")) {
    return (
      <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    );
  }
  if (eventType.startsWith("calendar.")) {
    return (
      <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    );
  }
  if (eventType.startsWith("subscription.")) {
    return (
      <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
      </svg>
    );
  }
  if (eventType.startsWith("user.")) {
    return (
      <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    );
  }
  return (
    <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  );
}

function NotificationSkeleton() {
  return (
    <div className="flex gap-4 p-4 border-b border-border animate-pulse">
      <div className="w-2 h-2 mt-2 rounded-full bg-surface-2 flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3.5 bg-surface-2 rounded w-48" />
        <div className="h-3 bg-surface-2 rounded w-72" />
        <div className="h-2.5 bg-surface-2 rounded w-20" />
      </div>
    </div>
  );
}

export default function NotificationsPage() {
  const { locale, t } = useLocale();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const router = useRouter();
  const navigatingIdRef = useRef<string | null>(null);

  const [items, setItems] = useState<NotificationRead[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [loading, setLoading] = useState(true);
  const [markingAll, setMarkingAll] = useState(false);
  const [offset, setOffset] = useState(0);
  const LIMIT = 20;

  const fetch = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    try {
      const data = await notificationApi.list(agencyId, accessToken, {
        is_read: filter === "unread" ? false : undefined,
        limit: LIMIT,
        offset,
      });
      setItems(data.items);
      setTotal(data.total);
      setUnreadCount(data.unread_count ?? 0);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, filter, offset]);

  useEffect(() => {
    setOffset(0);
  }, [filter]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const handleMarkRead = async (id: string) => {
    if (!accessToken || !agencyId) return;
    try {
      const updated = await notificationApi.markRead(id, agencyId, accessToken);
      setItems((prev) => prev.map((n) => (n.id === id ? updated : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  };

  const handleOpenNotification = async (n: NotificationRead) => {
    if (navigatingIdRef.current === n.id) return;
    navigatingIdRef.current = n.id;
    if (!n.is_read) await handleMarkRead(n.id);
    if (isSafeInternalPath(n.action_url)) router.push(n.action_url);
    navigatingIdRef.current = null;
  };

  const handleMarkAllRead = async () => {
    if (!accessToken || !agencyId) return;
    setMarkingAll(true);
    try {
      await notificationApi.markAllRead(agencyId, accessToken);
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    } finally {
      setMarkingAll(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-text">{t("notifications.title")}</h1>
          {unreadCount > 0 && (
            <p className="text-sm text-text-muted mt-1">
              {t("notifications.unreadCount", { count: unreadCount })}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-surface-2 rounded-lg p-0.5">
            {(["all", "unread"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  filter === f
                    ? "bg-surface text-text shadow-sm"
                    : "text-text-muted hover:text-text"
                }`}
              >
                {t(f === "all" ? "notifications.filter.all" : "notifications.filter.unread")}
              </button>
            ))}
          </div>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              disabled={markingAll}
              className="text-sm text-accent hover:text-accent/80 transition-colors disabled:opacity-50"
            >
              {markingAll ? t("notifications.processing") : t("notifications.markAllRead")}
            </button>
          )}
        </div>
      </div>

      {/* List */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => <NotificationSkeleton key={i} />)
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
              <svg className="w-7 h-7 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </div>
            <p className="text-base font-medium text-text">{t("notifications.emptyTitle")}</p>
            <p className="text-sm text-text-muted mt-1">
              {t(filter === "unread" ? "notifications.emptyUnread" : "notifications.empty")}
            </p>
          </div>
        ) : (
          items.map((n) => {
            const localized = localizeNotification(n, locale);
            return (
            <button
              key={n.id}
              type="button"
              onClick={() => handleOpenNotification(n)}
              className={`w-full text-left flex gap-4 px-5 py-4 border-b border-border last:border-b-0 transition-colors focus-visible:outline-none focus-visible:bg-surface-2/50 ${
                !n.is_read ? "bg-surface" : "hover:bg-surface-2/50"
              }`}
            >
              {/* Icon circle with colored dot */}
              <div className="relative flex-shrink-0 mt-0.5">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${eventColor(n.event_type)} bg-current/10`}
                  style={{ backgroundColor: undefined }}
                >
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                    n.event_type.startsWith("brief.approved") ? "bg-emerald-500/10 text-emerald-500" :
                    n.event_type.includes("revision") || n.event_type.includes("failed") ? "bg-amber-500/10 text-amber-500" :
                    n.event_type.startsWith("brief.") ? "bg-indigo-500/10 text-indigo-500" :
                    n.event_type.startsWith("calendar.") ? "bg-cyan-500/10 text-cyan-500" :
                    n.event_type.startsWith("subscription.") ? "bg-violet-500/10 text-violet-500" :
                    "bg-surface-2 text-text-muted"
                  }`}>
                    <NotificationIcon eventType={n.event_type} />
                  </div>
                </div>
                {!n.is_read && (
                  <span className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-surface ${eventDotColor(n.event_type)}`} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className={`text-sm font-semibold ${!n.is_read ? "text-text" : "text-text/80"}`}>
                      {localized.title}
                    </p>
                    <p className={`text-sm mt-0.5 leading-relaxed ${!n.is_read ? "text-text-muted" : "text-text-muted/70"}`}>{localized.body}</p>
                  </div>
                  <span className="text-xs text-text-muted whitespace-nowrap flex-shrink-0 mt-0.5">
                    {timeAgo(n.created_at, locale)}
                  </span>
                </div>
              </div>
              {isSafeInternalPath(n.action_url) && (
                <ChevronRight className="w-3.5 h-3.5 text-text-muted/50 flex-shrink-0 self-center" aria-hidden="true" />
              )}
            </button>
            );
          })
        )}
      </div>

      {/* Pagination */}
      {!loading && total > LIMIT && (
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
            disabled={offset === 0}
            className="text-sm text-text-muted hover:text-text disabled:opacity-40 transition-colors"
          >
            ← {t("notifications.previous")}
          </button>
          <span className="text-sm text-text-muted">
            {offset + 1}–{Math.min(offset + LIMIT, total)} / {total}
          </span>
          <button
            onClick={() => setOffset((o) => o + LIMIT)}
            disabled={offset + LIMIT >= total}
            className="text-sm text-text-muted hover:text-text disabled:opacity-40 transition-colors"
          >
            {t("notifications.next")} →
          </button>
        </div>
      )}
    </div>
  );
}
