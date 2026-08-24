"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  Building2,
  ChevronRight,
  CreditCard,
  Palette,
  User,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useLocale } from "@/context/locale-context";
import { useWorkspace } from "@/context/workspace-context";
import { cn } from "@/lib/utils";
import type { TranslationKey } from "@/messages";

interface AgencySettingsSection {
  href: string;
  labelKey: TranslationKey;
  icon: LucideIcon;
  ownerOnly?: boolean;
}

interface AgencySettingsGroup {
  labelKey: TranslationKey;
  sections: AgencySettingsSection[];
}

const AGENCY_SECTION_GROUPS: AgencySettingsGroup[] = [
  {
    labelKey: "settings.nav.group.personal",
    sections: [
      {
        href: "/dashboard/settings/profile",
        labelKey: "settings.nav.profileSecurity",
        icon: User,
      },
      {
        href: "/dashboard/settings/notifications",
        labelKey: "settings.nav.notifications",
        icon: Bell,
      },
    ],
  },
  {
    labelKey: "settings.nav.group.agency",
    sections: [
      {
        href: "/dashboard/settings/agency",
        labelKey: "settings.nav.agencyDetails",
        icon: Building2,
      },
      {
        href: "/dashboard/settings/branding",
        labelKey: "settings.nav.branding",
        icon: Palette,
        ownerOnly: true,
      },
      {
        href: "/dashboard/settings/members",
        labelKey: "settings.nav.members",
        icon: Users,
      },
    ],
  },
  {
    labelKey: "settings.nav.group.subscription",
    sections: [
      {
        href: "/dashboard/settings/billing",
        labelKey: "settings.nav.billing",
        icon: CreditCard,
        ownerOnly: true,
      },
    ],
  },
];

const BRAND_SECTIONS = [
  {
    href: "/brand/settings?tab=profile",
    label: "Profilim",
    icon: User,
    iconColor: "bg-indigo-500/10 text-indigo-500",
  },
  {
    href: "/brand/notifications",
    label: "Bildirimler",
    icon: Bell,
    iconColor: "bg-amber-500/10 text-amber-500",
  },
  {
    href: "/brand/settings?tab=brand",
    label: "Marka Profili",
    icon: Palette,
    iconColor: "bg-purple-500/10 text-purple-500",
  },
];

interface SettingsLayoutProps {
  children: React.ReactNode;
  portal: "agency" | "brand";
  title?: string;
  description?: string;
  action?: React.ReactNode;
}

function isActivePath(pathname: string, href: string): boolean {
  const route = href.split("?")[0];
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function SettingsLayout({
  children,
  portal,
  title,
  description,
  action,
}: SettingsLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useLocale();
  const { activeAgency } = useWorkspace();

  if (portal === "agency") {
    const visibleGroups = AGENCY_SECTION_GROUPS.map((group) => ({
      ...group,
      sections: group.sections.filter(
        (section) => !section.ownerOnly || activeAgency?.member_role === "owner"
      ),
    })).filter((group) => group.sections.length > 0);
    const visibleSections = visibleGroups.flatMap((group) => group.sections);
    const activeSection = visibleSections.find((section) =>
      isActivePath(pathname, section.href)
    );

    return (
      <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
        <header className="mb-6 lg:mb-8">
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
            {t("settings.title")}
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-text lg:text-3xl">
            {activeSection ? t(activeSection.labelKey) : t("settings.title")}
          </h1>
        </header>

        <div className="mb-6 lg:hidden">
          <label htmlFor="settings-section" className="sr-only">
            {t("settings.nav.mobileLabel")}
          </label>
          <select
            id="settings-section"
            value={activeSection?.href ?? ""}
            onChange={(event) => router.push(event.target.value)}
            className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm font-medium text-text outline-none transition-colors focus:border-accent focus:ring-2 focus:ring-accent/20"
          >
            {!activeSection && (
              <option value="" disabled>
                {t("settings.nav.mobileLabel")}
              </option>
            )}
            {visibleGroups.map((group) => (
              <optgroup key={group.labelKey} label={t(group.labelKey)}>
                {group.sections.map((section) => (
                  <option key={section.href} value={section.href}>
                    {t(section.labelKey)}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div className="lg:grid lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-8">
          <aside className="hidden lg:block">
            <nav
              className="sticky top-6 px-1"
              aria-label={t("settings.nav.label")}
            >
              {visibleGroups.map((group, groupIndex) => (
                <div
                  key={group.labelKey}
                  className={cn(groupIndex > 0 && "mt-5")}
                >
                  <p className="px-2 pb-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
                    {t(group.labelKey)}
                  </p>
                  <ul className="space-y-1" role="list">
                    {group.sections.map((section) => {
                      const isActive = activeSection?.href === section.href;
                      const Icon = section.icon;

                      return (
                        <li key={section.href}>
                          <Link
                            href={section.href}
                            className={cn(
                              "flex min-h-9 items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors",
                              isActive
                                ? "bg-surface-2 text-text"
                                : "text-text-muted hover:text-text"
                            )}
                            aria-current={isActive ? "page" : undefined}
                          >
                            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                            <span>{t(section.labelKey)}</span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </nav>
          </aside>

          <main className="min-w-0">{children}</main>
        </div>
      </div>
    );
  }

  const activeBrandSection = BRAND_SECTIONS.find((section) => {
    if (!isActivePath(pathname, section.href)) return false;
    const query = section.href.split("?")[1];
    if (!query) return true;
    const currentQuery = typeof window === "undefined" ? "" : window.location.search;
    return new URLSearchParams(query).get("tab") === new URLSearchParams(currentQuery).get("tab");
  });

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 lg:py-12">
      <div className="mb-8">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl lg:text-3xl font-bold text-text">{title}</h1>
            {description && (
              <p className="mt-1 text-sm text-text-muted">{description}</p>
            )}
          </div>
          {action && <div className="flex-shrink-0">{action}</div>}
        </div>
      </div>

      <div className="lg:grid lg:grid-cols-[260px_1fr] lg:gap-8">
        <aside className="hidden lg:block mb-8 lg:mb-0">
          <nav className="bg-surface border border-border rounded-2xl p-3" aria-label="Ayarlar menüsü">
            <ul className="space-y-1" role="list">
              {BRAND_SECTIONS.map((section) => {
                const isActive = activeBrandSection?.href === section.href;
                const Icon = section.icon;
                return (
                  <li key={section.href}>
                    <Link
                      href={section.href}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all",
                        isActive ? "bg-accent/10 text-accent shadow-sm" : "text-text-muted hover:bg-surface-2 hover:text-text"
                      )}
                      aria-current={isActive ? "page" : undefined}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${section.iconColor}`}>
                        <Icon className="w-4.5 h-4.5" aria-hidden="true" />
                      </div>
                      <div className="flex-1 min-w-0 truncate">{section.label}</div>
                      {isActive && (
                        <ChevronRight className="w-4 h-4 text-accent flex-shrink-0" aria-hidden="true" />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>

            <div className="mt-6 pt-6 border-t border-border space-y-1">
              <p className="px-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Hızlı İşlemler</p>
              <Link
                href="/brand/settings?tab=profile"
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-text-muted hover:bg-surface-2 hover:text-text transition-colors"
              >
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-500 flex items-center justify-center flex-shrink-0">
                  <User className="w-4.5 h-4.5" aria-hidden="true" />
                </div>
                <div className="flex-1 truncate">Profilim</div>
                <ChevronRight className="w-4 h-4 text-text-muted" aria-hidden="true" />
              </Link>
              <a
                href="/brand/notifications"
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-text-muted hover:bg-surface-2 hover:text-text transition-colors"
              >
                <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-500 flex items-center justify-center flex-shrink-0">
                  <Bell className="w-4.5 h-4.5" aria-hidden="true" />
                </div>
                <div className="flex-1 truncate">Bildirimler</div>
                <ChevronRight className="w-4 h-4 text-text-muted" aria-hidden="true" />
              </a>
            </div>
          </nav>
        </aside>

        <main className="lg:min-w-0">{children}</main>
      </div>
    </div>
  );
}
