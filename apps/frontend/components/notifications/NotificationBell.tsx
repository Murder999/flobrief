"use client";

import { Bell, CheckCheck, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn, isSafeInternalPath } from "@/lib/utils";
import { useNotificationFeed, type NotificationFeedSource } from "./useNotificationFeed";

const PANEL_WIDTH = 320;
const VIEWPORT_MARGIN = 8;

interface NotificationBellProps {
  source: NotificationFeedSource | null;
  /** Route to the full notifications page, e.g. "/dashboard/notifications" or "/brand/notifications" */
  basePath: string;
  /** Fires whenever the polled unread count changes — lets a parent shell
   * (e.g. MobileBottomNavigation's badge) reuse this bell's own polling
   * instead of running a second independent useNotificationFeed. */
  onUnreadCountChange?: (count: number) => void;
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "az önce";
  if (minutes < 60) return `${minutes}dk`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}sa`;
  const days = Math.floor(hours / 24);
  return `${days}g`;
}

export function NotificationBell({ source, basePath, onUnreadCountChange }: NotificationBellProps) {
  const { unreadCount, recent, markRead, markAllRead } = useNotificationFeed(source);

  useEffect(() => {
    onUnreadCountChange?.(unreadCount);
  }, [unreadCount, onUnreadCountChange]);
  const [isOpen, setIsOpen] = useState(false);
  const [panelPos, setPanelPos] = useState<{ top: number; left: number } | null>(null);
  const [mounted, setMounted] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const router = useRouter();
  const navigatingIdRef = useRef<string | null>(null);

  const handleOpenNotification = (n: { id: string; is_read: boolean; action_url: string | null }) => {
    if (navigatingIdRef.current === n.id) return; // guards rapid repeat clicks on the same item
    navigatingIdRef.current = n.id;
    setIsOpen(false);
    const markReadPromise = n.is_read ? Promise.resolve() : markRead(n.id).catch(() => undefined);
    // Navigate regardless of whether marking-as-read succeeds — a failed read
    // receipt must never block the user from reaching the content.
    void markReadPromise.finally(() => {
      if (isSafeInternalPath(n.action_url)) router.push(n.action_url);
      navigatingIdRef.current = null;
    });
  };

  useEffect(() => setMounted(true), []);

  const computePosition = () => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const left = Math.min(
      Math.max(VIEWPORT_MARGIN, rect.left),
      window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN
    );
    setPanelPos({ top: rect.bottom + 8, left });
  };

  const toggleOpen = () => {
    setIsOpen((v) => {
      const next = !v;
      if (next) computePosition();
      return next;
    });
  };

  // Once the panel has actually rendered (and we know its real height), flip
  // it above the button — or clamp it to the viewport — if it would overflow
  // the bottom edge. computePosition() alone can't do this: it runs before
  // the portaled panel exists, so it only had the button's position to go on.
  useEffect(() => {
    if (!isOpen || !panelPos) return;
    const panel = panelRef.current;
    const btn = buttonRef.current;
    if (!panel || !btn) return;
    const panelRect = panel.getBoundingClientRect();
    if (panelRect.bottom > window.innerHeight - VIEWPORT_MARGIN) {
      const btnRect = btn.getBoundingClientRect();
      const flippedTop = btnRect.top - panelRect.height - 8;
      const top = flippedTop >= VIEWPORT_MARGIN
        ? flippedTop
        : Math.max(VIEWPORT_MARGIN, window.innerHeight - panelRect.height - VIEWPORT_MARGIN);
      setPanelPos((prev) => (prev && prev.top !== top ? { ...prev, top } : prev));
    }
  }, [isOpen, panelPos]);

  // Closes on outside click (checking both the button and the portaled panel,
  // since the panel is no longer a DOM descendant of the button's container),
  // on Escape, and on scroll/resize, since a stale position would otherwise
  // float away from the button it's anchored to.
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (buttonRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setIsOpen(false);
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    };
    const handleScrollOrResize = () => setIsOpen(false);
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScrollOrResize, true);
      window.removeEventListener("resize", handleScrollOrResize);
    };
  }, [isOpen]);

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={toggleOpen}
        className="relative p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-hover transition-all"
        title="Bildirimler"
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
      >
        <Bell className="w-3.5 h-3.5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 bg-accent text-white text-[9px] font-bold rounded-full flex items-center justify-center px-0.5">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && mounted && panelPos &&
        createPortal(
          <div
            ref={panelRef}
            id={panelId}
            role="dialog"
            aria-label="Bildirimler"
            style={{ position: "fixed", top: panelPos.top, left: panelPos.left, width: PANEL_WIDTH }}
            className="max-w-[90vw] bg-surface border border-border rounded-xl shadow-modal z-[9999] overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="text-xs font-semibold text-text">Bildirimler</span>
              {unreadCount > 0 && (
                <button
                  onClick={() => markAllRead()}
                  className="flex items-center gap-1 text-[11px] text-accent hover:text-accent-2 transition-colors"
                >
                  <CheckCheck className="w-3 h-3" />
                  Tümünü okundu yap
                </button>
              )}
            </div>

            <div className="max-h-80 overflow-y-auto">
              {recent.length === 0 ? (
                <div className="px-4 py-8 text-center text-xs text-text-muted">
                  Henüz bildirim yok
                </div>
              ) : (
                recent.map((n) => (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => handleOpenNotification(n)}
                    className={cn(
                      "w-full text-left px-4 py-3 border-b border-border/60 last:border-0 transition-colors hover:bg-hover focus-visible:bg-hover focus-visible:outline-none",
                      !n.is_read && "bg-accent-subtle/40"
                    )}
                  >
                    <div className="flex items-start gap-2">
                      {!n.is_read && (
                        <span className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 flex-shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-[12.5px] font-medium text-text truncate">{n.title}</p>
                        <p className="text-[11.5px] text-text-muted line-clamp-2 mt-0.5">{n.body}</p>
                        <p className="text-[10px] text-text-muted/70 mt-1">{timeAgo(n.created_at)}</p>
                      </div>
                      {isSafeInternalPath(n.action_url) && (
                        <ChevronRight className="w-3.5 h-3.5 text-text-muted/50 flex-shrink-0 mt-0.5" aria-hidden="true" />
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>

            <Link
              href={basePath}
              onClick={() => setIsOpen(false)}
              className="block px-4 py-2.5 text-center text-[12px] font-medium text-accent hover:bg-hover border-t border-border transition-colors"
            >
              Tüm bildirimleri gör
            </Link>
          </div>,
          document.body
        )}
    </div>
  );
}
