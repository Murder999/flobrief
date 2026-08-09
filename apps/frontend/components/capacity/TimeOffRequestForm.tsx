"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { capacityApi, type TimeOffRead, type TimeOffTypeValue } from "@/lib/api-client";
import { canApproveTimeOff, canRequestTimeOff, TIME_OFF_TYPE_LABEL } from "@/lib/capacity";
import { Check, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface TimeOffRequestFormProps {
  userId: string;
  currentUserId: string;
  agencyId: string;
  accessToken: string;
  role: string | null;
}

const TYPE_OPTIONS: { value: string; label: string }[] = Object.entries(TIME_OFF_TYPE_LABEL).map(
  ([value, label]) => ({ value, label })
);

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" });
}

function statusBadgeClass(status: string): string {
  if (status === "approved") return "status-success";
  if (status === "rejected") return "status-danger";
  return "status-warning";
}

function statusLabel(status: string): string {
  if (status === "approved") return "Onaylandı";
  if (status === "rejected") return "Reddedildi";
  return "Bekliyor";
}

/** Request/list/approve/reject `TimeOff` for one user (own or, with
 * `TIME_OFF_APPROVE`, a teammate selected on the schedule page). The
 * backend's `GET /capacity/time-off` requires a `user_id` — there is no
 * team-wide pending-approvals endpoint, so the approval queue here is
 * scoped to whichever member is currently selected. */
export function TimeOffRequestForm({ userId, currentUserId, agencyId, accessToken, role }: TimeOffRequestFormProps) {
  const { toast } = useToast();
  const [items, setItems] = useState<TimeOffRead[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [type, setType] = useState<TimeOffTypeValue>("vacation");
  const [notes, setNotes] = useState("");

  const canApprove = canApproveTimeOff(role);
  const canRequest = userId === currentUserId ? canRequestTimeOff(role) || canApprove : canApprove;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await capacityApi.listTimeOff(userId, agencyId, accessToken);
      setItems([...res].sort((a, b) => (a.start_at < b.start_at ? 1 : -1)));
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [userId, agencyId, accessToken]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async () => {
    if (!startDate || !endDate) {
      toast("Başlangıç ve bitiş tarihi girin", "error");
      return;
    }
    setSubmitting(true);
    try {
      const result = await capacityApi.requestTimeOff(
        {
          user_id: userId,
          start_at: `${startDate}T00:00:00Z`,
          end_at: `${endDate}T23:59:59Z`,
          all_day: true,
          type,
          notes: notes === "" ? null : notes,
        },
        agencyId,
        accessToken
      );
      toast(
        result.allocation_warning
          ? "İzin talebi oluşturuldu — bu dönemde mevcut atamalar var, kontrol edin"
          : "İzin talebi oluşturuldu",
        result.allocation_warning ? "warning" : "success"
      );
      setStartDate("");
      setEndDate("");
      setNotes("");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Talep oluşturulamadı", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await capacityApi.approveTimeOff(id, agencyId, accessToken);
      toast("İzin onaylandı", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Onaylanamadı", "error");
    }
  };

  const handleReject = async (id: string) => {
    try {
      await capacityApi.rejectTimeOff(id, {}, agencyId, accessToken);
      toast("İzin reddedildi", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Reddedilemedi", "error");
    }
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>İzinler</CardTitle>
          <CardDescription>
            İzin taleplerini görüntüleyin{canRequest ? " ve yeni talep oluşturun" : ""}.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {canRequest && (
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-5 items-end">
            <Input type="date" label="Başlangıç" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            <Input type="date" label="Bitiş" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            <Select
              label="Tür"
              options={TYPE_OPTIONS}
              value={type}
              onChange={(e) => setType(e.target.value as TimeOffTypeValue)}
            />
            <Button onClick={handleSubmit} isLoading={submitting} size="sm">
              Talep Oluştur
            </Button>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-12 bg-surface-2 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : !items || items.length === 0 ? (
          <p className="text-sm text-text-muted">Henüz izin kaydı yok.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {items.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between gap-3 bg-surface-2 rounded-lg px-3 py-2.5"
              >
                <div className="min-w-0">
                  <p className="text-sm text-text">{TIME_OFF_TYPE_LABEL[t.type] ?? t.type}</p>
                  <p className="text-xs text-text-muted">
                    {fmtDate(t.start_at)} – {fmtDate(t.end_at)}
                    {t.notes ? ` · ${t.notes}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusBadgeClass(t.status)}`}>
                    {statusLabel(t.status)}
                  </span>
                  {canApprove && t.status === "requested" && (
                    <>
                      <button
                        onClick={() => handleApprove(t.id)}
                        className="p-1.5 rounded-lg text-success hover:bg-success/10 transition-colors"
                        title="Onayla"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleReject(t.id)}
                        className="p-1.5 rounded-lg text-danger hover:bg-danger/10 transition-colors"
                        title="Reddet"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
