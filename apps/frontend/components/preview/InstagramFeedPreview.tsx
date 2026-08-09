"use client";

import { Heart, MessageCircle, Send, Bookmark, MoreHorizontal } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import { truncateCaption } from "./previewPlatformConfig";
import type { PlatformPreviewProps } from "./previewTypes";

/** Pure renderer for instagram/feed_single and instagram/feed_carousel. */
export default function InstagramFeedPreview({
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
  const { text: caption, truncated } = truncateCaption(config.caption, formatConfig);
  const displayName = config.display_name_override || "markaniz";

  return (
    <div className="mx-auto w-full max-w-[420px] rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-amber-400 via-pink-500 to-purple-600 flex-shrink-0" />
          <span className="text-[13px] font-semibold text-text truncate">{displayName}</span>
        </div>
        <MoreHorizontal className="w-4 h-4 text-text-muted flex-shrink-0" />
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
      />

      {slots.length > 1 && (
        <div className="flex items-center justify-center gap-1 py-2">
          {slots.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelectSlot(i)}
              aria-label={`${i + 1}. slayta git`}
              className={`h-1.5 rounded-full transition-all ${i === activeSlotIndex ? "w-4 bg-accent" : "w-1.5 bg-border"}`}
            />
          ))}
        </div>
      )}

      <div className="px-3 py-2.5 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3.5 text-text">
            <Heart className="w-5 h-5" />
            <MessageCircle className="w-5 h-5" />
            <Send className="w-5 h-5" />
          </div>
          <Bookmark className="w-5 h-5 text-text" />
        </div>
        {(caption || config.hashtags?.length) && (
          <p className="text-[12.5px] text-text leading-snug">
            <span className="font-semibold mr-1">{displayName}</span>
            {caption}
            {truncated && <span className="text-text-muted"> devamını gör</span>}
            {config.hashtags && config.hashtags.length > 0 && (
              <span className="text-accent"> {config.hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join(" ")}</span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
