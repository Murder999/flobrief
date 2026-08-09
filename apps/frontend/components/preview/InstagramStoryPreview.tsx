"use client";

import { X, Send, Heart, MoreHorizontal } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import type { PlatformPreviewProps } from "./previewTypes";

/** Pure renderer for instagram/story, instagram/reel, instagram/reel_cover. */
export default function InstagramStoryPreview({
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
    <div className="mx-auto w-full max-w-[280px] rounded-2xl border border-border bg-black overflow-hidden">
      <div className="relative" style={{ aspectRatio: formatConfig.aspectRatio || 9 / 16 }}>
        {slots.length > 1 && (
          <div className="absolute top-2 inset-x-2 z-10 flex gap-1">
            {slots.map((s, i) => (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelectSlot(i)}
                aria-label={`${i + 1}. slayta git`}
                className={`h-0.5 flex-1 rounded-full ${i <= activeSlotIndex ? "bg-white" : "bg-white/30"}`}
              />
            ))}
          </div>
        )}
        <div className="absolute top-4 left-2 right-2 z-10 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-amber-400 via-pink-500 to-purple-600 ring-2 ring-white/70" />
            <span className="text-[11px] font-semibold text-white drop-shadow">{displayName}</span>
          </div>
          <div className="flex items-center gap-1.5 text-white/90">
            <MoreHorizontal className="w-3.5 h-3.5" />
            <X className="w-3.5 h-3.5" />
          </div>
        </div>

        <PreviewAssetStage
          assetId={activeSlot?.asset_id ?? null}
          accessToken={accessToken}
          aspectRatio={formatConfig.aspectRatio}
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
          safeZones={formatConfig.safeZones}
          className="absolute inset-0 h-full"
        />

        {config.caption && (
          <p className="absolute bottom-14 left-3 right-3 z-10 text-[12px] text-white drop-shadow line-clamp-2">
            {config.caption}
          </p>
        )}

        <div className="absolute bottom-2.5 inset-x-2 z-10 flex items-center gap-2">
          <div className="flex-1 rounded-full border border-white/40 px-3 py-1.5 text-[11px] text-white/80">
            Mesaj gönder
          </div>
          <Heart className="w-4 h-4 text-white" />
          <Send className="w-4 h-4 text-white" />
        </div>
      </div>
    </div>
  );
}
