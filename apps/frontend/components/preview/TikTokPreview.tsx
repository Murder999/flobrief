"use client";

import { Heart, MessageCircle, Share2, Music2 } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import type { PlatformPreviewProps } from "./previewTypes";

/** Pure renderer for tiktok/reel and tiktok/reel_cover. */
export default function TikTokPreview({
  config,
  formatConfig,
  slots,
  activeSlotIndex,
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

        <div className="absolute right-2 bottom-16 z-10 flex flex-col items-center gap-3 text-white">
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center">
            <Heart className="w-5 h-5" />
          </div>
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center">
            <MessageCircle className="w-5 h-5" />
          </div>
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center">
            <Share2 className="w-5 h-5" />
          </div>
        </div>

        <div className="absolute bottom-3 left-3 right-14 z-10 text-white">
          <p className="text-[12px] font-semibold">@{displayName.toLowerCase().replace(/\s+/g, "")}</p>
          {config.caption && <p className="text-[11.5px] mt-1 line-clamp-2">{config.caption}</p>}
          <p className="mt-1.5 flex items-center gap-1 text-[10.5px] text-white/80">
            <Music2 className="w-3 h-3" /> Orijinal ses
          </p>
        </div>
      </div>
      {slots.length > 1 && (
        <p className="px-3 py-1.5 text-[10px] text-white/60 text-center">{formatConfig.formatLabel} — {slots.length} varyant</p>
      )}
    </div>
  );
}
