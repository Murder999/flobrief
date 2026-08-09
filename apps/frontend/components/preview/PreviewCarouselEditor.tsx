"use client";

import { ArrowUp, ArrowDown, Star } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import { cn } from "@/lib/utils";

export interface CarouselSlotDraft {
  asset_id: string;
  position: number;
  is_cover: boolean;
}

interface PreviewCarouselEditorProps {
  slots: CarouselSlotDraft[];
  onChange: (slots: CarouselSlotDraft[]) => void;
  accessToken: string;
  disabled?: boolean;
}

function renumber(slots: CarouselSlotDraft[]): CarouselSlotDraft[] {
  return slots.map((s, i) => ({ ...s, position: i }));
}

/** Controlled up/down/move-to-position buttons + cover radio + slide
 * counter. No drag-and-drop library — the codebase has none, and controlled
 * buttons are simpler to make accessible. */
export function PreviewCarouselEditor({ slots, onChange, accessToken, disabled }: PreviewCarouselEditorProps) {
  const ordered = [...slots].sort((a, b) => a.position - b.position);

  const moveUp = (index: number) => {
    if (index <= 0) return;
    const next = [...ordered];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    onChange(renumber(next));
  };

  const moveDown = (index: number) => {
    if (index >= ordered.length - 1) return;
    const next = [...ordered];
    [next[index], next[index + 1]] = [next[index + 1], next[index]];
    onChange(renumber(next));
  };

  const moveToPosition = (index: number, targetPosition: number) => {
    const clamped = Math.max(0, Math.min(ordered.length - 1, targetPosition));
    if (clamped === index) return;
    const next = [...ordered];
    const [item] = next.splice(index, 1);
    next.splice(clamped, 0, item);
    onChange(renumber(next));
  };

  const setCover = (index: number) => {
    onChange(ordered.map((s, i) => ({ ...s, is_cover: i === index })));
  };

  if (ordered.length === 0) {
    return <p className="text-xs text-text-muted">Henüz slayt eklenmedi.</p>;
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold text-text-muted uppercase tracking-wide">
        Karüsel Sırası · {ordered.length} slayt
      </p>
      <ul className="space-y-1.5">
        {ordered.map((slot, i) => (
          <li
            key={slot.asset_id}
            className="flex items-center gap-2.5 rounded-lg border border-border bg-surface px-2.5 py-2"
          >
            <span className="text-[11px] font-semibold text-text-muted w-4 text-center flex-shrink-0">{i + 1}</span>
            <PreviewAssetStage
              assetId={slot.asset_id}
              accessToken={accessToken}
              aspectRatio={1}
              mode="thumbnail"
              className="w-10 h-10 rounded-md flex-shrink-0"
            />
            <button
              type="button"
              disabled={disabled}
              onClick={() => setCover(i)}
              aria-pressed={slot.is_cover}
              title="Kapak olarak ayarla"
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium border transition-colors disabled:opacity-50",
                slot.is_cover
                  ? "bg-amber-500/10 text-amber-600 border-amber-500/30"
                  : "bg-surface text-text-muted border-border hover:border-amber-500/30",
              )}
            >
              <Star className={cn("w-3 h-3", slot.is_cover && "fill-current")} />
              Kapak
            </button>
            <div className="ml-auto flex items-center gap-1">
              <input
                type="number"
                aria-label={`${i + 1}. slaytın pozisyonu`}
                value={i + 1}
                disabled={disabled}
                min={1}
                max={ordered.length}
                onChange={(e) => moveToPosition(i, Number(e.target.value) - 1)}
                className="w-11 px-1.5 py-1 rounded-md border border-border bg-surface text-[11px] text-text text-center disabled:opacity-50"
              />
              <button
                type="button"
                disabled={disabled || i === 0}
                onClick={() => moveUp(i)}
                aria-label={`${i + 1}. slaytı yukarı taşı`}
                className="p-1 rounded-md border border-border text-text-muted hover:text-text disabled:opacity-30"
              >
                <ArrowUp className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                disabled={disabled || i === ordered.length - 1}
                onClick={() => moveDown(i)}
                aria-label={`${i + 1}. slaytı aşağı taşı`}
                className="p-1 rounded-md border border-border text-text-muted hover:text-text disabled:opacity-30"
              >
                <ArrowDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
