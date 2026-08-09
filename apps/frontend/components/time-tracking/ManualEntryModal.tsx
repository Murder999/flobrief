"use client";

import { Modal } from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { ApiError, timeEntryApi, type TimeEntryCategory, type TimeEntryRead } from "@/lib/api-client";
import { useState } from "react";
import { TIME_CATEGORY_OPTIONS } from "./TimeCategoryBadge";

interface ManualEntryModalProps {
  isOpen: boolean;
  onClose: () => void;
  agencyId: string;
  accessToken: string;
  briefId?: string | null;
  brandId?: string | null;
  onCreated: (entry: TimeEntryRead, overlapWarning: boolean) => void;
}

function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function ManualEntryModal({
  isOpen,
  onClose,
  agencyId,
  accessToken,
  briefId,
  brandId,
  onCreated,
}: ManualEntryModalProps) {
  const now = new Date();
  const hourAgo = new Date(now.getTime() - 60 * 60 * 1000);

  const [category, setCategory] = useState<TimeEntryCategory>("design");
  const [description, setDescription] = useState("");
  const [startedAt, setStartedAt] = useState(toLocalInputValue(hourAgo));
  const [endedAt, setEndedAt] = useState(toLocalInputValue(now));
  const [billable, setBillable] = useState(true);
  const [needsFutureConfirm, setNeedsFutureConfirm] = useState(false);
  const [confirmFuture, setConfirmFuture] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setCategory("design");
    setDescription("");
    setStartedAt(toLocalInputValue(hourAgo));
    setEndedAt(toLocalInputValue(now));
    setBillable(true);
    setNeedsFutureConfirm(false);
    setConfirmFuture(false);
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await timeEntryApi.createManual(
        {
          brief_id: briefId ?? undefined,
          brand_id: brandId ?? undefined,
          category,
          description: description.trim() || undefined,
          started_at: new Date(startedAt).toISOString(),
          ended_at: new Date(endedAt).toISOString(),
          billable,
          confirm_future: confirmFuture,
        },
        agencyId,
        accessToken
      );
      onCreated(result.entry, result.overlap_warning);
      handleClose();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        const detail = typeof e.detail === "object" && e.detail && "detail" in e.detail
          ? String((e.detail as { detail?: unknown }).detail)
          : e.message;
        if (detail.toLowerCase().includes("gelecek")) {
          setNeedsFutureConfirm(true);
          setError(detail);
        } else {
          setError(detail);
        }
      } else {
        setError(e instanceof Error ? e.message : "Kayıt oluşturulamadı");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Manuel Zaman Kaydı Ekle" maxWidth="md">
      <div className="flex flex-col gap-4">
        <Select
          label="Kategori"
          value={category}
          onChange={(e) => setCategory(e.target.value as TimeEntryCategory)}
          options={TIME_CATEGORY_OPTIONS}
        />

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Başlangıç"
            type="datetime-local"
            value={startedAt}
            onChange={(e) => setStartedAt(e.target.value)}
          />
          <Input
            label="Bitiş"
            type="datetime-local"
            value={endedAt}
            onChange={(e) => setEndedAt(e.target.value)}
          />
        </div>

        <Input
          label="Açıklama (opsiyonel)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Ne üzerinde çalıştınız?"
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

        {needsFutureConfirm && (
          <label className="flex items-center gap-2 text-sm text-warning cursor-pointer">
            <input
              type="checkbox"
              checked={confirmFuture}
              onChange={(e) => setConfirmFuture(e.target.checked)}
              className="rounded border-border"
            />
            Bu gelecek tarihli bir kayıt, onaylıyorum
          </label>
        )}

        {error && <p className="text-xs text-danger">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={handleClose} type="button">
            İptal
          </Button>
          <Button
            onClick={handleSubmit}
            isLoading={submitting}
            disabled={needsFutureConfirm && !confirmFuture}
            type="button"
          >
            Kaydet
          </Button>
        </div>
      </div>
    </Modal>
  );
}
