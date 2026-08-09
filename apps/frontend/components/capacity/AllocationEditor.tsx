"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  briefApi,
  capacityApi,
  type BriefRead,
  type TimeEntryCategory,
  type WorkAllocationRead,
} from "@/lib/api-client";
import { TIME_CATEGORY_OPTIONS } from "@/components/time-tracking/TimeCategoryBadge";
import { formatMinutesAsHours } from "@/lib/capacity";
import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface AllocationEditorProps {
  userId: string;
  agencyId: string;
  accessToken: string;
}

const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "—" },
  ...TIME_CATEGORY_OPTIONS,
];

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" });
}

/** Manual `WorkAllocation` CRUD for one user — the only allocation source
 * this UI writes (`allocation_source: "manual"`); `auto_task`/`auto_brief`
 * rows come only from the read-time formula in `CapacityCalculationService`
 * and are never created here. */
export function AllocationEditor({ userId, agencyId, accessToken }: AllocationEditorProps) {
  const { toast, confirm } = useToast();
  const [allocations, setAllocations] = useState<WorkAllocationRead[] | null>(null);
  const [briefTitles, setBriefTitles] = useState<Record<string, string>>({});
  const [briefOptions, setBriefOptions] = useState<BriefRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [briefId, setBriefId] = useState("");
  const [category, setCategory] = useState<TimeEntryCategory | "">("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [minutes, setMinutes] = useState(60);
  const [locked, setLocked] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await capacityApi.listAllocations(userId, agencyId, accessToken);
      setAllocations(res);
      const ids = Array.from(new Set(res.map((a) => a.brief_id).filter((v): v is string => !!v)));
      const titles = await Promise.all(
        ids.map((id) =>
          briefApi
            .get(id, agencyId, accessToken)
            .then((b) => [id, b.title] as const)
            .catch(() => [id, null] as const)
        )
      );
      setBriefTitles(Object.fromEntries(titles.filter((t): t is [string, string] => t[1] !== null)));
    } catch {
      setAllocations([]);
    } finally {
      setLoading(false);
    }
  }, [userId, agencyId, accessToken]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    briefApi
      .list({ limit: 50 }, agencyId, accessToken)
      .then((res) => setBriefOptions(res.items))
      .catch(() => {});
  }, [agencyId, accessToken]);

  const handleCreate = async () => {
    if (!startDate || !endDate || minutes <= 0) {
      toast("Tarih aralığı ve süre gerekli", "error");
      return;
    }
    setSubmitting(true);
    try {
      const result = await capacityApi.createAllocation(
        {
          user_id: userId,
          brief_id: briefId === "" ? null : briefId,
          category: category === "" ? null : category,
          start_date: startDate,
          end_date: endDate,
          allocated_minutes: minutes,
          locked,
        },
        agencyId,
        accessToken
      );
      toast(
        result.over_capacity_warning ? "Atama oluşturuldu — kapasite aşımı olabilir" : "Atama oluşturuldu",
        result.over_capacity_warning ? "warning" : "success"
      );
      setBriefId("");
      setCategory("");
      setStartDate("");
      setEndDate("");
      setMinutes(60);
      setLocked(false);
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Oluşturulamadı", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    const ok = await confirm({
      title: "Atamayı sil",
      message: "Bu atamayı silmek istediğinizden emin misiniz?",
      destructive: true,
    });
    if (!ok) return;
    try {
      await capacityApi.deleteAllocation(id, agencyId, accessToken);
      toast("Atama silindi", "success");
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Silinemedi", "error");
    }
  };

  const briefSelectOptions = [
    { value: "", label: "Genel kapasite bloğu" },
    ...briefOptions.map((b) => ({ value: b.id, label: b.title })),
  ];

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Manuel Atamalar</CardTitle>
          <CardDescription>
            Belirli bir brief için manuel kapasite bloğu oluşturun; brief seçilmezse genel kapasite bloğu olur.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 mb-5 items-end">
          <Select label="Brief (opsiyonel)" options={briefSelectOptions} value={briefId} onChange={(e) => setBriefId(e.target.value)} />
          <Select
            label="Kategori"
            options={CATEGORY_OPTIONS}
            value={category}
            onChange={(e) => setCategory(e.target.value as TimeEntryCategory | "")}
          />
          <Input type="date" label="Başlangıç" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          <Input type="date" label="Bitiş" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          <Input
            type="number"
            min={1}
            label="Dakika"
            value={minutes}
            onChange={(e) => setMinutes(Math.max(1, Number(e.target.value)))}
          />
          <Button onClick={handleCreate} isLoading={submitting} size="sm">
            Ekle
          </Button>
        </div>

        {loading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-12 bg-surface-2 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : !allocations || allocations.length === 0 ? (
          <p className="text-sm text-text-muted">Henüz manuel atama yok.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {allocations.map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between gap-3 bg-surface-2 rounded-lg px-3 py-2.5"
              >
                <div className="min-w-0">
                  <p className="text-sm text-text truncate">
                    {a.brief_id ? briefTitles[a.brief_id] ?? "Brief" : "Genel kapasite bloğu"}
                  </p>
                  <p className="text-xs text-text-muted">
                    {fmtDate(a.start_date)} – {fmtDate(a.end_date)}
                    {a.locked && " · Kilitli"}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-sm font-semibold text-text tabular-nums">
                    {formatMinutesAsHours(a.allocated_minutes)}
                  </span>
                  <button
                    onClick={() => handleDelete(a.id)}
                    className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-hover transition-colors"
                    title="Sil"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
