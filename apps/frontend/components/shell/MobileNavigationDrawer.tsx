"use client";

import { AnimatePresence, motion } from "framer-motion";
import { LogOut, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { SafeAreaContainer } from "@/components/ui/safe-area-container";
import type { NavDrawerGroup } from "./types";
import { useLocale } from "@/context/locale-context";
import { LanguageSelector } from "@/components/i18n/language-selector";

interface MobileNavigationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  groups: NavDrawerGroup[];
  brandTitle: string;
  brandSubtitle?: string;
  topContent?: ReactNode;
  user: { name: string; email: string; initials: string } | null;
  profileHref: string;
  onLogout: () => void;
}

function isActive(pathname: string, href: string, exact?: boolean): boolean {
  return exact ? pathname === href : pathname === href || pathname.startsWith(href + "/");
}

/**
 * Premium slide-in-from-left nav drawer shared by the agency and brand
 * shells. Focus trap + body scroll lock (shared hooks), Escape/overlay
 * close, closes automatically on route change, and supports the browser
 * back button via a one-entry history guard: opening pushes a synthetic
 * history state that a `popstate` closes the drawer; any other close path
 * pops that same entry in cleanup so the stack stays clean — except a
 * nav-link click, which skips that pop so it doesn't fight Next's own
 * navigation entry (the one accepted trade-off: a link click followed by a
 * *second*, separate back-press can land one extra step back).
 */
export function MobileNavigationDrawer({
  isOpen,
  onClose,
  groups,
  brandTitle,
  brandSubtitle,
  topContent,
  user,
  profileHref,
  onLogout,
}: MobileNavigationDrawerProps) {
  const { t } = useLocale();
  const pathname = usePathname();
  const panelRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const pushedRef = useRef(false);
  const skipHistoryCleanupRef = useRef(false);

  useEffect(() => setMounted(true), []);
  useBodyScrollLock(isOpen);
  useFocusTrap(panelRef, isOpen);

  // Auto-close whenever the route changes while open.
  const prevPathnameRef = useRef(pathname);
  useEffect(() => {
    if (prevPathnameRef.current !== pathname) {
      prevPathnameRef.current = pathname;
      if (isOpen) onClose();
    }
  }, [pathname, isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Browser-back history guard (see doc comment above).
  useEffect(() => {
    if (!isOpen) return;
    window.history.pushState({ flobriefDrawerOpen: true }, "");
    pushedRef.current = true;

    const onPopState = () => {
      pushedRef.current = false;
      onClose();
    };
    window.addEventListener("popstate", onPopState);

    return () => {
      window.removeEventListener("popstate", onPopState);
      if (pushedRef.current && !skipHistoryCleanupRef.current) {
        window.history.back();
      }
      pushedRef.current = false;
      skipHistoryCleanupRef.current = false;
    };
  }, [isOpen, onClose]);

  const handleChromeClose = () => onClose();
  const handleNavigate = () => {
    skipHistoryCleanupRef.current = true;
    onClose();
  };

  if (!mounted) return null;

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex">
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={handleChromeClose}
          />
          <motion.div
            id="mobile-nav-drawer"
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={`${brandTitle} ${t("dashboard.navigation.more")}`}
            tabIndex={-1}
            className="relative h-full w-[85vw] max-w-[320px] bg-surface border-r border-border shadow-modal flex flex-col overflow-hidden outline-none"
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            <SafeAreaContainer top left minTop="0px" minLeft="0px" className="flex flex-col h-full min-h-0">
              {/* Logo row */}
              <div className="flex items-center gap-2.5 px-4 py-4 flex-shrink-0 border-b border-border">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "var(--gradient-accent)", boxShadow: "0 2px 8px rgba(99,102,241,0.30)" }}
                >
                  <span className="text-white font-bold text-xs tracking-tight leading-none">F</span>
                </div>
                <div className="flex-1 min-w-0">
                  <span className="font-semibold text-text text-sm tracking-tight block leading-tight">
                    {brandTitle}
                  </span>
                  {brandSubtitle && (
                    <span className="text-[10px] text-text-muted leading-tight">{brandSubtitle}</span>
                  )}
                </div>
                <button
                  onClick={handleChromeClose}
                  className="w-11 h-11 -mr-2.5 flex items-center justify-center rounded-lg text-text-muted hover:text-text hover:bg-hover transition-colors flex-shrink-0"
                  aria-label={t("dashboard.shell.closeMenu")}
                >
                  <X className="w-4.5 h-4.5" />
                </button>
              </div>

              {topContent ? <div className="shrink-0 border-b border-border">{topContent}</div> : null}

              {/* Nav groups */}
              <nav className="flex-1 min-h-0 overflow-y-auto px-2.5 py-3">
                {groups.map((group, gi) => (
                  <div key={group.label ?? gi} className={gi > 0 ? "mt-4" : ""}>
                    {group.label && (
                      <p className="px-2.5 mb-1 text-label-xs text-text-muted/55 tracking-widest">
                        {group.label}
                      </p>
                    )}
                    <div className="space-y-0.5">
                      {group.items.map((item) => {
                        const active = isActive(pathname, item.href, item.exact);
                        const IconComp = item.icon;
                        const showCount = typeof item.badge === "number" && item.badge > 0;
                        const showDot = item.badge === true;
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            data-onboarding-target={item.href}
                            onClick={handleNavigate}
                            aria-current={active ? "page" : undefined}
                            className={cn(
                              "flex items-center gap-3 min-h-[44px] px-2.5 py-2 rounded-lg text-[13px] transition-all duration-150",
                              active
                                ? "bg-accent-subtle text-accent font-medium"
                                : "text-text-secondary hover:text-text hover:bg-hover"
                            )}
                          >
                            <IconComp className={cn("w-4.5 h-4.5 flex-shrink-0", active ? "text-accent" : "")} />
                            <span className="flex-1 truncate">{item.label}</span>
                            {showCount && (
                              <span className="min-w-[18px] h-[18px] bg-accent-subtle text-accent text-[9px] font-bold rounded-full flex items-center justify-center px-1 flex-shrink-0">
                                {(item.badge as number) > 9 ? "9+" : item.badge}
                              </span>
                            )}
                            {showDot && (
                              <span className="w-2 h-2 rounded-full bg-accent flex-shrink-0" aria-label={t("dashboard.shell.new")} />
                            )}
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </nav>

              {/* Profile + logout footer */}
              {user && (
                <div className="flex-shrink-0 border-t border-border px-2.5 py-3">
                  <div className="mb-2 flex justify-center"><LanguageSelector /></div>
                  <div className="flex items-center gap-2 px-2 py-1.5 rounded-xl">
                    <Link
                      href={profileHref}
                      onClick={handleNavigate}
                      className="flex items-center gap-2 flex-1 min-w-0"
                    >
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center ring-2 ring-accent/25 flex-shrink-0"
                        style={{ background: "var(--gradient-accent)" }}
                      >
                        <span className="text-[11px] font-bold text-white">{user.initials}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-text truncate leading-tight">{user.name}</p>
                        <p className="text-[10px] text-text-muted truncate leading-tight">{user.email}</p>
                      </div>
                    </Link>
                    <div className="flex items-center gap-0.5 flex-shrink-0">
                      <ThemeToggle menuPosition="up" />
                      <button
                        onClick={() => {
                          skipHistoryCleanupRef.current = true;
                          onLogout();
                        }}
                        className="w-11 h-11 flex items-center justify-center rounded-lg text-text-muted hover:text-danger transition-colors"
                        aria-label={t("auth.actions.logout")}
                      >
                        <LogOut className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </SafeAreaContainer>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}
