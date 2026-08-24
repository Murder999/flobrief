"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import {
  User,
  Bell,
  Shield,
  Palette,
  CreditCard,
  Users,
  Settings,
  HelpCircle,
  LogOut,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SettingsSection {
  href: string;
  label: string;
  description: string;
  icon: React.ElementType;
  iconColor: string;
  roles?: string[];
  permissions?: string[];
}

const AGENCY_SECTIONS: SettingsSection[] = [
  {
    href: "/dashboard/settings/profile",
    label: "Profil & Güvenlik",
    description: "Ad, unvan, şifre, 2FA, tema, WhatsApp",
    icon: User,
    iconColor: "bg-indigo-500/10 text-indigo-500",
  },
  {
    href: "/dashboard/settings/notifications",
    label: "Bildirimler",
    description: "E-posta, uygulama içi, WhatsApp tercihleri",
    icon: Bell,
    iconColor: "bg-amber-500/10 text-amber-500",
  },
  {
    href: "/dashboard/settings/branding",
    label: "White-label & Marka",
    description: "Logo, renkler, özel alan adı",
    icon: Palette,
    iconColor: "bg-purple-500/10 text-purple-500",
  },
  {
    href: "/dashboard/settings/billing",
    label: "Abonelik & Faturalama",
    description: "Plan, kullanım limitleri, faturalar",
    icon: CreditCard,
    iconColor: "bg-emerald-500/10 text-emerald-500",
  },
  {
    href: "/dashboard/settings/members",
    label: "Ekip Üyeleri",
    description: "Üyeleri yönetin, davetler gönderin",
    icon: Users,
    iconColor: "bg-sky-500/10 text-sky-500",
  },
  {
    href: "/dashboard/settings/agency",
    label: "Ajans Bilgileri",
    description: "Ajans adı, logo, slug",
    icon: Settings,
    iconColor: "bg-slate-500/10 text-slate-500",
  },
];

const BRAND_SECTIONS: SettingsSection[] = [
  {
    href: "/brand/settings?tab=profile",
    label: "Profilim",
    description: "Ad, unvan, şifre, WhatsApp",
    icon: User,
    iconColor: "bg-indigo-500/10 text-indigo-500",
  },
  {
    href: "/brand/notifications",
    label: "Bildirimler",
    description: "E-posta, uygulama içi, WhatsApp tercihleri",
    icon: Bell,
    iconColor: "bg-amber-500/10 text-amber-500",
  },
  {
    href: "/brand/settings?tab=brand",
    label: "Marka Profili",
    description: "Marka adı, slug, durum",
    icon: Palette,
    iconColor: "bg-purple-500/10 text-purple-500",
  },
];

interface SettingsLayoutProps {
  children: React.ReactNode;
  portal: "agency" | "brand";
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function SettingsLayout({ children, portal, title, description, action }: SettingsLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const isAgency = portal === "agency";
  const sections = isAgency ? AGENCY_SECTIONS : BRAND_SECTIONS;

  // Determine active section based on current path
  const activeSection = useMemo(() => {
    return sections.find((s) => {
      if (isAgency) {
        return pathname.startsWith(s.href);
      } else {
        // Brand portal uses query params for tabs
        if (s.href.includes("?tab=")) {
          const [path, query] = s.href.split("?");
          return pathname.startsWith(path) && new URLSearchParams(query).get("tab") === new URLSearchParams(window.location.search).get("tab");
        }
        return pathname.startsWith(s.href);
      }
    });
  }, [pathname, sections, isAgency]);

  // Mobile section navigation - use router.push instead of window.location
  useEffect(() => {
    const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      if (value && value.startsWith("/")) {
        router.push(value);
      }
    };
    return () => {
      // cleanup
    };
  }, [router]);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 lg:py-12">
      {/* Header */}
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
        {/* Sidebar Navigation */}
        <aside className="hidden lg:block mb-8 lg:mb-0">
          <nav className="bg-surface border border-border rounded-2xl p-3" aria-label="Ayarlar menüsü">
            <ul className="space-y-1" role="list">
              {sections.map((section) => {
                const isActive = activeSection?.href === section.href;
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
            
            {/* Quick actions section */}
            <div className="mt-6 pt-6 border-t border-border space-y-1">
              <p className="px-3 text-xs font-semibold text-text-muted uppercase tracking-wider">Hızlı İşlemler</p>
              {isAgency && (
                <Link
                  href="/dashboard/settings/billing?upgrade=true"
                  className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-text-muted hover:bg-surface-2 hover:text-text transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center flex-shrink-0">
                    <CreditCard className="w-4.5 h-4.5" aria-hidden="true" />
                  </div>
                  <div className="flex-1 truncate">Plan Yükselt</div>
                  <ChevronRight className="w-4 h-4 text-text-muted" aria-hidden="true" />
                </Link>
              )}
              <Link
                href={isAgency ? "/dashboard/settings/profile" : "/brand/settings?tab=profile"}
                className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-text-muted hover:bg-surface-2 hover:text-text transition-colors"
              >
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-500 flex items-center justify-center flex-shrink-0">
                  <User className="w-4.5 h-4.5" aria-hidden="true" />
                </div>
                <div className="flex-1 truncate">Profilim</div>
                <ChevronRight className="w-4 h-4 text-text-muted" aria-hidden="true" />
              </Link>
              <a
                href={isAgency ? "/dashboard/settings/notifications" : "/brand/notifications"}
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

        {/* Main Content */}
        <main className="lg:min-w-0">
          {children}
        </main>
      </div>
    </div>
  );
}