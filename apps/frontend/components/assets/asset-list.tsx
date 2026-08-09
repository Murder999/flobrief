"use client";

import { useState } from "react";
import { assetApi, type AssetRead } from "@/lib/api-client";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

import { useAuthBlob, downloadWithAuth } from "@/components/media/MediaPreview";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function isImage(mime: string) { return mime.startsWith("image/"); }
function isVideo(mime: string) { return mime.startsWith("video/"); }
function isPdf(mime: string) { return mime === "application/pdf"; }

// ── File icon (non-image fallback) ────────────────────────────────────────────

function FileTypeIcon({ mimeType, size = "md" }: { mimeType: string; size?: "sm" | "md" }) {
  const dim = size === "sm" ? "w-7 h-7" : "w-9 h-9";
  const base = `${dim} rounded-lg flex items-center justify-center font-bold text-xs flex-shrink-0`;

  if (isImage(mimeType)) return (
    <div className={`${base} bg-violet-500/10 text-violet-400`}>
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    </div>
  );
  if (isPdf(mimeType)) return (
    <div className={`${base} bg-red-500/10 text-red-400`}>PDF</div>
  );
  if (isVideo(mimeType)) return (
    <div className={`${base} bg-purple-500/10 text-purple-400`}>
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
    </div>
  );
  if (mimeType.startsWith("audio/")) return (
    <div className={`${base} bg-emerald-500/10 text-emerald-400`}>
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
      </svg>
    </div>
  );
  return (
    <div className={`${base} bg-surface-2 text-text-muted`}>
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    </div>
  );
}

// ── Lightbox ──────────────────────────────────────────────────────────────────

interface LightboxProps {
  asset: AssetRead;
  accessToken: string;
  onClose: () => void;
}

function Lightbox({ asset, accessToken, onClose }: LightboxProps) {
  const { blobUrl, loading } = useAuthBlob(asset.id, accessToken);

  return (
    <div className="fixed inset-0 z-[9999] bg-black/92 flex flex-col" onClick={onClose}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
        <p className="text-sm text-white font-medium truncate max-w-lg">{asset.original_filename}</p>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">{formatBytes(asset.size_bytes)}</span>
          <button
            type="button"
            onClick={() => downloadWithAuth(asset.id, asset.original_filename, accessToken)}
            className="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
            title="İndir"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
          <button type="button" onClick={onClose} className="p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Media */}
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
        {!loading && blobUrl && isImage(asset.mime_type) && (
          <img src={blobUrl} alt={asset.original_filename} className="max-w-full max-h-full object-contain rounded-lg shadow-2xl" />
        )}
        {!loading && blobUrl && isVideo(asset.mime_type) && (
          <video src={blobUrl} controls autoPlay className="max-w-full max-h-full rounded-lg shadow-2xl" />
        )}
        {!loading && !isImage(asset.mime_type) && !isVideo(asset.mime_type) && (
          <div className="flex flex-col items-center gap-4 text-white">
            <FileTypeIcon mimeType={asset.mime_type} />
            <p className="text-sm opacity-70">{asset.original_filename}</p>
            <button
              type="button"
              onClick={() => downloadWithAuth(asset.id, asset.original_filename, accessToken)}
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

// ── Image thumbnail card ──────────────────────────────────────────────────────

interface ImageCardProps {
  asset: AssetRead;
  accessToken: string;
  onPreview: () => void;
  onDelete: () => void;
  deleting: boolean;
}

function ImageCard({ asset, accessToken, onPreview, onDelete, deleting }: ImageCardProps) {
  const { blobUrl, loading, failed } = useAuthBlob(asset.id, accessToken);

  return (
    <div className="group relative rounded-xl overflow-hidden border border-border bg-surface-2 aspect-square">
      {/* Thumbnail */}
      <button type="button" onClick={onPreview} className="w-full h-full block">
        {loading && (
          <div className="w-full h-full flex items-center justify-center">
            <svg className="w-5 h-5 animate-spin text-text-muted/40" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          </div>
        )}
        {!loading && blobUrl && (
          <img
            src={blobUrl}
            alt={asset.original_filename}
            className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
          />
        )}
        {!loading && failed && (
          <div className="w-full h-full flex items-center justify-center">
            <FileTypeIcon mimeType={asset.mime_type} />
          </div>
        )}
      </button>

      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors pointer-events-none" />

      {/* Bottom label */}
      <div className="absolute bottom-0 inset-x-0 p-2 bg-gradient-to-t from-black/80 to-transparent translate-y-full group-hover:translate-y-0 transition-transform duration-200 pointer-events-none">
        <p className="text-[10px] text-white truncate">{asset.original_filename}</p>
        <p className="text-[10px] text-white/50">{formatBytes(asset.size_bytes)}</p>
      </div>

      {/* Action buttons */}
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); downloadWithAuth(asset.id, asset.original_filename, accessToken); }}
          className="p-1 rounded-md bg-black/60 text-white hover:bg-black/80 transition-colors"
          title="İndir"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          disabled={deleting}
          className="p-1 rounded-md bg-black/60 text-red-400 hover:bg-red-600 hover:text-white transition-colors disabled:opacity-40"
          title="Sil"
        >
          {deleting ? (
            <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          ) : (
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}

// ── File / video row ──────────────────────────────────────────────────────────

interface FileRowProps {
  asset: AssetRead;
  accessToken: string;
  onPreview?: () => void;
  onDelete: () => void;
  deleting: boolean;
}

function FileRow({ asset, accessToken, onPreview, onDelete, deleting }: FileRowProps) {
  return (
    <div className="group flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-surface-2 transition-colors">
      <button
        type="button"
        onClick={onPreview}
        className={onPreview ? "flex-shrink-0 cursor-pointer" : "flex-shrink-0 cursor-default"}
        disabled={!onPreview}
      >
        <FileTypeIcon mimeType={asset.mime_type} />
      </button>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text truncate" title={asset.original_filename}>
          {asset.original_filename}
        </p>
        <p className="text-xs text-text-muted">
          {formatBytes(asset.size_bytes)} · {asset.mime_type.split("/")[1]?.toUpperCase()}
        </p>
      </div>

      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          type="button"
          onClick={() => downloadWithAuth(asset.id, asset.original_filename, accessToken)}
          className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors"
          title="İndir"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
        <button
          onClick={onDelete}
          disabled={deleting}
          className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-40"
          title="Sil"
        >
          {deleting ? (
            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}

// ── Asset item wrapper ────────────────────────────────────────────────────────

interface AssetItemProps {
  asset: AssetRead;
  agencyId: string;
  accessToken: string;
  onDeleted: (id: string) => void;
  onPreview: (asset: AssetRead) => void;
}

function AssetItem({ asset, agencyId, accessToken, onDeleted, onPreview }: AssetItemProps) {
  const [deleting, setDeleting] = useState(false);
  const { confirm } = useToast();

  const handleDelete = async () => {
    const ok = await confirm({
      title: "Dosyayı Sil",
      message: `"${asset.original_filename}" silinsin mi? Bu işlem geri alınamaz.`,
      confirmLabel: "Sil",
      destructive: true,
    });
    if (!ok) return;
    setDeleting(true);
    try {
      await assetApi.delete(asset.id, agencyId, accessToken);
      onDeleted(asset.id);
    } catch {
      setDeleting(false);
    }
  };

  if (isImage(asset.mime_type)) {
    return (
      <ImageCard
        asset={asset}
        accessToken={accessToken}
        onPreview={() => onPreview(asset)}
        onDelete={handleDelete}
        deleting={deleting}
      />
    );
  }

  return (
    <FileRow
      asset={asset}
      accessToken={accessToken}
      onPreview={isVideo(asset.mime_type) ? () => onPreview(asset) : undefined}
      onDelete={handleDelete}
      deleting={deleting}
    />
  );
}

// ── Main AssetList ────────────────────────────────────────────────────────────

interface AssetListProps {
  assets: AssetRead[];
  agencyId: string;
  accessToken: string;
  onDeleted: (id: string) => void;
}

export function AssetList({ assets, agencyId, accessToken, onDeleted }: AssetListProps) {
  const [lightboxAsset, setLightboxAsset] = useState<AssetRead | null>(null);

  if (assets.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-surface/50 py-8 text-center">
        <svg className="w-8 h-8 text-text-muted/30 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
        <p className="text-sm text-text-muted">Henüz dosya eklenmedi.</p>
      </div>
    );
  }

  const images = assets.filter((a) => isImage(a.mime_type));
  const others = assets.filter((a) => !isImage(a.mime_type));

  return (
    <>
      <div className="space-y-3">
        {images.length > 0 && (
          <div className={cn(
            "grid gap-2",
            images.length === 1 ? "grid-cols-1 max-w-[240px]" :
            images.length === 2 ? "grid-cols-2" :
            images.length === 3 ? "grid-cols-3" :
            "grid-cols-2 sm:grid-cols-3 md:grid-cols-4"
          )}>
            {images.map((asset) => (
              <AssetItem
                key={asset.id}
                asset={asset}
                agencyId={agencyId}
                accessToken={accessToken}
                onDeleted={onDeleted}
                onPreview={setLightboxAsset}
              />
            ))}
          </div>
        )}

        {others.length > 0 && (
          <div className={cn("rounded-xl border border-border bg-surface overflow-hidden", images.length > 0 && "mt-1")}>
            {images.length > 0 && (
              <div className="px-4 py-2 border-b border-border">
                <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">Diğer Dosyalar</p>
              </div>
            )}
            <div className="p-2 space-y-0.5">
              {others.map((asset) => (
                <AssetItem
                  key={asset.id}
                  asset={asset}
                  agencyId={agencyId}
                  accessToken={accessToken}
                  onDeleted={onDeleted}
                  onPreview={setLightboxAsset}
                />
              ))}
            </div>
          </div>
        )}

        {assets.length > 1 && (
          <p className="text-[11px] text-text-muted text-right">{assets.length} dosya</p>
        )}
      </div>

      {lightboxAsset && (
        <Lightbox
          asset={lightboxAsset}
          accessToken={accessToken}
          onClose={() => setLightboxAsset(null)}
        />
      )}
    </>
  );
}
