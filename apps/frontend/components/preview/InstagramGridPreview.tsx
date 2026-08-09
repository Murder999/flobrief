"use client";

import { Grid3x3 } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import type { PlatformPreviewProps } from "./previewTypes";

/** Pure renderer for instagram/grid — shows the profile grid context around
 * the deliverable's assets so the agency/brand can judge how a multi-slide
 * post will sit among neighbouring tiles. Purely presentational; the
 * surrounding tiles are empty placeholders, never fabricated content. */
export default function InstagramGridPreview({
  config,
  formatConfig,
  slots,
  activeSlotIndex,
  onSelectSlot,
  accessToken,
  annotations,
  activeAnnotationId,
  onAnnotationClick,
  annotationMode,
  onCanvasClick,
  onExitAnnotationMode,
  newPinDraft,
  renderNewPinComposer,
  onCloseNewPinComposer,
  renderAnnotationPopover,
  onCloseAnnotationPopover,
  readOnly,
}: PlatformPreviewProps) {
  const activeSlot = slots[activeSlotIndex] ?? null;
  const displayName = config.display_name_override || "markaniz";

  return (
    <div className="mx-auto w-full max-w-[380px] rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-amber-400 via-pink-500 to-purple-600" />
        <span className="text-[12.5px] font-semibold text-text">{displayName}</span>
        <Grid3x3 className="w-3.5 h-3.5 text-text-muted ml-auto" />
      </div>

      <div className="grid grid-cols-3 gap-[2px] bg-border/60">
        <div className="col-span-2 row-span-2 relative">
          <PreviewAssetStage
            assetId={activeSlot?.asset_id ?? null}
            accessToken={accessToken}
            aspectRatio={1}
            mode={readOnly ? "thumbnail" : "annotatable"}
            annotations={annotations}
            activeAnnotationId={activeAnnotationId}
            onAnnotationClick={onAnnotationClick}
            annotationMode={annotationMode}
            onCanvasClick={onCanvasClick}
            onExitAnnotationMode={onExitAnnotationMode}
            newPinDraft={newPinDraft}
            renderNewPinComposer={renderNewPinComposer}
            onCloseNewPinComposer={onCloseNewPinComposer}
            renderAnnotationPopover={renderAnnotationPopover}
            onCloseAnnotationPopover={onCloseAnnotationPopover}
          />
        </div>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="aspect-square bg-surface-2" aria-hidden="true" />
        ))}
      </div>

      {slots.length > 1 && (
        <div className="flex items-center justify-center gap-1 py-2">
          {slots.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelectSlot(i)}
              aria-label={`${i + 1}. görsele git`}
              className={`h-1.5 rounded-full transition-all ${i === activeSlotIndex ? "w-4 bg-accent" : "w-1.5 bg-border"}`}
            />
          ))}
        </div>
      )}
      <p className="px-3 pb-2.5 text-[10px] text-text-muted">{formatConfig.formatLabel} — profil ızgarasındaki konum önizlemesi</p>
    </div>
  );
}
