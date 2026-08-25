"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { demoApi } from "@/lib/api-client";
import { useLocale } from "@/context/locale-context";
import { cn } from "@/lib/utils";
import { FlaskConical, Loader2 } from "lucide-react";

export type DemoPortal = "agency" | "brand";

const PORTALS = [
  {
    id: "agency" as const,
    shortLabelKey: "dashboard.demo.agency",
    labelKey: "dashboard.demo.agencyPortal",
  },
  {
    id: "brand" as const,
    shortLabelKey: "dashboard.demo.brand",
    labelKey: "dashboard.demo.brandPortal",
  },
] as const;

interface DemoPortalSwitcherProps {
  portal: DemoPortal;
}

export function DemoPortalSwitcher({ portal }: DemoPortalSwitcherProps) {
  const { user, accessToken } = useAuth();
  const { t } = useLocale();
  const [isConfirmedDemo, setIsConfirmedDemo] = useState(false);
  const [pendingPortal, setPendingPortal] = useState<DemoPortal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestInFlightRef = useRef(false);

  const canHaveDemoSession =
    user?.user_type === "agency_user" || user?.user_type === "brand_user";

  useEffect(() => {
    let active = true;

    if (!accessToken || !canHaveDemoSession) {
      setIsConfirmedDemo(false);
      return;
    }

    void demoApi
      .session(accessToken)
      .then((session) => {
        if (!active) return;
        setIsConfirmedDemo(session.is_demo);
      })
      .catch(() => {
        if (active) setIsConfirmedDemo(false);
      });

    return () => {
      active = false;
    };
  }, [accessToken, canHaveDemoSession]);

  const switchPortal = async (targetPortal: DemoPortal) => {
    if (
      !accessToken ||
      targetPortal === portal ||
      requestInFlightRef.current
    ) {
      return;
    }

    requestInFlightRef.current = true;
    setPendingPortal(targetPortal);
    setError(null);
    let isNavigating = false;

    try {
      const response = await demoApi.switchPortal(targetPortal, accessToken);
      const expectedRoute = targetPortal === "agency" ? "/dashboard" : "/brand/dashboard";
      if (response.portal !== targetPortal || response.redirect_to !== expectedRoute) {
        setError(t("dashboard.demo.switchError"));
        return;
      }

      isNavigating = true;
      // The backend has atomically replaced the demo identity and HttpOnly
      // refresh session. A new document prevents either portal guard from
      // observing the now-revoked access token during a client-side transition.
      window.location.replace(response.redirect_to);
    } catch {
      setError(t("dashboard.demo.switchError"));
    } finally {
      if (!isNavigating) {
        requestInFlightRef.current = false;
        setPendingPortal(null);
      }
    }
  };

  if (!isConfirmedDemo) return null;

  return (
    <section
      data-testid="demo-portal-switcher"
      data-floating-demo-control
      className="pointer-events-none fixed inset-x-3 bottom-[calc(3.5rem+env(safe-area-inset-bottom,0px)+0.75rem)] z-40 flex justify-center lg:inset-x-auto lg:bottom-6 lg:right-6"
      aria-label={t("dashboard.demo.switchPortal")}
      aria-busy={pendingPortal !== null}
    >
      <div
        data-testid="demo-portal-switcher-dock"
        className="pointer-events-auto w-max max-w-full rounded-2xl border border-border/90 bg-surface/95 p-1.5 shadow-xl backdrop-blur-xl"
      >
        <div className="flex items-center gap-1.5">
          <div className="flex shrink-0 items-center gap-1.5 px-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-md bg-accent-subtle">
              <FlaskConical className="h-3 w-3 text-accent" aria-hidden="true" />
            </span>
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">
              <span className="sm:hidden">{t("dashboard.demo.mobileMode")}</span>
              <span className="hidden sm:inline">{t("dashboard.demo.mode")}</span>
            </p>
          </div>

          <div
            className="grid grid-cols-2 gap-1 rounded-xl bg-surface-2 p-1"
            role="group"
            aria-label={t("dashboard.demo.switchPortal")}
          >
            {PORTALS.map((portalOption) => {
              const selected = portal === portalOption.id;
              const isPending = pendingPortal === portalOption.id;

              return (
                <button
                  key={portalOption.id}
                  type="button"
                  onClick={() => void switchPortal(portalOption.id)}
                  disabled={pendingPortal !== null}
                  aria-label={t(portalOption.labelKey)}
                  aria-pressed={selected}
                  className={cn(
                    "flex h-9 min-w-[68px] items-center justify-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-2 sm:min-w-[76px]",
                    selected
                      ? "bg-accent text-white shadow-sm"
                      : "text-text-muted hover:bg-surface hover:text-text",
                    pendingPortal !== null && "cursor-wait"
                  )}
                >
                  {isPending ? (
                    <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
                  ) : null}
                  <span>{t(portalOption.shortLabelKey)}</span>
                </button>
              );
            })}
          </div>
        </div>

        {pendingPortal && (
          <p
            className="sr-only"
            role="status"
            aria-live="polite"
          >
            {t("dashboard.demo.switching")}
          </p>
        )}

        {error && (
          <p
            className="max-w-[260px] px-2 pb-1 pt-2 text-[10px] leading-snug text-danger"
            role="alert"
            aria-live="assertive"
          >
            {error}
          </p>
        )}
      </div>
    </section>
  );
}
