"use client";

import { useState, useCallback, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { demoApi, type DemoPortalSwitchResponse } from "@/lib/api-client";
import { useRouter } from "next/navigation";
import { useLocale } from "@/context/locale-context";
import { cn } from "@/lib/utils";
import { Building2, Briefcase, Loader2, FlaskConical } from "lucide-react";

const PORTALS = [
  {
    id: "agency" as const,
    labelKey: "dashboard.demo.agencyPortal",
    descKey: "dashboard.demo.agencyDesc",
    icon: <Building2 className="w-4 h-4" />,
  },
  {
    id: "brand" as const,
    labelKey: "dashboard.demo.brandPortal",
    descKey: "dashboard.demo.brandDesc",
    icon: <Briefcase className="w-4 h-4" />,
  },
] as const;

export function DemoPortalSwitcher() {
  const { user, accessToken } = useAuth();
  const router = useRouter();
  const { t } = useLocale();
  const [currentPortal, setCurrentPortal] = useState<"agency" | "brand" | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const isDemoUser = user?.user_type === "agency_user" || user?.user_type === "brand_user";

  const fetchSession = useCallback(async () => {
    if (!accessToken || !isDemoUser) return;
    try {
      const session = await demoApi.session(accessToken);
      if (session.is_demo && session.active_portal) {
        setCurrentPortal(session.active_portal);
      } else if (session.is_demo) {
        // Default to agency if not set
        setCurrentPortal("agency");
      }
    } catch {
      // Silent fail - demo switcher not critical
    }
  }, [accessToken, isDemoUser]);

  const switchPortal = async (portal: "agency" | "brand") => {
    if (!accessToken || isLoading) return;
    setIsLoading(true);
    setIsOpen(false);
    try {
      const response: DemoPortalSwitchResponse = await demoApi.switchPortal(portal, accessToken);
      setCurrentPortal(response.portal);
      router.push(response.redirect_to);
      router.refresh();
    } catch (err) {
      console.error("Portal switch failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  if (!isDemoUser) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen((p) => !p)}
        disabled={isLoading}
        className={cn(
          "w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-2",
          "transition-colors text-left group",
          isLoading && "opacity-60 cursor-wait"
        )}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={t("dashboard.demo.switchPortal") ?? "Demo portal değiştir"}
      >
        <div className="w-6 h-6 bg-accent/10 rounded flex items-center justify-center flex-shrink-0">
          <FlaskConical className="w-3.5 h-3.5 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text truncate">
            {t("dashboard.demo.mode") ?? "Demo Modu"}
          </p>
          <p className="text-[11px] text-text-muted truncate">
            {currentPortal
              ? t(PORTALS.find((p) => p.id === currentPortal)?.labelKey as "dashboard.demo.agencyPortal" | "dashboard.demo.brandPortal") ?? ""
              : t("dashboard.demo.loading") ?? "Yükleniyor…"}
          </p>
        </div>
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 text-text-muted flex-shrink-0 animate-spin" />
        ) : (
          <svg
            className={cn(
              "w-3.5 h-3.5 text-text-muted flex-shrink-0 transition-transform",
              isOpen ? "rotate-180" : ""
            )}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute left-0 right-0 top-full mt-1 z-20 bg-surface border border-border rounded-xl shadow-xl overflow-hidden">
            {PORTALS.map((portal) => (
              <button
                key={portal.id}
                onClick={() => switchPortal(portal.id)}
                disabled={isLoading || currentPortal === portal.id}
                role="option"
                aria-selected={currentPortal === portal.id}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-surface-2",
                  "transition-colors text-left",
                  currentPortal === portal.id ? "bg-accent-subtle" : "",
                  isLoading && "opacity-60 cursor-wait"
                )}
              >
                <span
                  className={cn(
                    "w-6 h-6 rounded flex items-center justify-center flex-shrink-0",
                    currentPortal === portal.id
                      ? "bg-accent text-white"
                      : "bg-surface-2 text-text-muted"
                  )}
                >
                  {portal.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text truncate">
                    {t(portal.labelKey as "dashboard.demo.agencyPortal" | "dashboard.demo.brandPortal")}
                  </p>
                  <p className="text-[11px] text-text-muted truncate">
                    {t(portal.descKey as "dashboard.demo.agencyDesc" | "dashboard.demo.brandDesc")}
                  </p>
                </div>
                {currentPortal === portal.id && (
                  <svg
                    className="w-4 h-4 text-accent flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}