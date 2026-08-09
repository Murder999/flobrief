"use client";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { ManualEntryModal } from "@/components/time-tracking/ManualEntryModal";
import { TimeCategoryBadge } from "@/components/time-tracking/TimeCategoryBadge";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  timeEntryApi,
  timeReportApi,
  type ActiveTimerRead,
  type TimeEntryRead,
} from "@/lib/api-client";
import { Plus, Timer, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function fmtRangeDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "long",
  });
}

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString("tr-TR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtHours(seconds: number | null): string {
  if (seconds === null) return "—";
  return `${(seconds / 3600).toFixed(1)}s`;
}

function EntrySkeleton() {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 animate-pulse">
      <div className="h-4 bg-surface-2 rounded w-1/3 mb-2" />
      <div className="h-3 bg-surface-2 rounded w-1/2" />
    </div>
  );
}

export default function MyTimePage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const { toast, confirm } = useToast();
  const agencyId = activeAgency?.id ?? null;
  const searchParams = useSearchParams();

  // Deep-link params from a time-tracking notification (see
  // notification_routes.py): `timer=active` highlights the running timer,
  // `start`/`end` scope the week shown to the date the notification is about.
  const wantsTimerHighlight = searchParams.get("timer") === "active";
  const rangeStart = searchParams.get("start");
  const rangeEnd = searchParams.get("end");

  const [entries, setEntries] = useState<TimeEntryRead[]>([]);
  const [totalHours, setTotalHours] = useState(0);
  const [billableHours, setBillableHours] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [activeTimer, setActiveTimer] = useState<ActiveTimerRead | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await timeReportApi.getWeekly(agencyId, accessToken, {
        start_date: rangeStart ?? undefined,
        end_date: rangeEnd ?? undefined,
      });
      setEntries([...data.entries].reverse());
      setTotalHours(data.total_hours);
      setBillableHours(data.billable_hours);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, rangeStart, rangeEnd]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!accessToken || !agencyId || !wantsTimerHighlight) return;
    timeEntryApi.getActive(agencyId, accessToken).then(setActiveTimer).catch(() => {});
  }, [accessToken, agencyId, wantsTimerHighlight]);

  const handleDelete = async (entry: TimeEntryRead) => {
    if (!accessToken || !agencyId) return;
    const ok = await confirm({
      title: "Zaman kaydını sil",
      message: "Bu zaman kaydını silmek istediğinizden emin misiniz?",
      destructive: true,
    });
    if (!ok) return;
    try {
      await timeEntryApi.remove(entry.id, agencyId, accessToken);
      toast("Zaman kaydı silindi", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Silinemedi", "error");
    }
  };

  if (!agencyId) return null;

  return (
    <div>
      {wantsTimerHighlight && activeTimer && (
        <div className="mb-4 flex items-center gap-3 rounded-xl border border-accent/40 bg-accent/5 px-4 py-3 animate-pulse">
          <div className="w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center flex-shrink-0">
            <Timer className="w-4 h-4 text-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text">Aktif zamanlayıcınız çalışıyor</p>
            <p className="text-xs text-text-muted truncate">
              {activeTimer.description || "Açıklama yok"} ·{" "}
              {fmtDateTime(activeTimer.started_at)}&apos;den beri
            </p>
          </div>
        </div>
      )}

      {rangeStart && rangeEnd && (
        <div className="mb-4 rounded-xl border border-border bg-surface-2 px-4 py-2.5 text-xs text-text-muted">
          {rangeStart === rangeEnd
            ? `${fmtRangeDate(rangeStart)} tarihi gösteriliyor.`
            : `${fmtRangeDate(rangeStart)} – ${fmtRangeDate(rangeEnd)} aralığı gösteriliyor.`}
        </div>
      )}

      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-4 text-sm text-text-muted">
          <span>
            Toplam: <span className="font-semibold text-text">{totalHours.toFixed(1)}s</span>
          </span>
          <span>
            Faturalandırılabilir:{" "}
            <span className="font-semibold text-text">{billableHours.toFixed(1)}s</span>
          </span>
        </div>
        <Button onClick={() => setModalOpen(true)} size="sm">
          <Plus className="w-3.5 h-3.5" />
          Manuel Kayıt Ekle
        </Button>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <EntrySkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-sm text-danger">
          {error}
        </div>
      ) : entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-sm font-medium text-text mb-1">
            {rangeStart && rangeEnd
              ? rangeStart === rangeEnd
                ? `${fmtRangeDate(rangeStart)} için zaman kaydı yok`
                : `${fmtRangeDate(rangeStart)} – ${fmtRangeDate(rangeEnd)} aralığında zaman kaydı yok`
              : "Bu hafta zaman kaydı yok"}
          </p>
          <p className="text-xs text-text-muted mb-4">
            Bir zamanlayıcı başlatın veya manuel kayıt ekleyin.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {entries.map((entry) => (
            <div
              key={entry.id}
              className="bg-surface border border-border rounded-xl p-4 flex items-center justify-between gap-3"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <TimeCategoryBadge category={entry.category} />
                  {entry.locked && (
                    <span className="text-[10px] text-text-muted">Kilitli</span>
                  )}
                  {!entry.billable && (
                    <span className="text-[10px] text-text-muted">Faturasız</span>
                  )}
                </div>
                {entry.description && (
                  <p className="text-sm text-text truncate">{entry.description}</p>
                )}
                <p className="text-xs text-text-muted mt-0.5">
                  {fmtDateTime(entry.started_at)}
                  {entry.ended_at ? ` – ${fmtDateTime(entry.ended_at)}` : " (devam ediyor)"}
                </p>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className="text-sm font-semibold text-text tabular-nums">
                  {fmtHours(entry.duration_seconds)}
                </span>
                {!entry.locked && (
                  <button
                    onClick={() => handleDelete(entry)}
                    className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-hover transition-colors"
                    title="Sil"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <ManualEntryModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        agencyId={agencyId}
        accessToken={accessToken ?? ""}
        onCreated={() => load()}
      />
    </div>
  );
}
