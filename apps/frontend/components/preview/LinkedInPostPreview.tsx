"use client";

import { ThumbsUp, MessageCircle, Repeat2, Send, FileText } from "lucide-react";
import { PreviewAssetStage } from "./PreviewAssetStage";
import { truncateCaption } from "./previewPlatformConfig";
import type { PlatformPreviewProps } from "./previewTypes";

/** Pure renderer for linkedin/feed_single, feed_carousel, document_carousel,
 * text_post. Branches only on formatConfig.chrome, never on platform detection. */
export default function LinkedInPostPreview({
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
  const isTextOnly = formatConfig.chrome === "text";
  const isDocument = formatConfig.chrome === "document";

  return (
    <div className="mx-auto w-full max-w-[420px] rounded-xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <div className="w-10 h-10 rounded-lg bg-[#0a66c2] flex-shrink-0" />
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-text truncate">{displayName}</p>
          <p className="text-[10.5px] text-text-muted">Şirket sayfası · şimdi</p>
        </div>
      </div>

      {(caption || config.hashtags?.length) && (
        <p className="px-3 pb-2 text-[12.5px] text-text leading-snug whitespace-pre-line">
          {caption}
          {truncated && <span className="text-text-muted"> devamını gör</span>}
          {config.hashtags && config.hashtags.length > 0 && (
            <span className="text-[#0a66c2]"> {config.hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join(" ")}</span>
          )}
        </p>
      )}

      {!isTextOnly && (
        <>
          {isDocument && (
            <div className="mx-3 mb-2 flex items-center gap-1.5 text-[11px] text-text-muted">
              <FileText className="w-3.5 h-3.5" /> Belge · {slots.length} sayfa
            </div>
          )}
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
                  aria-label={`${i + 1}. ${isDocument ? "sayfaya" : "slayta"} git`}
                  className={`h-1.5 rounded-full transition-all ${i === activeSlotIndex ? "w-4 bg-[#0a66c2]" : "w-1.5 bg-border"}`}
                />
              ))}
            </div>
          )}
        </>
      )}

      <div className="flex items-center justify-around px-3 py-2 border-t border-border mt-1">
        <span className="flex items-center gap-1.5 text-[12px] text-text-muted"><ThumbsUp className="w-4 h-4" /> Beğen</span>
        <span className="flex items-center gap-1.5 text-[12px] text-text-muted"><MessageCircle className="w-4 h-4" /> Yorum</span>
        <span className="flex items-center gap-1.5 text-[12px] text-text-muted"><Repeat2 className="w-4 h-4" /> Repost</span>
        <span className="flex items-center gap-1.5 text-[12px] text-text-muted"><Send className="w-4 h-4" /> Gönder</span>
      </div>
    </div>
  );
}
