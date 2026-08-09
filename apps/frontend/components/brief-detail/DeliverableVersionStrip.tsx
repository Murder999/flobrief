"use client";

import { cn } from "@/lib/utils";
import type { BrandDeliverableRead } from "@/lib/api-client";
import { mediaType, useAuthBlob } from "@/components/media/MediaPreview";
import { CheckCircle, AlertCircle, FileText } from "lucide-react";
import { fmtShortDate } from "./shared";

function StripThumb({ deliverable, accessToken }: { deliverable: BrandDeliverableRead; accessToken: string }) {
  const asset = deliverable.assets[0] ?? null;
  const type = asset ? mediaType(asset.mime_type) : null;
  const { blobUrl, loading } = useAuthBlob(asset?.id ?? "", accessToken, !!asset && (type === "image" || type === "video"));

  if (!asset) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-2">
        <FileText className="w-4 h-4 text-text-muted/50" />
      </div>
    );
  }
  if (loading) {
    return <div className="w-full h-full bg-surface-2 animate-pulse" />;
  }
  if (type === "image" && blobUrl) {
    return <img src={blobUrl} alt="" className="w-full h-full object-cover" />;
  }
  if (type === "video" && blobUrl) {
    return <video src={blobUrl} className="w-full h-full object-cover" muted />;
  }
  return (
    <div className="w-full h-full flex items-center justify-center bg-surface-2">
      <FileText className="w-4 h-4 text-text-muted/50" />
    </div>
  );
}

interface DeliverableVersionStripProps {
  deliverables: BrandDeliverableRead[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  accessToken: string;
}

export function DeliverableVersionStrip({ deliverables, selectedId, onSelect, accessToken }: DeliverableVersionStripProps) {
  if (deliverables.length < 2) return null;

  return (
    <div className="flex items-center gap-2 overflow-x-auto px-4 py-3 border-t border-border bg-surface/40">
      {deliverables.map((d) => {
        const isSelected = d.id === selectedId;
        return (
          <button
            key={d.id}
            type="button"
            data-testid={`version-strip-thumb-${d.id}`}
            onClick={() => onSelect(d.id)}
            className={cn(
              "relative flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all",
              isSelected ? "border-accent shadow-sm" : "border-border hover:border-border-hover"
            )}
            title={`${d.title} · v${d.version_number}`}
          >
            <StripThumb deliverable={d} accessToken={accessToken} />
            <div className="absolute inset-x-0 bottom-0 bg-black/60 px-1 py-0.5 flex items-center justify-between">
              <span className="text-[9px] text-white font-semibold">v{d.version_number}</span>
              {d.status === "approved" && <CheckCircle className="w-2.5 h-2.5 text-emerald-400" />}
              {d.open_annotation_count > 0 && <AlertCircle className="w-2.5 h-2.5 text-amber-400" />}
            </div>
            {d.submitted_at && (
              <span className="absolute top-0.5 right-0.5 text-[8px] text-white/80 bg-black/40 px-1 rounded">
                {fmtShortDate(d.submitted_at)}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
