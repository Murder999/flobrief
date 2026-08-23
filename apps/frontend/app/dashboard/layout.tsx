"use client";

import { useAuth } from "@/hooks/useAuth";
import { getInitials } from "@/lib/auth";
import { notificationApi, invitationApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState, useCallback, useMemo, type ReactNode } from "react";
import { CommandPalette } from "@/components/search/command-palette";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import type { NotificationFeedSource } from "@/components/notifications/useNotificationFeed";
import { GlobalTimerWidget } from "@/components/time-tracking/GlobalTimerWidget";
import { WorkspaceSwitcher } from "@/components/workspace/workspace-switcher";
import { DemoPortalSwitcher } from "@/components/workspace/demo-portal-switcher";
import { useWorkspace } from "@/context/workspace-context";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { AgencyOnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useOnboardingPageSeen } from "@/hooks/useOnboardingPageSeen";
import { ResponsiveAppShell } from "@/components/shell/ResponsiveAppShell";
import type { BottomNavItem, NavDrawerGroup, NavIcon } from "@/components/shell/types";
import { useLocale } from "@/context/locale-context";
import { translateAppNavigationLabel } from "@/lib/i18n/app-navigation";
import { LanguageSelector } from "@/components/i18n/language-selector";
import {
  LayoutDashboard, FileText, Calendar, Layers, Building2, BarChart3,
  Zap, Users, Mail, CreditCard, User, Bell, Settings2, LogOut,
  Gauge, Clock, Wallet, Hourglass, Receipt, Repeat, Plug,
  TrendingUp, Info,
} from "lucide-react";

// ── Nav config ────────────────────────────────────────────────────────────────

interface NavItem {
  href: string;
  label: string;
  icon: NavIcon;
  exact?: boolean;
  badge?: boolean;
  ownerOnly?: boolean;
}

interface NavGroup {
  label: string | null;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: null,
    items: [
      { href: "/dashboard", label: "Genel Bakış", icon: LayoutDashboard, exact: true },
    ],
  },
  {
    label: "İş Akışı",
    items: [
      { href: "/dashboard/briefs",    label: "Brief'ler",  icon: FileText },
      { href: "/dashboard/calendar",  label: "Takvim",    icon: Calendar },
      { href: "/dashboard/templates", label: "Şablonlar", icon: Layers },
      { href: "/dashboard/time",      label: "Zaman Takibi", icon: Clock },
    ],
  },
  {
    label: "Markalar & Raporlar",
    items: [
      { href: "/dashboard/brands",   label: "Markalar",  icon: Building2 },
      { href: "/dashboard/reports",  label: "Raporlar",  icon: BarChart3 },
      { href: "/dashboard/activity", label: "Aktivite",  icon: Zap },
    ],
  },
  {
    label: "Ekip",
    items: [
      { href: "/dashboard/settings/members", label: "Ekip Üyeleri", icon: Users },
      { href: "/dashboard/capacity",         label: "Kapasite",     icon: Gauge },
      { href: "/dashboard/invitations",      label: "Davetlerim",   icon: Mail, badge: true },
    ],
  },
  {
    label: "Finans",
    items: [
      // Phase 4 adds billable time + invoice lifecycle + retainers.
      // "Faturalandırılabilir Zaman" is deliberately not ownerOnly — any
      // BILLING_TIME_VIEW holder (Owner/Admin/Brand Manager per plan §8)
      // can reach it; the backend is the real gate for anyone else who
      // guesses the URL. Faturalar/Retainer'lar stay ownerOnly per the
      // plan's explicit nav spec (Admin's INVOICE_VIEW is still reachable
      // by direct URL, backend-enforced). Kârlılık/Muhasebe land later.
      { href: "/dashboard/finance/billable-time", label: "Faturalandırılabilir Zaman", icon: Hourglass },
      { href: "/dashboard/finance/invoices", label: "Faturalar", icon: Receipt, ownerOnly: true },
      { href: "/dashboard/finance/retainers", label: "Retainer'lar", icon: Repeat, ownerOnly: true },
      { href: "/dashboard/finance/settings", label: "Finans Ayarları", icon: Wallet, ownerOnly: true },
      // Phase 5: ACCOUNTING_INTEGRATION_MANAGE is Owner-only per plan §8
      // (not even Admin) — ownerOnly here matches that exactly.
      { href: "/dashboard/finance/accounting", label: "Muhasebe Entegrasyonu", icon: Plug, ownerOnly: true },
      // Phase 6: PROFITABILITY_VIEW is granted to Owner/Admin/Brand Manager
      // server-side (plan §8) — ownerOnly here is the same UX
      // simplification already applied to Faturalar/Retainer'lar above; a
      // direct URL visit from Admin/Brand Manager still works, backend-enforced.
      { href: "/dashboard/finance/profitability", label: "Kârlılık", icon: TrendingUp, ownerOnly: true },
    ],
  },
  {
    label: "Hesap",
    items: [
      { href: "/dashboard/settings/billing",       label: "Faturalama",      icon: CreditCard, ownerOnly: true },
      { href: "/dashboard/settings/profile",       label: "Profilim",        icon: User },
      { href: "/dashboard/settings/notifications", label: "Bildirimler",     icon: Bell },
      { href: "/dashboard/settings/agency",        label: "Ajans Ayarları",  icon: Settings2 },
    ],
  },
  {
    label: "Yardım",
    items: [
      { href: "/dashboard/help", label: "Yardım Merkezi", icon: Info },
    ],
  },
];

const BOTTOM_NAV_ITEMS: BottomNavItem[] = [
  { href: "/dashboard", label: "Ana Sayfa", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/briefs", label: "Briefler", icon: FileText },
  { href: "/dashboard/calendar", label: "Takvim", icon: Calendar },
  { href: "/dashboard/notifications", label: "Bildirimler", icon: Bell },
];

function toNavDrawerGroups(groups: NavGroup[], isOwner: boolean, pendingInviteCount: number, t: ReturnType<typeof useLocale>["t"]): NavDrawerGroup[] {
  return groups
    .map((group) => ({
      label: translateAppNavigationLabel(t, group.label),
      items: group.items
        .filter((item) => !item.ownerOnly || isOwner)
        .map((item) => ({
          href: item.href,
          label: translateAppNavigationLabel(t, item.label) ?? item.label,
          icon: item.icon,
          exact: item.exact,
          badge: item.badge ? pendingInviteCount : undefined,
        })),
    }))
    .filter((group) => group.items.length > 0);
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

// Route → onboarding view-step key, so organically navigating to a page
// counts the same as completing it via the wizard's own CTA (§4). Owner and
// member onboarding types use different step keys for the same page.
const ROUTE_TO_VIEW_STEP: Record<string, { owner?: string; member?: string }> = {
  "/dashboard/briefs": { owner: "preview_center", member: "assigned_briefs" },
  "/dashboard/brands": { owner: "brand_portal_preview" },
  "/dashboard/time": { owner: "time_tracking", member: "timesheet" },
  "/dashboard/capacity": { owner: "capacity" },
  "/dashboard/settings/notifications": { owner: "notification_preferences", member: "notifications" },
};

function useRouteOnboardingStep(pathname: string, isOwner: boolean): string | null {
  const match = Object.keys(ROUTE_TO_VIEW_STEP).find(
    (route) => pathname === route || pathname.startsWith(route + "/")
  );
  if (!match) return null;
  const entry = ROUTE_TO_VIEW_STEP[match];
  return (isOwner ? entry.owner : entry.member) ?? null;
}

interface SidebarProps {
  isOwner: boolean;
  pendingInviteCount: number;
  notificationSource: NotificationFeedSource | null;
  pathname: string;
}

function Sidebar({ isOwner, pendingInviteCount, notificationSource, pathname }: SidebarProps) {
  const { user, logout } = useAuth();
  const { t } = useLocale();

  return (
    <aside
      className="hidden lg:flex lg:flex-col w-56 flex-shrink-0 h-screen sticky top-0 overflow-hidden bg-surface-2"
      style={{ boxShadow: "var(--shadow-sidebar)" }}
    >
      {/* Subtle gradient top accent */}
      <div className="absolute inset-x-0 top-0 h-40 bg-gradient-sidebar pointer-events-none" />
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-accent opacity-20 pointer-events-none" />

      {/* Logo row */}
      <div className="relative flex items-center gap-2.5 px-4 py-4 flex-shrink-0">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{
            background: "var(--gradient-accent)",
            boxShadow: "0 2px 8px rgba(99,102,241,0.30)",
          }}
        >
          <span className="text-white font-bold text-xs tracking-tight leading-none">F</span>
        </div>
        <span className="font-semibold text-text text-sm flex-1 tracking-tight">Flobrief</span>
        <GlobalTimerWidget />
        <NotificationBell source={notificationSource} basePath="/dashboard/notifications" />
      </div>

      {/* Workspace switcher */}
      <div className="relative px-2.5 pb-2.5 flex-shrink-0">
        <div className="border-b border-border pb-2.5">
          <WorkspaceSwitcher />
        </div>
      </div>

      {/* Navigation */}
      <nav className="relative flex-1 px-2.5 py-2 overflow-y-auto">
        {NAV_GROUPS.map((group, gi) => {
          const visibleItems = group.items.filter((item) => !item.ownerOnly || isOwner);
          if (visibleItems.length === 0) return null;

          return (
            <div key={gi} className={gi > 0 ? "mt-4" : ""}>
              {group.label && (
                <p className="px-2.5 mb-1 text-label-xs text-text-muted/55 tracking-widest">
                  {translateAppNavigationLabel(t, group.label)}
                </p>
              )}
              <div className="space-y-0.5">
                {visibleItems.map((item) => {
                  const isActive = item.exact
                    ? pathname === item.href
                    : pathname === item.href || pathname.startsWith(item.href + "/");
                  const showBadge = item.badge && pendingInviteCount > 0;
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
                      <IconComp
                        className={cn(
                          "w-4 h-4 flex-shrink-0 transition-colors",
                          isActive ? "text-accent" : ""
                        )}
                      />
                      <span className="flex-1 truncate">{translateAppNavigationLabel(t, item.label)}</span>
                      {showBadge && (
                        <span className="min-w-[18px] h-[18px] bg-accent-subtle text-accent text-[9px] font-bold rounded-full flex items-center justify-center px-1 flex-shrink-0">
                          {pendingInviteCount > 9 ? "9+" : pendingInviteCount}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Footer — user + controls */}
      <div
        className="relative px-2.5 py-3 flex-shrink-0 border-t border-border"
      >
        {/* Demo Portal Switcher */}
        <div className="mb-2.5">
          <DemoPortalSwitcher />
        </div>

        <div className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-hover transition-all">
          <Link href="/dashboard/settings/profile" className="flex-shrink-0" title="Profil">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center ring-2 ring-accent/25"
              style={{ background: "var(--gradient-accent)" }}
            >
              <span className="text-[10px] font-bold text-white">
                {user ? getInitials(user.full_name) : "?"}
              </span>
            </div>
          </Link>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-text truncate leading-tight">
              {user?.full_name}
            </p>
            <p className="text-[10px] text-text-muted truncate leading-tight">{user?.email}</p>
          </div>
          <div className="flex items-center gap-0.5 flex-shrink-0">
            <LanguageSelector compact />
            <ThemeToggle menuPosition="up" />
            <button
              onClick={logout}
              className="p-1.5 rounded-lg text-text-muted hover:text-danger transition-colors"
              title="Çıkış yap"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

// ── Layout ────────────────────────────────────────────────────────────────────

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { t } = useLocale();
  const { user, logout, accessToken, isLoading, isInitialized } = useAuth();
  const { activeAgency } = useWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [pendingInviteCount, setPendingInviteCount] = useState(0);

  const currentAgencyId = activeAgency?.id ?? null;
  const isOwner = activeAgency?.member_role === "owner";

  useOnboardingPageSeen({
    stepKey: useRouteOnboardingStep(pathname, isOwner),
    variant: "agency",
    agencyId: currentAgencyId,
    accessToken,
  });

  const notificationSource: NotificationFeedSource | null = useMemo(() => {
    if (!accessToken || !currentAgencyId) return null;
    return {
      list: (params) => notificationApi.list(currentAgencyId, accessToken, params),
      markRead: (id) => notificationApi.markRead(id, currentAgencyId, accessToken),
      markAllRead: () => notificationApi.markAllRead(currentAgencyId, accessToken),
      createRealtimeTicket: () =>
        notificationApi.createRealtimeTicket(currentAgencyId, accessToken),
    };
  }, [accessToken, currentAgencyId]);

  const fetchPendingInvites = useCallback(async () => {
    if (!accessToken) return;
    try {
      const invites = await invitationApi.getMyPending(accessToken);
      setPendingInviteCount(invites.length);
    } catch { /* silent */ }
  }, [accessToken]);

  useEffect(() => {
    fetchPendingInvites();
    const interval = setInterval(fetchPendingInvites, 120_000);
    return () => clearInterval(interval);
  }, [fetchPendingInvites]);

  const navDrawerGroups = useMemo(
    () => toNavDrawerGroups(NAV_GROUPS, isOwner, pendingInviteCount, t),
    [isOwner, pendingInviteCount, t]
  );

  const localizedBottomNavItems = useMemo(
    () => BOTTOM_NAV_ITEMS.map((item) => ({ ...item, label: translateAppNavigationLabel(t, item.label) ?? item.label })),
    [t]
  );

  useEffect(() => {
    if (!isInitialized || isLoading) return;
    if (!user) {
      router.replace("/auth/login");
    } else if (user.user_type === "brand_user") {
      router.replace("/brand/dashboard");
    }
  }, [isInitialized, isLoading, user, router]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  if (!isInitialized || isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: "var(--gradient-accent)" }}
          >
            <span className="text-white font-bold text-sm">F</span>
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
          <Sidebar
            isOwner={isOwner}
            pendingInviteCount={pendingInviteCount}
            notificationSource={notificationSource}
            pathname={pathname}
          />
        }
        groups={navDrawerGroups}
        bottomNavItems={localizedBottomNavItems}
        brandTitle="Flobrief"
        fallbackPageTitle="Flobrief"
        user={{ name: user.full_name, email: user.email, initials: getInitials(user.full_name) }}
        profileHref="/dashboard/settings/profile"
        onLogout={logout}
        notificationSource={notificationSource}
        notificationBasePath="/dashboard/notifications"
        showTimer
      >
        {children}
      </ResponsiveAppShell>
      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
      <AgencyOnboardingWizard />
    </>
  );
}
