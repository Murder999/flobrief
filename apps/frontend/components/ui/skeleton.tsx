import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-md shimmer", className)}
      {...props}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border bg-surface p-6 shadow-card">
      <Skeleton className="mb-3 h-4 w-24" />
      <Skeleton className="h-8 w-16" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 border-b border-border px-4 py-3">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="h-4 w-24" />
      <Skeleton className="ml-auto h-5 w-20 rounded-full" />
    </div>
  );
}
