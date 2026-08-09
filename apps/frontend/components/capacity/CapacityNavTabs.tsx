"use client";

import { cn } from "@/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/dashboard/capacity", label: "Ekip Kapasitesi" },
  { href: "/dashboard/capacity/unassigned", label: "Atanmamış İşler" },
  { href: "/dashboard/capacity/schedule", label: "Programım" },
];

/** Shared tab strip for the three top-level capacity pages — matches the
 * `app/dashboard/time/layout.tsx` tab convention. Not a shared layout.tsx
 * because `[userId]` is a drill-down detail route, not a peer tab. */
export function CapacityNavTabs() {
  const pathname = usePathname();
  return (
    <div className="flex items-center gap-1 border-b border-border mb-6 overflow-x-auto">
      {TABS.map((tab) => {
        const isActive = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "px-3 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors -mb-px",
              isActive ? "border-accent text-accent" : "border-transparent text-text-muted hover:text-text"
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
