"use client";

import { WhatsAppPreferencesPanel } from "@/components/notifications/WhatsAppPreferencesPanel";
import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, type NotificationRead } from "@/lib/api-client";
import { Tabs, type TabItem } from "@/components/ui/tabs";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bell, CheckCheck, Archive, ChevronRight } from "lucide-react";
import { isSafeInternalPath } from "@/lib/utils";

type Category =
  | "all"
  | "unread"
  | "approvals"
  | "briefs"
  | "comments"
  | "files"
  | "team"
  | "system"
  | "settings";

const APPROVAL_PREFIXES = ["brief.approved", "brief.revision_requested", "brief.rejected", "public_approval."];
const BRIEF_PREFIXES = ["brief."];
const COMMENT_PREFIXES = ["comment."];
const FILE_PREFIXES = ["file."];
const TEAM_PREFIXES = ["user.invited", "invitation."];

function categoryOf(eventType: string): Category {
  if (APPROVAL_PREFIXES.some((p) => eventType.startsWith(p))) return "approvals";
  if (COMMENT_PREFIXES.some((p) => eventType.startsWith(p))) return "comments";
  if (FILE_PREFIXES.some((p) => eventType.startsWith(p))) return "files";
  if (TEAM_PREFIXES.some((p) => eventType.startsWith(p))) return "team";
  if (BRIEF_PREFIXES.some((p) => eventType.startsWith(p))) return "briefs";
  return "system";
}

function routeFor(category: Category): string {
  switch (category) {
    case "approvals": return "/brand/approvals";
    case "briefs": return "/brand/briefs";
    case "comments": return "/brand/briefs";
    case "files": return "/brand/files";
    case "team": return "/brand/team";
    default: return "/brand/dashboard";
  }
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "şimdi";
  if (mins < 60) return `${mins}dk önce`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}s önce`;
  return `${Math.floor(hrs / 24)}g önce`;
}

const TAB_LABELS: TabItem[] = [
  { value: "all", label: "Tümü" },
  { value: "unread", label: "Okunmamış" },
  { value: "approvals", label: "Onaylar" },
  { value: "briefs", label: "Briefler" },
  { value: "comments", label: "Yorumlar" },
  { value: "files", label: "Dosyalar" },
  { value: "team", label: "Ekip" },
  { value: "system", label: "Sistem" },
  { value: "settings", label: "Ayarlar" },
];

export default function BrandNotificationsPage() {
  const { accessToken } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [items, setItems] = useState<NotificationRead[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [tab, setTab] = useState<Category>(
    searchParams.get("tab") === "settings" ? "settings" : "all"
  );
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const navigatingIdRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || tab === "settings") return;
    setLoading(true);
    try {
      const data = await brandPortalApi.listNotifications(accessToken, {
        unread_only: tab === "unread",
        limit: 50,
      });
      setItems(data.items);
      setUnreadCount(data.unread_count);
    } catch {
      // silent — empty-state renders naturally
    } finally {
      setLoading(false);
    }
  }, [accessToken, tab]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    if (tab === "all" || tab === "unread") return items;
    return items.filter((n) => categoryOf(n.event_type) === tab);
  }, [items, tab]);

  const tabsWithCounts = useMemo(
    () => TAB_LABELS.map((t) => (t.value === "unread" ? { ...t, count: unreadCount } : t)),
    [unreadCount]
  );

  const handleOpen = async (n: NotificationRead) => {
    if (!accessToken || navigatingIdRef.current === n.id) return;
    navigatingIdRef.current = n.id;
    if (!n.is_read) {
      setBusyId(n.id);
      try {
        await brandPortalApi.markNotificationRead(n.id, accessToken);
        setItems((prev) => prev.map((it) => (it.id === n.id ? { ...it, is_read: true } : it)));
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch {
        // A failed read receipt must never block navigation to the content.
      } finally {
        setBusyId(null);
      }
    }
    router.push(isSafeInternalPath(n.action_url) ? n.action_url : routeFor(categoryOf(n.event_type)));
    navigatingIdRef.current = null;
  };

  const handleArchive = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!accessToken) return;
    setBusyId(id);
    try {
      await brandPortalApi.archiveNotification(id, accessToken);
      setItems((prev) => prev.filter((it) => it.id !== id));
    } finally {
      setBusyId(null);
    }
  };

  const handleMarkAllRead = async () => {
    if (!accessToken) return;
    await brandPortalApi.markAllNotificationsRead(accessToken);
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-text">Bildirimler</h1>
          {unreadCount > 0 && (
            <p className="text-sm text-text-muted mt-1">{unreadCount} okunmamış bildirim</p>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAllRead}
            className="flex items-center gap-1.5 text-sm text-accent hover:text-accent-2 transition-colors"
          >
            <CheckCheck className="w-4 h-4" />
            Tümünü okundu yap
          </button>
        )}
      </div>

      <Tabs items={tabsWithCounts} value={tab} onChange={(v) => setTab(v as Category)} className="mb-4" />

      {tab === "settings" ? (
        <WhatsAppPreferencesPanel
          accessToken={accessToken}
          agencyId={null}
          portal="brand"
          phoneSettingsHref="/brand/settings"
        />
      ) : (
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex gap-4 p-4 border-b border-border animate-pulse">
              <div className="w-2 h-2 mt-2 rounded-full bg-surface-2 flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3.5 bg-surface-2 rounded w-48" />
                <div className="h-3 bg-surface-2 rounded w-72" />
              </div>
            </div>
          ))
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-14 h-14 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
              <Bell className="w-6 h-6 text-text-muted" />
            </div>
            <p className="text-base font-medium text-text">Bildirim yok</p>
            <p className="text-sm text-text-muted mt-1">Bu kategoride henüz bildirim yok.</p>
          </div>
        ) : (
          filtered.map((n) => (
            <div
              key={n.id}
              className={`group relative flex items-start gap-3 border-b border-border last:border-b-0 transition-colors ${
                !n.is_read ? "bg-accent-subtle/30" : "hover:bg-surface-2/50"
              } ${busyId === n.id ? "opacity-60 pointer-events-none" : ""}`}
            >
              <button
                type="button"
                onClick={() => handleOpen(n)}
                className="flex-1 min-w-0 flex items-start gap-3 px-5 py-4 text-left focus-visible:outline-none focus-visible:bg-hover"
              >
                {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-accent mt-2 flex-shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-semibold ${!n.is_read ? "text-text" : "text-text/80"}`}>{n.title}</p>
                  <p className="text-sm text-text-muted mt-0.5 leading-relaxed">{n.body}</p>
                  <p className="text-xs text-text-muted/70 mt-1.5">{timeAgo(n.created_at)}</p>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-text-muted/50 flex-shrink-0 mt-0.5" aria-hidden="true" />
              </button>
              <button
                onClick={(e) => handleArchive(e, n.id)}
                className="absolute right-3 top-3 opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-hover transition-all flex-shrink-0"
                title="Arşivle"
              >
                <Archive className="w-3.5 h-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
      )}
    </div>
  );
}
