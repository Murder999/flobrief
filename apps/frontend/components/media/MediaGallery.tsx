"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { AssetRead } from "@/lib/api-client";
import MediaPreview, { Lightbox } from "./MediaPreview";

interface MediaGalleryProps {
  assets: AssetRead[];
  accessToken: string;
  className?: string;
  emptyMessage?: string;
}

export default function MediaGallery({
  assets,
  accessToken,
  className,
  emptyMessage = "Henüz dosya eklenmemiş",
}: MediaGalleryProps) {
  const [lightbox, setLightbox] = useState<AssetRead | null>(null);
  const [view, setView] = useState<"grid" | "list">("grid");

  if (assets.length === 0) {
    return (
      <div className={cn("flex flex-col items-center justify-center py-8 text-center", className)}>
        <div className="w-10 h-10 rounded-full bg-surface border border-border flex items-center justify-center mb-3">
          <svg className="w-5 h-5 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          </svg>
        </div>
        <p className="text-sm text-text-muted">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <>
      {/* View toggle */}
      <div className={cn("space-y-3", className)}>
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-muted">{assets.length} dosya</span>
          <div className="flex items-center gap-0.5 bg-surface border border-border rounded-lg p-0.5">
            <button
              type="button"
              onClick={() => setView("grid")}
              className={cn(
                "p-1.5 rounded transition-colors",
                view === "grid" ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text"
              )}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              className={cn(
                "p-1.5 rounded transition-colors",
                view === "list" ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text"
              )}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>

        {view === "grid" ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {assets.map((asset) => (
              <MediaPreview
                key={asset.id}
                asset={asset}
                accessToken={accessToken}
                compact
                onClick={() => setLightbox(asset)}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {assets.map((asset) => (
              <MediaPreview
                key={asset.id}
                asset={asset}
                accessToken={accessToken}
                onClick={() => setLightbox(asset)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Lightbox */}
      {lightbox && (
        <Lightbox asset={lightbox} accessToken={accessToken} onClose={() => setLightbox(null)} />
      )}
    </>
  );
}
