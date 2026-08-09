"use client";

import { useWorkspace } from "@/context/workspace-context";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

const TEAM_SCOPED_ROLES = new Set(["owner", "admin", "brand_manager"]);

// Only these three share the date-range filter (useDateRangeFilter) — /my
// and /weekly and /by-brief have different, single-period semantics and
// must not inherit a stale range from the team tabs.
const DATE_FILTER_TABS = new Set([
  "/dashboard/time/team",
  "/dashboard/time/by-brand",
  "/dashboard/time/missing",
]);

interface TimeTab {
  href: string;
  label: string;
  teamOnly?: boolean;
}

const TABS: TimeTab[] = [
  { href: "/dashboard/time/my", label: "Benim Zamanım" },
  { href: "/dashboard/time/weekly", label: "Haftalık Timesheet" },
  { href: "/dashboard/time/team", label: "Ekip Timesheet", teamOnly: true },
  { href: "/dashboard/time/by-brand", label: "Marka Bazlı", teamOnly: true },
  { href: "/dashboard/time/by-brief", label: "Brief Bazlı", teamOnly: true },
  { href: "/dashboard/time/missing", label: "Eksik Zamanlar", teamOnly: true },
];

export default function TimeTrackingLayout({ children }: { children: ReactNode }) {
  const { activeAgency } = useWorkspace();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // Client-side hiding is a UX convenience only — every team-scoped endpoint
  // is also 403'd server-side regardless of what tabs are shown here.
  const canViewTeam = TEAM_SCOPED_ROLES.has(activeAgency?.member_role ?? "");
  const visibleTabs = TABS.filter((t) => !t.teamOnly || canViewTeam);

  // Carry range/start/end across the three date-filtered tabs only, so
  // switching e.g. Ekip → Marka Bazlı keeps the same period selected.
  const filterQuery = DATE_FILTER_TABS.has(pathname)
    ? (() => {
        const params = new URLSearchParams();
        for (const key of ["range", "start", "end"]) {
          const v = searchParams.get(key);
          if (v) params.set(key, v);
        }
        return params.toString();
      })()
    : "";

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-text">Zaman Takibi</h1>
        <p className="text-sm text-text-muted mt-1">
          Brief ve marka bazlı harcanan zamanı takip edin
        </p>
      </div>

      <div className="flex items-center gap-1 border-b border-border mb-6 overflow-x-auto">
        {visibleTabs.map((tab) => {
          const isActive = pathname === tab.href || pathname.startsWith(tab.href + "/");
          const href =
            filterQuery && DATE_FILTER_TABS.has(tab.href)
              ? `${tab.href}?${filterQuery}`
              : tab.href;
          return (
            <Link
              key={tab.href}
              href={href}
              className={cn(
                "px-3 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors -mb-px",
                isActive
                  ? "border-accent text-accent"
                  : "border-transparent text-text-muted hover:text-text"
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {children}
    </div>
  );
}
