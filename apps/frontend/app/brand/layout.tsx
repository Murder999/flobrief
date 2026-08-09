"use client";

import { useAuth } from "@/hooks/useAuth";
import { getInitials } from "@/lib/auth";
import { brandPortalApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import type { NotificationFeedSource } from "@/components/notifications/useNotificationFeed";
import { BrandOnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useOnboardingPageSeen } from "@/hooks/useOnboardingPageSeen";
import { ResponsiveAppShell } from "@/components/shell/ResponsiveAppShell";
import type { BottomNavItem, NavDrawerGroup, NavIcon } from "@/components/shell/types";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  LayoutDashboard, CheckCircle, FileText, Calendar,
  FolderOpen, BarChart3, Settings2, LogOut, PlusSquare, Dna, Users, Bell, Receipt,
} from "lucide-react";

const BRAND_MANAGER_ROLES = new Set(["brand_owner", "brand_manager"]);

interface NavItem {
  href: string;
  label: string;
  icon: NavIcon;
  exact?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Genel",
    items: [
      { href: "/brand/dashboard", label: "Genel Bakış", icon: LayoutDashboard, exact: true },
    ],
  },
  {
    title: "İş Akışı",
    items: [
      { href: "/brand/briefs/new", label: "Brief Ver", icon: PlusSquare, exact: true },
      { href: "/brand/briefs", label: "Brieflerim", icon: FileText },
      { href: "/brand/approvals", label: "Onaylar", icon: CheckCircle },
      { href: "/brand/calendar", label: "Takvim", icon: Calendar },
      { href: "/brand/files", label: "Dosyalar", icon: FolderOpen },
      { href: "/brand/notifications", label: "Bildirimler", icon: Bell },
    ],
  },
  {
    title: "Marka",
    items: [
      { href: "/brand/identity", label: "Marka DNA", icon: Dna },
    ],
  },
  {
    title: "Faturalar",
    items: [
      { href: "/brand/invoices", label: "Faturalar", icon: Receipt },
    ],
  },
  {
    title: "Diğer",
    items: [
      { href: "/brand/reports", label: "Raporlar", icon: BarChart3 },
      { href: "/brand/settings", label: "Ayarlar", icon: Settings2 },
    ],
  },
];

const BOTTOM_NAV_ITEMS: BottomNavItem[] = [
  { href: "/brand/dashboard", label: "Ana Sayfa", icon: LayoutDashboard, exact: true },
  { href: "/brand/briefs", label: "Briefler", icon: FileText },
  { href: "/brand/approvals", label: "Onaylar", icon: CheckCircle },
  { href: "/brand/notifications", label: "Bildirimler", icon: Bell },
];

const ROLE_LABELS: Record<string, string> = {
  brand_owner: "Marka Sahibi",
  brand_manager: "Marka Yöneticisi",
  brand_viewer: "Görüntüleyici",
  external_approver: "Onay Yetkilisi",
};

function toNavDrawerGroups(sections: NavSection[]): NavDrawerGroup[] {
  return sections.map((section) => ({
    label: section.title,
    items: section.items.map((item) => ({
      href: item.href,
      label: item.label,
      icon: item.icon,
      exact: item.exact,
    })),
  }));
}

// ── Brand Sidebar ─────────────────────────────────────────────────────────────

// Route → onboarding view-step key, so organically navigating to a page
// counts the same as completing it via the wizard's own CTA (§4).
const ROUTE_TO_VIEW_STEP: Record<string, string> = {
  "/brand/dashboard": "portal_intro",
  "/brand/briefs": "view_briefs",
  "/brand/calendar": "calendar_invoices",
};

function routeOnboardingStep(pathname: string): string | null {
  const match = Object.keys(ROUTE_TO_VIEW_STEP).find(
    (route) => pathname === route || pathname.startsWith(route + "/")
  );
  return match ? ROUTE_TO_VIEW_STEP[match] : null;
}

interface BrandSidebarProps {
  isManager: boolean;
  membershipRole: string | null;
  notificationSource: NotificationFeedSource | null;
  pathname: string;
  navSections: NavSection[];
}

function BrandSidebar({ isManager, membershipRole, notificationSource, pathname, navSections }: BrandSidebarProps) {
  const { user, logout, accessToken } = useAuth();
  const [seatWarning, setSeatWarning] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !isManager) return;
    brandPortalApi
      .getTeamUsage(accessToken)
      .then((usage) => {
        if (usage.users.limit !== null && usage.users.available !== null && usage.users.available <= 0) {
          setSeatWarning(`Kullanıcı limitine ulaşıldı: ${usage.users.used}/${usage.users.limit}`);
        } else {
          setSeatWarning(null);
        }
      })
      .catch(() => {});
  }, [accessToken, isManager]);

  return (
    <aside
      className="hidden lg:flex lg:flex-col w-56 flex-shrink-0 bg-surface-2 h-screen sticky top-0 overflow-hidden"
      style={{ boxShadow: "var(--shadow-sidebar)" }}
    >
      {/* Top glow */}
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-sidebar pointer-events-none" />

      {/* Logo */}
      <div className="relative flex items-center gap-2.5 px-4 py-4 border-b border-border">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 shadow-glow-sm"
          style={{ background: "var(--gradient-accent)" }}
        >
          <span className="text-white font-bold text-xs tracking-tight">F</span>
        </div>
        <div className="flex-1 min-w-0">
          <span className="font-semibold text-text text-sm tracking-tight block leading-tight">Flobrief</span>
          <span className="text-[10px] text-text-muted leading-tight">Marka Portalı</span>
        </div>
        <NotificationBell source={notificationSource} basePath="/brand/notifications" />
      </div>

      {seatWarning && (
        <div className="relative mx-2.5 mt-2.5 px-2.5 py-2 rounded-lg bg-warning/10 border border-warning/30 text-[11px] text-warning font-medium">
          {seatWarning}
        </div>
      )}

      {/* Navigation */}
      <nav className="relative flex-1 px-2.5 py-3 overflow-y-auto space-y-3">
        {navSections.map((section) => (
          <div key={section.title}>
            <p className="px-2 mb-1.5 text-[10px] font-semibold text-text-muted/60 tracking-widest uppercase">
              {section.title}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = item.exact
                  ? pathname === item.href
                  : pathname === item.href || pathname.startsWith(item.href + "/");
                const IconComp = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    data-onboarding-target={item.href}
                    className={cn(
                      "flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-all duration-150",
                      isActive
                        ? "bg-accent-subtle text-accent font-medium"
                        : "text-text-secondary hover:text-text hover:bg-hover"
                    )}
                  >
                    <IconComp className={cn("w-4 h-4 flex-shrink-0", isActive ? "text-accent" : "")} />
                    <span className="flex-1 truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-2.5 py-3 border-t border-border">
        <div className="flex items-center gap-2 px-2 py-2 rounded-lg">
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center ring-2 ring-accent/30 flex-shrink-0"
            style={{ background: "var(--gradient-accent)" }}
          >
            <span className="text-[10px] font-bold text-white">
              {user ? getInitials(user.full_name) : "?"}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-text truncate leading-tight">{user?.full_name}</p>
            <p className="text-[10px] text-text-muted truncate leading-tight">
              {membershipRole ? ROLE_LABELS[membershipRole] ?? membershipRole : user?.email}
            </p>
          </div>
          <button
            onClick={logout}
            className="p-1.5 rounded-lg text-text-muted hover:text-danger transition-colors flex-shrink-0"
            title="Çıkış yap"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}

// ── Layout ────────────────────────────────────────────────────────────────────

export default function BrandLayout({ children }: { children: ReactNode }) {
  const { user, logout, accessToken, isLoading, isInitialized } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [membershipRole, setMembershipRole] = useState<string | null>(null);

  const isLoginPage = pathname === "/brand/login";
  const isManager = membershipRole ? BRAND_MANAGER_ROLES.has(membershipRole) : false;

  useOnboardingPageSeen({
    stepKey: routeOnboardingStep(pathname),
    variant: "brand",
    accessToken,
  });

  useEffect(() => {
    if (!accessToken) return;
    brandPortalApi.me(accessToken).then((me) => setMembershipRole(me.membership_role)).catch(() => {});
  }, [accessToken]);

  const notificationSource: NotificationFeedSource | null = useMemo(() => {
    if (!accessToken) return null;
    return {
      list: (params) => brandPortalApi.listNotifications(accessToken, params),
      markRead: (id) => brandPortalApi.markNotificationRead(id, accessToken),
      markAllRead: () => brandPortalApi.markAllNotificationsRead(accessToken),
      createRealtimeTicket: () =>
        brandPortalApi.createNotificationRealtimeTicket(accessToken),
    };
  }, [accessToken]);

  const navSections = useMemo(() => {
    if (!isManager) return NAV_SECTIONS;
    const teamItem: NavItem = { href: "/brand/team", label: "Ekip", icon: Users };
    return NAV_SECTIONS.map((section) =>
      section.title === "Marka" ? { ...section, items: [...section.items, teamItem] } : section
    );
  }, [isManager]);

  const navDrawerGroups = useMemo(() => toNavDrawerGroups(navSections), [navSections]);

  useEffect(() => {
    if (!isInitialized || isLoading) return;

    if (isLoginPage) {
      if (user?.user_type === "brand_user") router.replace("/brand/dashboard");
      return;
    }

    if (!user) {
      router.replace("/brand/login");
    } else if (user.user_type === "agency_user") {
      router.replace("/dashboard");
    } else if (user.user_type === "platform_admin") {
      router.replace("/platform");
    }
  }, [isInitialized, isLoading, user, router, isLoginPage]);

  if (isLoginPage) return <>{children}</>;

  if (!isInitialized || isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center"
            style={{ background: "var(--gradient-accent)" }}
          >
            <span className="text-white font-bold text-xs">F</span>
          </div>
          <div className="flex items-center gap-2 text-text-muted">
            <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-70" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-xs">Yükleniyor…</span>
          </div>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <>
      <ResponsiveAppShell
        sidebar={
          <BrandSidebar
            isManager={isManager}
            membershipRole={membershipRole}
            notificationSource={notificationSource}
            pathname={pathname}
            navSections={navSections}
          />
        }
        groups={navDrawerGroups}
        bottomNavItems={BOTTOM_NAV_ITEMS}
        brandTitle="Flobrief"
        brandSubtitle="Marka Portalı"
        fallbackPageTitle="Flobrief"
        user={{ name: user.full_name, email: user.email, initials: getInitials(user.full_name) }}
        profileHref="/brand/settings"
        onLogout={logout}
        notificationSource={notificationSource}
        notificationBasePath="/brand/notifications"
      >
        {children}
      </ResponsiveAppShell>
      <BrandOnboardingWizard />
    </>
  );
}
