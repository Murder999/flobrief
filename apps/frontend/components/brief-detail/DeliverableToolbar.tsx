"use client";

import { cn } from "@/lib/utils";
import { Download, Maximize2, Eye, EyeOff, FileText } from "lucide-react";
import { fmtDate } from "./shared";

interface DeliverableToolbarProps {
  filename: string;
  versionNumber: number;
  uploadedAt: string | null;
  onDownload: () => void;
  onMaximize: () => void;
  annotationMode: boolean;
  onToggleAnnotationMode: () => void;
  showAnnotationAction: boolean;
}

export function DeliverableToolbar({
  filename,
  versionNumber,
  uploadedAt,
  onDownload,
  onMaximize,
  annotationMode,
  onToggleAnnotationMode,
  showAnnotationAction,
}: DeliverableToolbarProps) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border bg-surface/70">
      <div className="flex items-center gap-2 min-w-0">
        <FileText className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
        <span className="text-[13px] text-text font-medium truncate max-w-[220px]">{filename}</span>
        <span className="text-[11px] text-text-muted flex-shrink-0">v{versionNumber}</span>
        {uploadedAt && (
          <span className="text-[11px] text-text-muted flex-shrink-0 hidden sm:inline">· {fmtDate(uploadedAt)}</span>
        )}
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          type="button"
          onClick={onMaximize}
          className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors"
          title="Büyüt"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={onDownload}
          className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors"
          title="İndir"
        >
          <Download className="w-4 h-4" />
        </button>
        {showAnnotationAction && (
          <button
            type="button"
            onClick={onToggleAnnotationMode}
            className={cn(
              "flex items-center gap-1.5 pl-2.5 pr-3 py-1.5 ml-1 text-[12.5px] font-semibold rounded-full transition-colors",
              annotationMode
                ? "bg-accent text-white shadow-sm"
                : "bg-gradient-accent text-white hover:opacity-90 shadow-sm"
            )}
          >
            {annotationMode ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            {annotationMode ? "Revizyon Modunu Kapat" : "Revizyon Noktası Belirle"}
          </button>
        )}
      </div>
    </div>
  );
}
