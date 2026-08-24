"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { demoApi } from "@/lib/api-client";
import { useLocale } from "@/context/locale-context";
import { cn } from "@/lib/utils";
import { Building2, Briefcase, Loader2, FlaskConical } from "lucide-react";

type DemoPortal = "agency" | "brand";

const PORTALS = [
  {
    id: "agency" as const,
    labelKey: "dashboard.demo.agencyPortal",
    icon: Building2,
  },
  {
    id: "brand" as const,
    labelKey: "dashboard.demo.brandPortal",
    icon: Briefcase,
  },
] as const;

interface DemoPortalSwitcherProps {
  portal: DemoPortal;
}

export function DemoPortalSwitcher({ portal }: DemoPortalSwitcherProps) {
  const { user, accessToken } = useAuth();
  const { t } = useLocale();
  const [isConfirmedDemo, setIsConfirmedDemo] = useState(false);
  const [currentPortal, setCurrentPortal] = useState<DemoPortal>(portal);
  const [pendingPortal, setPendingPortal] = useState<DemoPortal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestInFlightRef = useRef(false);

  const canHaveDemoSession =
    user?.user_type === "agency_user" || user?.user_type === "brand_user";

  useEffect(() => {
    setCurrentPortal(portal);
  }, [portal]);

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
        if (session.is_demo && session.active_portal) {
          setCurrentPortal(session.active_portal);
        }
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
      targetPortal === currentPortal ||
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
      className="relative shrink-0 px-2.5 py-2.5"
      aria-label={t("dashboard.demo.switchPortal")}
      aria-busy={pendingPortal !== null}
    >
      <div className="rounded-xl border border-accent/20 bg-gradient-to-br from-accent-subtle/80 via-surface to-surface p-1.5 shadow-sm">
        <div className="flex items-center gap-1.5 px-1 pb-1.5">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-accent-subtle">
            <FlaskConical className="h-3 w-3 text-accent" />
          </span>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            {t("dashboard.demo.mode")}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-1 rounded-lg bg-surface-2 p-1">
          {PORTALS.map((portalOption) => {
            const selected = currentPortal === portalOption.id;
            const isPending = pendingPortal === portalOption.id;
            const Icon = portalOption.icon;

            return (
              <button
                key={portalOption.id}
                type="button"
                onClick={() => void switchPortal(portalOption.id)}
                disabled={pendingPortal !== null || selected}
                aria-pressed={selected}
                className={cn(
                  "flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-1 py-1.5 text-[10px] font-semibold leading-tight transition-all",
                  selected
                    ? "bg-gradient-accent text-white shadow-glow-sm ring-1 ring-accent/30"
                    : "text-text-muted hover:bg-surface hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
                  pendingPortal !== null && "cursor-wait"
                )}
              >
                {isPending ? (
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
                ) : (
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                )}
                <span className="text-center">{t(portalOption.labelKey)}</span>
              </button>
            );
          })}
        </div>

        {pendingPortal && (
          <p
            className="flex items-center gap-1.5 px-1 pt-1.5 text-[10px] text-text-muted"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
            {t("dashboard.demo.switching")}
          </p>
        )}

        {error && (
          <p
            className="px-1 pt-1.5 text-[10px] leading-snug text-danger"
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
