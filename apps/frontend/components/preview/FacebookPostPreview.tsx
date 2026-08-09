"use client";

import { ThumbsUp, MessageCircle, Share2, Globe2 } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import { truncateCaption } from "./previewPlatformConfig";
import type { PlatformPreviewProps } from "./previewTypes";

/** Pure renderer for facebook/feed_single, facebook/feed_carousel, facebook/story.
 * Branches only on the format-config "chrome" value it's handed — never on
 * platform detection of its own. */
export default function FacebookPostPreview({
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
  const isStory = formatConfig.chrome === "story";

  const stage = (
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
      className={isStory ? "absolute inset-0 h-full" : undefined}
    />
  );

  if (isStory) {
    return (
      <div className="mx-auto w-full max-w-[280px] rounded-2xl border border-border bg-black overflow-hidden">
        <div className="relative" style={{ aspectRatio: formatConfig.aspectRatio || 9 / 16 }}>
          <div className="absolute top-3 left-2.5 right-2.5 z-10 flex items-center gap-1.5">
            <div className="w-6 h-6 rounded-full bg-blue-600" />
            <span className="text-[11px] font-semibold text-white drop-shadow">{displayName}</span>
          </div>
          {stage}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[420px] rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <div className="w-9 h-9 rounded-full bg-blue-600 flex-shrink-0" />
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-text truncate">{displayName}</p>
          <p className="text-[10.5px] text-text-muted flex items-center gap-1">
            Sponsorlu · <Globe2 className="w-2.5 h-2.5" />
          </p>
        </div>
      </div>

      {(caption || config.hashtags?.length) && (
        <p className="px-3 pb-2 text-[12.5px] text-text leading-snug">
          {caption}
          {truncated && <span className="text-text-muted"> devamını gör</span>}
          {config.hashtags && config.hashtags.length > 0 && (
            <span className="text-blue-600"> {config.hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join(" ")}</span>
          )}
        </p>
      )}

      {stage}

      {slots.length > 1 && (
        <div className="flex items-center justify-center gap-1 py-2">
          {slots.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelectSlot(i)}
              aria-label={`${i + 1}. slayta git`}
              className={`h-1.5 rounded-full transition-all ${i === activeSlotIndex ? "w-4 bg-blue-600" : "w-1.5 bg-border"}`}
            />
          ))}
        </div>
      )}

      <div className="flex items-center justify-around px-3 py-2 border-t border-border mt-1">
        <span className="flex items-center gap-1.5 text-[12px] text-text-muted"><ThumbsUp className="w-4 h-4" /> Beğen</span>
        <span className="flex items-center gap-1.5 text-[12px] text-text-muted"><MessageCircle className="w-4 h-4" /> Yorum Yap</span>
        <span className="flex items-center gap-1.5 text-[12px] text-text-muted"><Share2 className="w-4 h-4" /> Paylaş</span>
      </div>
    </div>
  );
}
