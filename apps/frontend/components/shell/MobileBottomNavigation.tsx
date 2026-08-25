"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { SafeAreaContainer } from "@/components/ui/safe-area-container";
import type { BottomNavItem } from "./types";
import { useLocale } from "@/context/locale-context";

interface MobileBottomNavigationProps {
  items: BottomNavItem[];
  onMoreClick: () => void;
  moreActive: boolean;
}

function isActive(pathname: string, href: string, exact?: boolean): boolean {
  return exact ? pathname === href : pathname === href || pathname.startsWith(href + "/");
}

/**
 * Fixed bottom tab bar, mobile/tablet only (`lg:hidden`). Caps at the 4
 * routes the caller passes plus a fixed "Daha Fazla" tab that opens the
 * same MobileNavigationDrawer instead of duplicating its list.
 */
export function MobileBottomNavigation({ items, onMoreClick, moreActive }: MobileBottomNavigationProps) {
  const { t } = useLocale();
  const pathname = usePathname();

  return (
    <SafeAreaContainer
      bottom
      minBottom="0px"
      className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-surface/95 backdrop-blur-md border-t border-border"
    >
      <nav
        data-testid="mobile-bottom-navigation"
        className="flex h-14 items-stretch"
        aria-label={t("dashboard.shell.bottomNavigation")}
      >
        {items.map((item) => {
          const active = isActive(pathname, item.href, item.exact);
          const IconComp = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex-1 flex flex-col items-center justify-center gap-0.5 min-w-[44px] transition-colors",
                active ? "text-accent" : "text-text-muted hover:text-text"
              )}
            >
              <span className="relative">
                <IconComp className="w-5 h-5" />
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute -top-1 -right-1.5 min-w-[14px] h-3.5 bg-accent text-white text-[9px] font-bold rounded-full flex items-center justify-center px-0.5">
                    {item.badge > 9 ? "9+" : item.badge}
                  </span>
                )}
              </span>
              <span className="text-[10px] font-medium leading-none">{item.label}</span>
              {active && <span className="absolute top-0 inset-x-1/4 h-0.5 rounded-full bg-accent" />}
            </Link>
          );
        })}
        <button
          type="button"
          onClick={onMoreClick}
          aria-haspopup="true"
          aria-expanded={moreActive}
          className={cn(
            "relative flex-1 flex flex-col items-center justify-center gap-0.5 min-w-[44px] transition-colors",
            moreActive ? "text-accent" : "text-text-muted hover:text-text"
          )}
        >
          <Menu className="w-5 h-5" />
          <span className="text-[10px] font-medium leading-none">{t("dashboard.navigation.more")}</span>
          {moreActive && <span className="absolute top-0 inset-x-1/4 h-0.5 rounded-full bg-accent" />}
        </button>
      </nav>
    </SafeAreaContainer>
  );
}
