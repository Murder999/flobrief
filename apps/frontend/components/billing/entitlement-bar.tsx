interface EntitlementBarProps {
  label: string;
  used: number;
  limit: number | null;
}

export function EntitlementBar({ label, used, limit }: EntitlementBarProps) {
  const unlimited = limit === null;
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / limit) * 100));
  const isCritical = !unlimited && pct >= 90;
  const isWarning = !unlimited && pct >= 70 && pct < 90;

  const barColor = isCritical
    ? "bg-red-500"
    : isWarning
      ? "bg-amber-500"
      : "bg-indigo-500";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-300">{label}</span>
        <span className={`font-medium ${isCritical ? "text-red-400" : "text-gray-400"}`}>
          {unlimited ? `${used} / Sınırsız` : `${used} / ${limit}`}
        </span>
      </div>
      {!unlimited && (
        <div className="h-1.5 w-full rounded-full bg-white/10">
          <div
            className={`h-full rounded-full transition-all ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
