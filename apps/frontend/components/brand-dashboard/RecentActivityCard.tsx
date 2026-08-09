"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import { Activity, MessageSquare, Package, RotateCcw, CheckCircle, CalendarClock, FileText, Bell } from "lucide-react";
import type { NotificationRead } from "@/lib/api-client";
import { cn, isSafeInternalPath } from "@/lib/utils";
import { bucketForEventType, activityDotCls, fmtRelative, type ActivityBucket } from "./shared";

const BUCKET_ICON: Record<ActivityBucket, typeof Package> = {
  deliverable: Package,
  comment: MessageSquare,
  approval: CheckCircle,
  revision: RotateCcw,
  calendar: CalendarClock,
  brief: FileText,
  other: Bell,
};

function RowSkeleton() {
  return (
    <div className="flex items-start gap-3 px-4 py-2.5 border-b border-border last:border-0 animate-pulse">
      <div className="mt-0.5 h-6 w-6 rounded-lg bg-surface-2" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 w-40 rounded bg-surface-2" />
        <div className="h-2.5 w-56 rounded bg-surface-2" />
      </div>
    </div>
  );
}

export function RecentActivityCard({
  notifications, onMarkRead,
}: {
  notifications: NotificationRead[] | null;
  onMarkRead: (id: string) => Promise<unknown>;
}) {
  const router = useRouter();
  const navigatingIdRef = useRef<string | null>(null);
  const items = (notifications ?? []).slice(0, 5);

  function open(n: NotificationRead) {
    if (navigatingIdRef.current === n.id) return;
    navigatingIdRef.current = n.id;
    const markReadPromise = n.is_read ? Promise.resolve() : onMarkRead(n.id).catch(() => undefined);
    void markReadPromise.finally(() => {
      if (isSafeInternalPath(n.action_url)) router.push(n.action_url);
      navigatingIdRef.current = null;
    });
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <Activity className="h-4 w-4 text-accent" />
        <h2 className="text-sm font-semibold text-text">Son Hareketler</h2>
      </div>

      {notifications === null ? (
        <>
          <RowSkeleton />
          <RowSkeleton />
        </>
      ) : items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1.5 px-4 py-6 text-center">
          <p className="text-[13px] font-medium text-text">Henüz bir hareket yok</p>
          <p className="text-[11.5px] text-text-muted">Yeni gelişmeler burada listelenecek.</p>
        </div>
      ) : (
        <div>
          {items.map((n) => {
            const Icon = BUCKET_ICON[bucketForEventType(n.event_type)];
            const clickable = isSafeInternalPath(n.action_url);
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => clickable && open(n)}
                className={cn(
                  "flex w-full items-start gap-3 px-4 py-2.5 border-b border-border last:border-0 text-left transition-colors",
                  clickable ? "hover:bg-surface-2 cursor-pointer" : "cursor-default"
                )}
              >
                <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-surface-2">
                  <Icon className="h-3.5 w-3.5 text-text-muted" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className={cn("h-1.5 w-1.5 flex-shrink-0 rounded-full", activityDotCls(n))} />
                    <p className="truncate text-[13px] text-text">{n.title}</p>
                  </div>
                  <p className="mt-0.5 line-clamp-1 text-[11.5px] text-text-muted">{n.body}</p>
                </div>
                <span className="flex-shrink-0 text-[10.5px] text-text-muted/70">{fmtRelative(n.created_at)}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
