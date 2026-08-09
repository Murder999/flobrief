"use client";

import { brandPortalApi, ApiError, type AssetRead } from "@/lib/api-client";
import { UploadCloud, File as FileIcon, X, Loader2, Image as ImageIcon, FileVideo, FileText } from "lucide-react";
import { useCallback, useRef, useState } from "react";

interface FileDropzoneProps {
  accessToken: string | null;
  /** Returns the brief ID to attach files to, saving a draft first if none exists yet. */
  ensureBriefId: () => Promise<string | null>;
  files: AssetRead[];
  onFilesChange: (files: AssetRead[]) => void;
  onUploadingChange?: (isUploading: boolean) => void;
}

const MAX_FILE_MB = 50;

function iconFor(mimeType: string) {
  if (mimeType.startsWith("image/")) return ImageIcon;
  if (mimeType.startsWith("video/")) return FileVideo;
  if (mimeType === "application/pdf") return FileText;
  return FileIcon;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileDropzone({
  accessToken,
  ensureBriefId,
  files,
  onFilesChange,
  onUploadingChange,
}: FileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState<{ name: string; progress: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const uploadFiles = useCallback(
    async (fileList: FileList | File[]) => {
      if (!accessToken) return;
      setError(null);
      const briefId = await ensureBriefId();
      if (!briefId) {
        setError("Dosya eklemeden önce brief kaydedilemedi.");
        return;
      }

      const toUpload = Array.from(fileList).filter((f) => {
        if (f.size > MAX_FILE_MB * 1024 * 1024) {
          setError(`${f.name} çok büyük (maksimum ${MAX_FILE_MB}MB)`);
          return false;
        }
        return true;
      });
      if (toUpload.length === 0) return;

      onUploadingChange?.(true);
      setUploading(toUpload.map((f) => ({ name: f.name, progress: 0 })));

      for (const file of toUpload) {
        try {
          const asset = await brandPortalApi.uploadBriefAsset(briefId, file, accessToken);
          onFilesChange([...files, asset]);
        } catch (err) {
          const msg = err instanceof ApiError ? err.message : "Dosya yüklenemedi";
          setError(`${file.name}: ${msg}`);
        } finally {
          setUploading((prev) => prev.filter((u) => u.name !== file.name));
        }
      }
      onUploadingChange?.(false);
    },
    [accessToken, ensureBriefId, files, onFilesChange, onUploadingChange]
  );

  const handleDelete = async (assetId: string) => {
    if (!accessToken) return;
    try {
      await brandPortalApi.deleteAsset(assetId, accessToken);
      onFilesChange(files.filter((f) => f.id !== assetId));
    } catch {
      setError("Dosya silinemedi");
    }
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-2 py-8 px-4 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
          isDragging ? "border-accent bg-accent-subtle/40" : "border-border hover:border-accent/40 hover:bg-hover"
        }`}
      >
        <UploadCloud className="w-6 h-6 text-text-muted" />
        <p className="text-sm text-text-muted">
          <span className="text-accent font-medium">Dosya seçin</span> veya buraya sürükleyin
        </p>
        <p className="text-xs text-text-muted/70">Görsel, video, PDF, doküman — maksimum {MAX_FILE_MB}MB</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => { if (e.target.files) uploadFiles(e.target.files); e.target.value = ""; }}
        />
      </div>

      {error && <p className="text-xs text-danger">{error}</p>}

      {uploading.map((u) => (
        <div key={u.name} className="flex items-center gap-3 px-3 py-2 bg-surface-2 rounded-lg">
          <Loader2 className="w-4 h-4 text-accent animate-spin flex-shrink-0" />
          <span className="text-xs text-text-muted truncate flex-1">{u.name} yükleniyor…</span>
        </div>
      ))}

      {files.length > 0 && (
        <div className="space-y-1.5">
          {files.map((f) => {
            const Icon = iconFor(f.mime_type);
            return (
              <div key={f.id} className="flex items-center gap-3 px-3 py-2 bg-surface-2 rounded-lg group">
                <Icon className="w-4 h-4 text-text-muted flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-text truncate">{f.original_filename}</p>
                  <p className="text-[10px] text-text-muted">{formatSize(f.size_bytes)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(f.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-text-muted hover:text-danger transition-all"
                  title="Kaldır"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
