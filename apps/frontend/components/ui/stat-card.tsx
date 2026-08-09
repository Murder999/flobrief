import { cn } from "@/lib/utils";
import type { ReactNode } from "react";
import { Skeleton } from "./skeleton";

type TrendDirection = "up" | "down" | "neutral";

interface StatCardTrend {
  value: string;
  direction: TrendDirection;
}

interface StatCardProps {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  trend?: StatCardTrend;
  loading?: boolean;
  className?: string;
}

const TREND_COLOR: Record<TrendDirection, string> = {
  up: "text-success",
  down: "text-danger",
  neutral: "text-text-muted",
};

export function StatCard({ label, value, icon, trend, loading = false, className }: StatCardProps) {
  if (loading) {
    return (
      <div className={cn("bg-surface border border-border rounded-xl p-5", className)}>
        <Skeleton className="mb-3 h-3 w-20" />
        <Skeleton className="h-7 w-16" />
      </div>
    );
  }

  return (
    <div className={cn("bg-surface border border-border rounded-xl p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-text-muted tracking-wide truncate">{label}</p>
          <div className="mt-2 text-2xl font-bold text-text tabular-nums">{value}</div>
          {trend && (
            <p className={cn("mt-1.5 text-xs font-medium", TREND_COLOR[trend.direction])}>
              {trend.value}
            </p>
          )}
        </div>
        {icon && (
          <div className="w-9 h-9 rounded-lg bg-accent/10 text-accent flex items-center justify-center flex-shrink-0">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
