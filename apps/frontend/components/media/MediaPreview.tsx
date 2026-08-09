"use client";

import { useState, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { AssetRead } from "@/lib/api-client";
import { showGlobalToast } from "@/components/ui/toast";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function rawUrl(id: string) {
  return `${API_BASE}/api/v1/assets/${id}/download`;
}

export function fmtSize(bytes: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function mediaType(mime: string): "image" | "video" | "pdf" | "file" {
  if (!mime) return "file";
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime === "application/pdf") return "pdf";
  return "file";
}

// ── Authenticated blob URL hook ───────────────────────────────────────────────
// The download endpoint requires JWT — plain <img src> doesn't send
// Authorization header, so we fetch manually and create a blob URL.

export function useAuthBlob(assetId: string, accessToken: string, enabled = true) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!enabled || !accessToken) return;
    let objectUrl: string | null = null;
    let cancelled = false;

    setLoading(true);
    setFailed(false);
    setBlobUrl(null);

    fetch(rawUrl(assetId), {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) { setFailed(true); setLoading(false); }
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [assetId, accessToken, enabled]);

  return { blobUrl, loading, failed };
}

// Guards against duplicate simultaneous downloads (e.g. a double-click)
// firing the same fetch + <a download> sequence twice.
const pendingDownloads = new Set<string>();

export async function downloadWithAuth(
  assetId: string,
  filename: string,
  accessToken: string
): Promise<boolean> {
  if (pendingDownloads.has(assetId)) return false;
  pendingDownloads.add(assetId);
  try {
    const resp = await fetch(rawUrl(assetId), {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!resp.ok) {
      if (resp.status === 401 || resp.status === 403) {
        showGlobalToast("Dosya indirilemedi. Yetkiniz veya indirme bağlantısının süresi dolmuş olabilir.", "error");
      } else if (resp.status === 404) {
        showGlobalToast("Dosya bulunamadı. Kaldırılmış olabilir.", "error");
      } else {
        showGlobalToast("Dosya indirilemedi. Lütfen tekrar deneyin.", "error");
      }
      return false;
    }
    const blob = await resp.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(href);
    return true;
  } catch {
    showGlobalToast("Dosya indirilemedi. Ağ bağlantınızı kontrol edip tekrar deneyin.", "error");
    return false;
  } finally {
    pendingDownloads.delete(assetId);
  }
}

// ── File icon ─────────────────────────────────────────────────────────────────

function FileIcon({ type }: { type: "image" | "video" | "pdf" | "file" }) {
  if (type === "pdf") {
    return (
      <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
        <span className="text-[10px] font-bold text-red-500 uppercase">PDF</span>
      </div>
    );
  }
  if (type === "video") {
    return (
      <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
        <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
    );
  }
  return (
    <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
      <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    </div>
  );
}

// ── Main preview card ─────────────────────────────────────────────────────────

interface MediaPreviewProps {
  asset: AssetRead;
  accessToken: string;
  onClick?: () => void;
  compact?: boolean;
}

export default function MediaPreview({ asset, accessToken, onClick, compact = false }: MediaPreviewProps) {
  const type = mediaType(asset.mime_type);
  const { blobUrl, loading, failed } = useAuthBlob(asset.id, accessToken, type === "image" || type === "video");

  if (compact) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="group relative aspect-square rounded-xl overflow-hidden bg-surface border border-border hover:border-accent/40 transition-all"
        title={asset.filename}
      >
        {loading && (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-5 h-5 animate-spin text-text-muted/30" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          </div>
        )}
        {!loading && blobUrl && type === "image" && (
          <img src={blobUrl} alt={asset.filename} className="w-full h-full object-cover" />
        )}
        {!loading && blobUrl && type === "video" && (
          <video src={blobUrl} className="w-full h-full object-cover" muted />
        )}
        {!loading && (failed || (type !== "image" && type !== "video")) && (
          <div className="w-full h-full flex items-center justify-center">
            <FileIcon type={type} />
          </div>
        )}

        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <div className="absolute bottom-0 inset-x-0 p-1.5 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
          <p className="text-[10px] text-white truncate">{asset.filename}</p>
        </div>
      </button>
    );
  }

  // Full card
  return (
    <div className="flex items-start gap-3 p-3 rounded-xl border border-border bg-surface hover:border-border/80 transition-colors">
      {type === "image" && !loading && blobUrl ? (
        <button type="button" onClick={onClick} className="flex-shrink-0">
          <img
            src={blobUrl}
            alt={asset.filename}
            className="w-16 h-16 rounded-lg object-cover cursor-pointer hover:opacity-90 transition-opacity"
          />
        </button>
      ) : type === "image" && loading ? (
        <div className="w-16 h-16 rounded-lg bg-surface-2 flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 animate-spin text-text-muted/40" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
        </div>
      ) : (
        <FileIcon type={type} />
      )}

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text truncate">{asset.filename}</p>
        <div className="flex items-center gap-2 mt-0.5">
          {asset.mime_type && (
            <span className="text-[11px] text-text-muted uppercase">{asset.mime_type.split("/")[1]}</span>
          )}
          {asset.size_bytes && (
            <span className="text-[11px] text-text-muted">{fmtSize(asset.size_bytes)}</span>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={() => downloadWithAuth(asset.id, asset.filename, accessToken)}
        className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors flex-shrink-0"
        title="İndir"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
      </button>
    </div>
  );
}

// ── Lightbox ──────────────────────────────────────────────────────────────────

interface LightboxProps {
  asset: AssetRead;
  accessToken: string;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Lightbox({ asset, accessToken, onClose }: LightboxProps) {
  const type = mediaType(asset.mime_type);
  const { blobUrl, loading } = useAuthBlob(asset.id, accessToken);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Escape closes the lightbox; body scroll is locked while it's open;
  // focus moves into the dialog on open, is trapped inside it (Tab/Shift+Tab
  // wrap at the edges), and returns to the trigger on close.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !containerRef.current) return;

      const focusable = Array.from(
        containerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [onClose]);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-[9999] bg-black/92 flex flex-col"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={asset.filename}
    >
      <div className="flex items-center justify-between px-5 py-3 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
        <p className="text-sm text-white font-medium truncate max-w-lg">{asset.filename}</p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => downloadWithAuth(asset.id, asset.filename, accessToken)}
            className="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
            title="İndir"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            title="Kapat"
            className="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-4 overflow-auto" onClick={(e) => e.stopPropagation()}>
        {loading && (
          <div className="flex flex-col items-center gap-3 text-white/40">
            <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            <span className="text-xs">Yükleniyor…</span>
          </div>
        )}
        {!loading && blobUrl && type === "image" && (
          <img src={blobUrl} alt={asset.filename} className="max-w-full max-h-full object-contain rounded-lg shadow-2xl" />
        )}
        {!loading && blobUrl && type === "video" && (
          <video src={blobUrl} controls className="max-w-full max-h-full rounded-lg shadow-2xl" />
        )}
        {!loading && type !== "image" && type !== "video" && (
          <div className="flex flex-col items-center gap-4 text-white">
            <FileIcon type={type} />
            <p className="text-sm opacity-70">{asset.filename}</p>
            <button
              type="button"
              onClick={() => downloadWithAuth(asset.id, asset.filename, accessToken)}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-sm transition-colors"
            >
              İndir
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
