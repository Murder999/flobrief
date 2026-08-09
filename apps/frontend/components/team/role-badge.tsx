import { ROLE_COLORS, ROLE_LABELS } from "@/lib/workspace";

interface RoleBadgeProps {
  role: string;
}

export function RoleBadge({ role }: RoleBadgeProps) {
  const label = ROLE_LABELS[role] ?? role;
  const color = ROLE_COLORS[role] ?? "text-text-muted bg-surface-2";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${color}`}
    >
      {label}
    </span>
  );
}
