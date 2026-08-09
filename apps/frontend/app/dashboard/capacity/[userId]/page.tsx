"use client";

import { MemberCapacityDetail } from "@/components/capacity/MemberCapacityDetail";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { agencyApi, type AgencyMemberRead } from "@/lib/api-client";
import { getRangeForScale, type CapacityScale } from "@/lib/capacity";
import { cn } from "@/lib/utils";
import { ROLE_LABELS } from "@/lib/workspace";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const SCALE_OPTIONS: { value: CapacityScale; label: string }[] = [
  { value: "daily", label: "Günlük" },
  { value: "weekly", label: "Haftalık" },
  { value: "monthly", label: "Aylık" },
];

export default function CapacityMemberDetailPage() {
  const params = useParams<{ userId: string }>();
  const userId = params.userId;
  const { user, accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [scale, setScale] = useState<CapacityScale>("weekly");
  const range = useMemo(() => getRangeForScale(scale), [scale]);
  const [member, setMember] = useState<AgencyMemberRead | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi
      .listMembers(agencyId, accessToken)
      .then((mems) => setMember(mems.find((m) => m.user_id === userId) ?? null))
      .catch(() => {});
  }, [accessToken, agencyId, userId]);

  if (!isInitialized || !agencyId || !accessToken || !user) return null;

  const displayName = member?.user_full_name ?? member?.user_email ?? "Ekip Üyesi";
  const isSelf = user.id === userId;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <Link
        href="/dashboard/capacity"
        className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text mb-4"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Ekip Kapasitesine Dön
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-text">
            {displayName}
            {isSelf && <span className="text-text-muted font-normal"> (Ben)</span>}
          </h1>
          {member && <p className="text-sm text-text-muted mt-1">{ROLE_LABELS[member.role] ?? member.role}</p>}
        </div>
        <div className="flex items-center gap-1 bg-surface-2 border border-border rounded-lg p-1">
          {SCALE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setScale(opt.value)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                scale === opt.value ? "bg-accent text-white" : "text-text-muted hover:text-text"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <MemberCapacityDetail
        userId={userId}
        userName={displayName}
        agencyId={agencyId}
        accessToken={accessToken}
        startDate={range.start}
        endDate={range.end}
      />
    </div>
  );
}
