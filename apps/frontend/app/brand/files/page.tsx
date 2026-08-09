"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, type AssetRead } from "@/lib/api-client";
import { useEffect, useState, useCallback } from "react";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function FileIcon({ mime }: { mime: string }) {
  const isImage = mime.startsWith("image/");
  const isPdf = mime === "application/pdf";
  const isVideo = mime.startsWith("video/");
  const color = isImage ? "text-emerald-400" : isPdf ? "text-red-400" : isVideo ? "text-purple-400" : "text-blue-400";
  return (
    <div className={`w-9 h-9 rounded-lg bg-surface-2 flex items-center justify-center flex-shrink-0 ${color}`}>
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        {isImage ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        ) : isPdf ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        ) : (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
        )}
      </svg>
    </div>
  );
}

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-5 py-4 border-b border-border last:border-0 animate-pulse">
      <div className="w-9 h-9 bg-surface-2 rounded-lg flex-shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3.5 bg-surface-2 rounded w-48" />
        <div className="h-3 bg-surface-2 rounded w-32" />
      </div>
      <div className="h-3 bg-surface-2 rounded w-16" />
    </div>
  );
}

interface FileWithBrief extends AssetRead {
  brief_title: string;
  brief_id: string;
}

export default function BrandFilesPage() {
  const { accessToken } = useAuth();
  const [files, setFiles] = useState<FileWithBrief[] | null>(null);
  const [error, setError] = useState(false);

  const loadData = useCallback(async () => {
    if (!accessToken) return;
    try {
      const res = await brandPortalApi.listFiles(accessToken);
      const allFiles: FileWithBrief[] = [];
      for (const bwa of res.briefs) {
        for (const asset of bwa.assets) {
          allFiles.push({ ...asset, brief_title: bwa.brief.title, brief_id: bwa.brief.id });
        }
      }
      allFiles.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setFiles(allFiles);
    } catch {
      setError(true);
      setFiles([]);
    }
  }, [accessToken]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalSize = files?.reduce((sum, f) => sum + f.size_bytes, 0) ?? 0;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text">Dosyalar</h1>
        <p className="mt-1 text-text-muted">
          Brieflere yüklenmiş tüm dosya ve ekler.
          {files !== null && files.length > 0 && (
            <span className="ml-2 text-text">
              {files.length} dosya · {formatBytes(totalSize)}
            </span>
          )}
        </p>
      </div>

      {error ? (
        <div className="bg-surface border border-border rounded-xl p-10 text-center">
          <p className="text-sm text-danger mb-3">Dosyalar yüklenemedi.</p>
          <button onClick={loadData} className="text-xs text-accent hover:underline">
            Tekrar dene
          </button>
        </div>
      ) : files === null ? (
        <div className="bg-surface border border-border rounded-xl">
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
        </div>
      ) : files.length === 0 ? (
        <div className="bg-surface border border-border rounded-xl p-16 flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-text mb-1">Henüz dosya yok</p>
          <p className="text-xs text-text-muted max-w-sm">
            Briflere eklenen dosyalar burada görüntülenecek.
          </p>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-xl">
          {files.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-4 px-5 py-4 border-b border-border last:border-0 group"
            >
              <FileIcon mime={file.mime_type} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text truncate">{file.original_filename}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <Link
                    href={`/brand/briefs/${file.brief_id}`}
                    className="text-xs text-accent hover:underline truncate max-w-xs"
                  >
                    {file.brief_title}
                  </Link>
                  <span className="text-text-muted">·</span>
                  <span className="text-xs text-text-muted">{formatBytes(file.size_bytes)}</span>
                </div>
              </div>
              <span className="text-xs text-text-muted flex-shrink-0">{formatDate(file.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
