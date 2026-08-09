import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

type BadgeVariant =
  | "default"
  | "draft"
  | "submitted"
  | "in_review"
  | "approved"
  | "revision_requested"
  | "rejected"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "purple"
  | "accent";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  dot?: boolean;
}

const variantClasses: Record<BadgeVariant, string> = {
  default:            "status-neutral",
  draft:              "status-neutral",
  submitted:          "status-info",
  in_review:          "status-warning",
  approved:           "status-success",
  revision_requested: "status-danger",
  rejected:           "status-danger",
  success:            "status-success",
  warning:            "status-warning",
  danger:             "status-danger",
  info:               "status-info",
  purple:             "status-purple",
  accent:             "status-accent",
};

const dotColors: Record<BadgeVariant, string> = {
  default:            "bg-text-muted",
  draft:              "bg-text-muted",
  submitted:          "bg-info",
  in_review:          "bg-warning",
  approved:           "bg-success",
  revision_requested: "bg-danger",
  rejected:           "bg-danger",
  success:            "bg-success",
  warning:            "bg-warning",
  danger:             "bg-danger",
  info:               "bg-info",
  purple:             "bg-purple",
  accent:             "bg-accent",
};

export function Badge({
  variant = "default",
  dot = false,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        variantClasses[variant],
        className
      )}
      {...props}
    >
      {dot && (
        <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", dotColors[variant])} />
      )}
      {children}
    </span>
  );
}
