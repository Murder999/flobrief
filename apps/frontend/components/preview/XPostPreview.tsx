"use client";

import { MessageCircle, Repeat2, Heart, BarChart2 } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import { truncateCaption } from "./previewPlatformConfig";
import type { PlatformPreviewProps } from "./previewTypes";

/** Pure renderer for x/feed_single, x/feed_carousel, x/text_post. */
export default function XPostPreview({
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
  const { text: caption } = truncateCaption(config.caption, formatConfig);
  const displayName = config.display_name_override || "markaniz";
  const isTextOnly = formatConfig.chrome === "text";
  const overLimit = (config.caption?.length ?? 0) > formatConfig.captionTruncateAt;

  return (
    <div className="mx-auto w-full max-w-[420px] rounded-xl border border-border bg-surface overflow-hidden p-3">
      <div className="flex gap-2.5">
        <div className="w-10 h-10 rounded-full bg-black flex-shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1 text-[13px]">
            <span className="font-bold text-text truncate">{displayName}</span>
            <span className="text-text-muted">@{displayName.toLowerCase().replace(/\s+/g, "")}</span>
          </div>

          <p className={`text-[13px] leading-snug mt-0.5 whitespace-pre-line ${overLimit ? "text-red-500" : "text-text"}`}>
            {caption}
            {config.hashtags && config.hashtags.length > 0 && (
              <span className="text-accent"> {config.hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join(" ")}</span>
            )}
          </p>

          {!isTextOnly && (
            <>
              <div className="mt-2 rounded-2xl overflow-hidden border border-border">
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
              </div>
              {slots.length > 1 && (
                <div className="flex items-center justify-center gap-1 py-1.5">
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
            </>
          )}

          <div className="flex items-center justify-between mt-2.5 max-w-[300px] text-text-muted">
            <span className="flex items-center gap-1 text-[11px]"><MessageCircle className="w-4 h-4" /></span>
            <span className="flex items-center gap-1 text-[11px]"><Repeat2 className="w-4 h-4" /></span>
            <span className="flex items-center gap-1 text-[11px]"><Heart className="w-4 h-4" /></span>
            <span className="flex items-center gap-1 text-[11px]"><BarChart2 className="w-4 h-4" /></span>
          </div>
        </div>
      </div>
    </div>
  );
}
