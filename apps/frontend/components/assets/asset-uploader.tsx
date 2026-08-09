"use client";

import { useCallback, useRef, useState } from "react";
import { assetApi, type AssetRead } from "@/lib/api-client";

const ALLOWED_TYPES = [
  "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-powerpoint",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/zip",
  "video/mp4", "video/webm",
  "audio/mpeg", "audio/wav",
];

const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

function validateFile(file: File): string | null {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return `Desteklenmeyen dosya türü: ${file.type}`;
  }
  if (file.size > MAX_SIZE_BYTES) {
    return `Dosya çok büyük: ${(file.size / 1024 / 1024).toFixed(1)} MB (max 10 MB)`;
  }
  return null;
}

interface AssetUploaderProps {
  briefId: string;
  agencyId: string;
  accessToken: string;
  onUploaded: (asset: AssetRead) => void;
}

export function AssetUploader({ briefId, agencyId, accessToken, onUploaded }: AssetUploaderProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = useCallback(
    async (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }

      setError(null);
      setUploading(true);
      try {
        const asset = await assetApi.upload(briefId, file, agencyId, accessToken);
        onUploaded(asset);
      } catch (e: unknown) {
        const err = e as { message?: string };
        setError(err?.message ?? "Yükleme başarısız.");
      } finally {
        setUploading(false);
      }
    },
    [briefId, agencyId, accessToken, onUploaded]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) upload(file);
    },
    [upload]
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      upload(file);
      e.target.value = "";
    }
  };

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        className={`relative cursor-pointer rounded-xl border-2 border-dashed transition-all px-6 py-8 text-center
          ${dragging ? "border-accent bg-accent/5 scale-[1.01]" : "border-border hover:border-accent/60 hover:bg-surface-2"}
          ${uploading ? "pointer-events-none opacity-60" : ""}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={ALLOWED_TYPES.join(",")}
          onChange={handleFileChange}
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <svg className="animate-spin w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            <p className="text-sm text-text-muted font-medium">Yükleniyor…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${dragging ? "bg-accent/15" : "bg-surface-2"}`}>
              <svg className={`w-5 h-5 transition-colors ${dragging ? "text-accent" : "text-text-muted"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-text">
                {dragging ? "Bırak!" : "Dosya yükle"}
              </p>
              <p className="text-xs text-text-muted mt-0.5">
                Sürükle & bırak veya tıkla · Max 10 MB
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-red-50 border border-red-200">
          <svg className="w-3.5 h-3.5 text-red-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <p className="text-xs text-red-700">{error}</p>
        </div>
      )}
    </div>
  );
}
