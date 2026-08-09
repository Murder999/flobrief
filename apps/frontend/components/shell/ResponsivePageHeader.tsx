"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import type { NotificationFeedSource } from "@/components/notifications/useNotificationFeed";
import { GlobalTimerWidget } from "@/components/time-tracking/GlobalTimerWidget";
import { SafeAreaContainer } from "@/components/ui/safe-area-container";
import type { NavDrawerGroup } from "./types";

interface ResponsivePageHeaderProps {
  onMenuClick: () => void;
  menuOpen: boolean;
  groups: NavDrawerGroup[];
  fallbackTitle: string;
  notificationSource: NotificationFeedSource | null;
  notificationBasePath: string;
  onUnreadCountChange?: (count: number) => void;
  showTimer?: boolean;
  profileHref: string;
  profileInitials: string;
}

/** Longest-href-match against the same nav data the drawer renders, so the
 * mobile header's title always matches the drawer's active item without a
 * second, hand-maintained title map. */
function resolvePageTitle(pathname: string, groups: NavDrawerGroup[], fallback: string): string {
  let best: { href: string; label: string } | null = null;
  for (const group of groups) {
    for (const item of group.items) {
      const matches = item.exact ? pathname === item.href : pathname.startsWith(item.href);
      if (matches && (!best || item.href.length > best.href.length)) {
        best = item;
      }
    }
  }
  return best?.label ?? fallback;
}

/** Sticky mobile/tablet top bar (`lg:hidden`) — desktop keeps the plain
 * sidebar-only layout with no header row at all. */
export function ResponsivePageHeader({
  onMenuClick,
  menuOpen,
  groups,
  fallbackTitle,
  notificationSource,
  notificationBasePath,
  onUnreadCountChange,
  showTimer,
  profileHref,
  profileInitials,
}: ResponsivePageHeaderProps) {
  const pathname = usePathname();
  const title = useMemo(() => resolvePageTitle(pathname, groups, fallbackTitle), [pathname, groups, fallbackTitle]);

  return (
    <SafeAreaContainer
      top
      minTop="0px"
      className="lg:hidden sticky top-0 z-30 bg-surface/95 backdrop-blur-md border-b border-border"
    >
      <div className="flex items-center gap-2 px-3 h-14">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Menüyü aç"
          aria-expanded={menuOpen}
          aria-controls="mobile-nav-drawer"
          className="w-11 h-11 -ml-1.5 flex items-center justify-center rounded-lg text-text-secondary hover:text-text hover:bg-hover transition-colors flex-shrink-0"
        >
          <Menu className="w-5 h-5" />
        </button>

        <h1 className="flex-1 min-w-0 text-sm font-semibold text-text tracking-tight truncate">{title}</h1>

        <div className="flex items-center gap-0.5 flex-shrink-0">
          {showTimer && <GlobalTimerWidget />}
          <NotificationBell
            source={notificationSource}
            basePath={notificationBasePath}
            onUnreadCountChange={onUnreadCountChange}
          />
          <Link
            href={profileHref}
            aria-label="Profil"
            className="w-11 h-11 flex items-center justify-center rounded-lg hover:bg-hover transition-colors"
          >
            <span
              className="w-7 h-7 rounded-full flex items-center justify-center ring-2 ring-accent/25"
              style={{ background: "var(--gradient-accent)" }}
            >
              <span className="text-[10px] font-bold text-white">{profileInitials}</span>
            </span>
          </Link>
        </div>
      </div>
    </SafeAreaContainer>
  );
}
