"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  timeEntryApi,
  type ActiveTimerRead,
  type TimeEntryCategory,
  type TimeEntryCreateResult,
  type TimeEntryRead,
} from "@/lib/api-client";
import { Play, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { TIME_CATEGORY_OPTIONS } from "./TimeCategoryBadge";

interface TimerControlsProps {
  agencyId: string;
  accessToken: string;
  activeTimer: ActiveTimerRead | null;
  briefId?: string | null;
  brandId?: string | null;
  onStarted: (entry: TimeEntryRead) => void;
  onStopped: (result: TimeEntryCreateResult) => void;
}

function formatElapsed(startedAtIso: string, nowMs: number): string {
  // Recomputed purely from the server's started_at + wall-clock now — never
  // trusts a client-only interval as the source of truth for elapsed time.
  const elapsedMs = Math.max(0, nowMs - new Date(startedAtIso).getTime());
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function TimerControls({
  agencyId,
  accessToken,
  activeTimer,
  briefId,
  brandId,
  onStarted,
  onStopped,
}: TimerControlsProps) {
  const [category, setCategory] = useState<TimeEntryCategory>("design");
  const [description, setDescription] = useState("");
  const [billable, setBillable] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!activeTimer) return;
    const interval = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [activeTimer]);

  const handleStart = async () => {
    setBusy(true);
    setError(null);
    try {
      const entry = await timeEntryApi.start(
        {
          brief_id: briefId ?? undefined,
          brand_id: brandId ?? undefined,
          category,
          description: description.trim() || undefined,
          billable,
        },
        agencyId,
        accessToken
      );
      onStarted(entry);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Zamanlayıcı başlatılamadı");
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    if (!activeTimer) return;
    setBusy(true);
    setError(null);
    try {
      const result = await timeEntryApi.stop(
        activeTimer.id,
        { category, description: description.trim() || undefined, billable },
        agencyId,
        accessToken
      );
      onStopped(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Zamanlayıcı durdurulamadı");
    } finally {
      setBusy(false);
    }
  };

  if (activeTimer) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-2xl font-bold text-text tabular-nums tracking-tight">
            {formatElapsed(activeTimer.started_at, nowMs)}
          </span>
          <Button variant="destructive" size="sm" onClick={handleStop} isLoading={busy}>
            <Square className="w-3.5 h-3.5" />
            Durdur
          </Button>
        </div>
        <Select
          label="Kategori"
          value={category}
          onChange={(e) => setCategory(e.target.value as TimeEntryCategory)}
          options={TIME_CATEGORY_OPTIONS}
        />
        <Input
          label="Açıklama (opsiyonel)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Ne üzerinde çalışıyorsunuz?"
        />
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={billable}
            onChange={(e) => setBillable(e.target.checked)}
            className="rounded border-border"
          />
          Faturalandırılabilir
        </label>
        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Select
        label="Kategori"
        value={category}
        onChange={(e) => setCategory(e.target.value as TimeEntryCategory)}
        options={TIME_CATEGORY_OPTIONS}
      />
      <Input
        label="Açıklama (opsiyonel)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Ne üzerinde çalışacaksınız?"
      />
      <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
        <input
          type="checkbox"
          checked={billable}
          onChange={(e) => setBillable(e.target.checked)}
          className="rounded border-border"
        />
        Faturalandırılabilir
      </label>
      <Button onClick={handleStart} isLoading={busy}>
        <Play className="w-3.5 h-3.5" />
        Zamanlayıcı Başlat
      </Button>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
