"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  capacityApi,
  type WorkScheduleDayPayload,
  type WorkScheduleRead,
} from "@/lib/api-client";
import { WEEKDAY_LABELS } from "@/lib/capacity";
import { Lock } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface WorkScheduleEditorProps {
  userId: string;
  agencyId: string;
  accessToken: string;
  canManage: boolean;
}

const DEFAULT_DAYS: WorkScheduleDayPayload[] = WEEKDAY_LABELS.map((_, weekday) => ({
  weekday,
  is_working_day: weekday < 5,
  capacity_minutes: weekday < 5 ? 480 : 0,
}));

/** Own-or-team `WorkSchedule` editor. An edit is always a full
 * soft-delete-old + insert-new on the backend (`WorkScheduleCreate` doubles
 * as the update shape) — this form always submits the full 7-day set. */
export function WorkScheduleEditor({ userId, agencyId, accessToken, canManage }: WorkScheduleEditorProps) {
  const { toast } = useToast();
  const [timezone, setTimezone] = useState("Europe/Istanbul");
  const [days, setDays] = useState<WorkScheduleDayPayload[]>(DEFAULT_DAYS);
  const [hasExisting, setHasExisting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const schedule: WorkScheduleRead = await capacityApi.getSchedule(userId, agencyId, accessToken);
      setHasExisting(true);
      setTimezone(schedule.timezone);
      setDays(
        DEFAULT_DAYS.map((d) => {
          const found = schedule.days.find((sd) => sd.weekday === d.weekday);
          return found
            ? { weekday: found.weekday, is_working_day: found.is_working_day, capacity_minutes: found.capacity_minutes }
            : d;
        })
      );
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setHasExisting(false);
        setTimezone("Europe/Istanbul");
        setDays(DEFAULT_DAYS);
      } else {
        setError(e instanceof Error ? e.message : "Yüklenemedi");
      }
    } finally {
      setLoading(false);
    }
  }, [userId, agencyId, accessToken]);

  useEffect(() => {
    load();
  }, [load]);

  const updateDay = (weekday: number, patch: Partial<WorkScheduleDayPayload>) => {
    setDays((prev) => prev.map((d) => (d.weekday === weekday ? { ...d, ...patch } : d)));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await capacityApi.upsertSchedule(userId, { user_id: userId, timezone, days }, agencyId, accessToken);
      setHasExisting(true);
      toast("Çalışma programı kaydedildi", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Kaydedilemedi", "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="h-56 bg-surface-2 rounded-xl animate-pulse" />;
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Çalışma Programı</CardTitle>
          <CardDescription>
            {hasExisting
              ? "Haftalık çalışma günleri ve kapasite (dakika)."
              : "Henüz bir program tanımlanmamış — aşağıdan oluşturun."}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {error && <p className="text-sm text-danger mb-4">{error}</p>}

        {!canManage ? (
          <div className="flex items-center gap-2 mb-4 text-xs text-text-muted">
            <Lock className="w-3.5 h-3.5" />
            Programı düzenleme yetkiniz yok — yalnızca görüntülüyorsunuz.
          </div>
        ) : (
          <div className="mb-5 max-w-xs">
            <Input
              label="Saat Dilimi (IANA)"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="Europe/Istanbul"
              hint="ör. Europe/Istanbul, Europe/London"
            />
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {days.map((day) => (
            <div key={day.weekday} className="bg-surface-2 border border-border rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-text">{WEEKDAY_LABELS[day.weekday]}</span>
                <input
                  type="checkbox"
                  checked={day.is_working_day}
                  disabled={!canManage}
                  onChange={(e) =>
                    updateDay(day.weekday, {
                      is_working_day: e.target.checked,
                      capacity_minutes: e.target.checked ? day.capacity_minutes || 480 : 0,
                    })
                  }
                  className="accent-accent disabled:opacity-50"
                />
              </div>
              <Input
                type="number"
                min={0}
                disabled={!canManage || !day.is_working_day}
                value={day.is_working_day ? day.capacity_minutes : 0}
                onChange={(e) => updateDay(day.weekday, { capacity_minutes: Math.max(0, Number(e.target.value)) })}
                hint="dakika"
              />
            </div>
          ))}
        </div>

        {canManage && (
          <div className="mt-5 flex justify-end">
            <Button onClick={handleSave} isLoading={saving} size="sm">
              Kaydet
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
