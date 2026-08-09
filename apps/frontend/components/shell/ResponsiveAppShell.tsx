"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import type { NotificationFeedSource } from "@/components/notifications/useNotificationFeed";
import { subscribeMobileDrawerRequests } from "@/lib/mobile-drawer-bridge";
import { MobileBottomNavigation } from "./MobileBottomNavigation";
import { MobileNavigationDrawer } from "./MobileNavigationDrawer";
import { ResponsivePageHeader } from "./ResponsivePageHeader";
import type { BottomNavItem, NavDrawerGroup } from "./types";

interface ResponsiveAppShellProps {
  /** The existing desktop Sidebar/BrandSidebar element — already
   * responsive (`hidden lg:flex`) at the call site, rendered as-is. */
  sidebar: ReactNode;
  groups: NavDrawerGroup[];
  bottomNavItems: BottomNavItem[];
  brandTitle: string;
  brandSubtitle?: string;
  fallbackPageTitle: string;
  user: { name: string; email: string; initials: string } | null;
  profileHref: string;
  onLogout: () => void;
  notificationSource: NotificationFeedSource | null;
  notificationBasePath: string;
  showTimer?: boolean;
  children: ReactNode;
}

/**
 * Composition shared by the agency and brand layouts: desktop sidebar
 * (untouched, CSS-hidden below `lg`) + a mobile/tablet column of sticky
 * header, page content, and fixed bottom nav, plus the portal-rendered nav
 * drawer. Desktop DOM/CSS output is unchanged from the pre-4A layout — the
 * only addition is a neutral flex-column wrapper around `main`.
 */
export function ResponsiveAppShell({
  sidebar,
  groups,
  bottomNavItems,
  brandTitle,
  brandSubtitle,
  fallbackPageTitle,
  user,
  profileHref,
  onLogout,
  notificationSource,
  notificationBasePath,
  showTimer,
  children,
}: ResponsiveAppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  // Onboarding-spotlight bridge: a step whose target only lives in the
  // mobile drawer forces it open via `requestMobileDrawerOpen` (see
  // lib/mobile-drawer-bridge.ts) since the wizard is rendered outside this
  // component's subtree and has no other way to reach `drawerOpen`.
  useEffect(() => subscribeMobileDrawerRequests(setDrawerOpen), []);

  const bottomNavWithBadge = useMemo(
    () =>
      bottomNavItems.map((item) =>
        item.href === notificationBasePath ? { ...item, badge: unreadCount } : item
      ),
    [bottomNavItems, notificationBasePath, unreadCount]
  );

  return (
    <div className="flex min-h-screen bg-background">
      {sidebar}

      <div className="flex-1 flex flex-col min-w-0">
        <ResponsivePageHeader
          onMenuClick={() => setDrawerOpen(true)}
          menuOpen={drawerOpen}
          groups={groups}
          fallbackTitle={fallbackPageTitle}
          notificationSource={notificationSource}
          notificationBasePath={notificationBasePath}
          onUnreadCountChange={setUnreadCount}
          showTimer={showTimer}
          profileHref={profileHref}
          profileInitials={user?.initials ?? "?"}
        />

        <main className="flex-1 overflow-auto min-w-0 pb-[calc(3.5rem+env(safe-area-inset-bottom))] lg:pb-0">
          {children}
        </main>

        <MobileBottomNavigation
          items={bottomNavWithBadge}
          onMoreClick={() => setDrawerOpen(true)}
          moreActive={drawerOpen}
        />
      </div>

      <MobileNavigationDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        groups={groups}
        brandTitle={brandTitle}
        brandSubtitle={brandSubtitle}
        user={user}
        profileHref={profileHref}
        onLogout={onLogout}
      />
    </div>
  );
}
