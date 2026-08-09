"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { impersonationState, platformAuthStorage, refreshPlatformSession } from "@/lib/platform-auth";
import { ApiError, platformApi, platformAuthApi } from "@/lib/api-client";
import { ImpersonationBanner } from "@/components/platform/impersonation-banner";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import {
  LayoutDashboard,
  Building2,
  Users,
  CreditCard,
  Globe,
  Bell,
  Activity,
  Shield,
  LogOut,
  ShieldCheck,
  Search,
  Layers,
  KeyRound,
  FlaskConical,
} from "lucide-react";

const NAV_GROUPS = [
  {
    label: "GENEL",
    items: [
      { href: "/platform/dashboard", label: "Genel Bakış", icon: LayoutDashboard },
    ],
  },
  {
    label: "KİRACILAR",
    items: [
      { href: "/platform/agencies",      label: "Ajanslar",           icon: Building2 },
      { href: "/platform/users",          label: "Kullanıcılar",       icon: Users },
      { href: "/platform/subscriptions",  label: "Abonelikler",        icon: CreditCard },
      { href: "/platform/plans",          label: "Paketler",           icon: Layers },
    ],
  },
  {
    label: "PLATFORM",
    items: [
      { href: "/platform/whitealabel",   label: "White-label",        icon: Layers },
      { href: "/platform/seo",           label: "SEO & Büyüme",       icon: Globe },
      { href: "/platform/notifications", label: "Bildirim Kanalları", icon: Bell },
      { href: "/platform/demo",          label: "Demo Sandbox",      icon: FlaskConical },
      { href: "/platform/system",        label: "Sistem Sağlığı",     icon: Activity },
    ],
  },
  {
    label: "GÜVENLİK",
    items: [
      { href: "/platform/profile", label: "Profil & Şifre", icon: KeyRound },
      { href: "/platform/audit-log", label: "Denetim Günlüğü", icon: Shield },
    ],
  },
];

function Spinner() {
  return (
    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

export default function PlatformLayout({ children }: { children: ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  const isAuthPage = pathname === "/platform/login" || pathname === "/platform/mfa";

  useEffect(() => {
    if (isAuthPage) { setReady(true); return; }

    const REFRESH_INTERVAL = 4 * 60 * 1000;
    let cancelled = false;

    const redirectToLogin = () => {
      platformAuthStorage.clearAll();
      router.replace("/platform/login");
    };

    const initializeSession = async () => {
      let token = platformAuthStorage.getToken();

      if (!token) {
        // No in-memory token — either a hard reload or first visit this tab.
        // Try to bootstrap the session from the HttpOnly refresh cookie
        // before giving up.
        const refreshed = await refreshPlatformSession();
        if (!refreshed) {
          if (!cancelled) redirectToLogin();
          return;
        }
        token = platformAuthStorage.getToken();
      }

      try {
        await platformApi.health(token as string);
        if (!cancelled) setReady(true);
      } catch (error) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          const refreshed = await refreshPlatformSession();
          if (refreshed && !cancelled) {
            setReady(true);
          } else if (!cancelled) {
            redirectToLogin();
          }
          return;
        }

        // A temporary network failure must not erase a valid in-memory session.
        if (!cancelled) setReady(true);
      }
    };

    void initializeSession();
    const id = setInterval(() => {
      void refreshPlatformSession().then((ok) => {
        if (!ok && !cancelled) redirectToLogin();
      });
    }, REFRESH_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isAuthPage, router]);

  function handleLogout() {
    const token = platformAuthStorage.getToken();
    if (impersonationState.getEmail() && token) {
      platformApi.endImpersonation(token).catch(() => {});
    }
    platformAuthApi.logout().catch(() => {});
    platformAuthStorage.clearAll();
    router.replace("/platform/login");
  }

  /* ── Loading screen ──────────────────────────────────────────────────────── */
  if (!ready) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex items-center gap-3 text-text-muted">
          <Spinner />
          <span className="text-sm">Yükleniyor…</span>
        </div>
      </div>
    );
  }

  /* ── Auth pages (login, mfa) ─────────────────────────────────────────────── */
  if (isAuthPage) {
    return (
      <div className="min-h-screen bg-background text-text">
        {children}
      </div>
    );
  }

  /* ── Main shell ──────────────────────────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-background text-text flex">

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className="w-60 flex-shrink-0 bg-surface border-r border-border flex flex-col h-screen sticky top-0 overflow-hidden">

        {/* Logo row */}
        <div className="flex items-center gap-3 px-5 h-14 border-b border-border flex-shrink-0">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 shadow-glow-sm"
            style={{ background: "var(--gradient-accent)" }}
          >
            <ShieldCheck className="w-3.5 h-3.5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-text leading-none">Flobrief</p>
            <p className="text-[10px] text-accent font-semibold tracking-widest uppercase mt-0.5">
              Platform Admin
            </p>
          </div>
        </div>

        {/* Search shortcut */}
        <div className="px-3 py-3 border-b border-border flex-shrink-0">
          <div className="flex items-center gap-2 px-3 py-2 bg-surface-2 border border-border rounded-lg text-xs text-text-muted cursor-pointer hover:border-border-hover transition-colors">
            <Search className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="flex-1">Hızlı arama…</span>
            <kbd className="px-1.5 py-0.5 bg-surface-3 border border-border rounded text-[10px] font-mono">⌘K</kbd>
          </div>
        </div>

        {/* Nav groups */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto space-y-5">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="px-3 mb-1.5 text-[10px] font-semibold tracking-widest uppercase text-text-muted/50">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive =
                    pathname === item.href || pathname.startsWith(item.href + "/");
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                        isActive
                          ? "bg-accent/15 text-accent font-medium"
                          : "text-text-muted hover:text-text hover:bg-surface-2"
                      }`}
                    >
                      <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-accent" : ""}`} />
                      <span className="truncate">{item.label}</span>
                      {isActive && (
                        <span className="ml-auto w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-3 py-4 border-t border-border flex-shrink-0">
          <div className="flex items-center gap-2.5 px-3 py-2 mb-1">
            <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
              <ShieldCheck className="w-3 h-3 text-accent" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text truncate">Platform Admin</p>
              <p className="text-[10px] text-text-muted truncate">Tam erişim</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-text-muted hover:text-danger hover:bg-danger/8 transition-all duration-150"
          >
            <LogOut className="w-4 h-4 flex-shrink-0" />
            Çıkış Yap
          </button>
        </div>
      </aside>

      {/* ── Main area ───────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-h-screen overflow-auto">
        {/* Top bar */}
        <header className="h-14 border-b border-border bg-surface flex items-center px-6 gap-4 flex-shrink-0 sticky top-0 z-10">
          <div className="flex-1" />
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className="w-2 h-2 rounded-full bg-success inline-block" />
            Sistem Sağlıklı
          </div>
          <div className="w-px h-5 bg-border" />
          <ThemeToggle />
          <div className="w-px h-5 bg-border" />
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center">
              <ShieldCheck className="w-3.5 h-3.5 text-accent" />
            </div>
            <span className="text-xs font-medium text-text">Admin</span>
          </div>
        </header>

        <ImpersonationBanner />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
