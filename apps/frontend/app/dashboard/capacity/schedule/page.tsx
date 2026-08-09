"use client";

import { AllocationEditor } from "@/components/capacity/AllocationEditor";
import { CapacityNavTabs } from "@/components/capacity/CapacityNavTabs";
import { TimeOffRequestForm } from "@/components/capacity/TimeOffRequestForm";
import { WorkScheduleEditor } from "@/components/capacity/WorkScheduleEditor";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { agencyApi, type AgencyMemberRead } from "@/lib/api-client";
import { canManageAllocation, canManageSchedule } from "@/lib/capacity";
import { useEffect, useState } from "react";

export default function CapacitySchedulePage() {
  const { user, accessToken } = useAuth();
  const { activeAgency, isInitialized } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const role = activeAgency?.member_role ?? null;

  const [members, setMembers] = useState<AgencyMemberRead[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const manageSchedule = canManageSchedule(role);
  const manageAllocation = canManageAllocation(role);

  useEffect(() => {
    if (!accessToken || !agencyId || !manageSchedule) return;
    agencyApi
      .listMembers(agencyId, accessToken)
      .then((mems) => setMembers(mems.filter((m) => m.status === "active")))
      .catch(() => {});
  }, [accessToken, agencyId, manageSchedule]);

  useEffect(() => {
    if (user && !selectedUserId) setSelectedUserId(user.id);
  }, [user, selectedUserId]);

  if (!isInitialized || !agencyId || !accessToken || !user) return null;

  const targetUserId = manageSchedule ? selectedUserId ?? user.id : user.id;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <CapacityNavTabs />

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-text">Kapasite Ayarları</h1>
        <p className="text-sm text-text-muted mt-1">Çalışma programınızı yönetin ve izin talebinde bulunun.</p>
      </div>

      {manageSchedule && members.length > 0 && (
        <div className="mb-6 max-w-xs">
          <Select
            label="Ekip Üyesi"
            options={[
              { value: user.id, label: "Ben" },
              ...members
                .filter((m) => m.user_id !== user.id)
                .map((m) => ({ value: m.user_id, label: m.user_full_name ?? m.user_email ?? m.user_id })),
            ]}
            value={targetUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
          />
        </div>
      )}

      <div className="flex flex-col gap-8">
        <WorkScheduleEditor
          userId={targetUserId}
          agencyId={agencyId}
          accessToken={accessToken}
          canManage={manageSchedule}
        />

        <TimeOffRequestForm
          userId={targetUserId}
          currentUserId={user.id}
          agencyId={agencyId}
          accessToken={accessToken}
          role={role}
        />

        {manageAllocation && (
          <AllocationEditor userId={targetUserId} agencyId={agencyId} accessToken={accessToken} />
        )}
      </div>
    </div>
  );
}
