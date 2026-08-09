"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FileText, Film, MessageSquare, Paperclip, X } from "lucide-react";
import {
  commentApi,
  mentionApi,
  type AssetRead,
  type CommentRead,
  type CommentVisibility,
  type MentionCandidate,
  type ThreadRead,
} from "@/lib/api-client";
import { useAuthBlob, mediaType } from "@/components/media/MediaPreview";
import PremiumCommentComposer from "@/components/comments/PremiumCommentComposer";
import { MentionAwareBody } from "@/components/mentions/MentionAwareBody";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("tr-TR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function VisibilityBadge({ v }: { v: CommentVisibility }) {
  if (v === "internal") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-700 text-[10px] font-medium">
        <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
        </svg>
        Dahili
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-700 text-[10px] font-medium">
      <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
        <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
      </svg>
      Müşteri
    </span>
  );
}

// ── Attachment display ────────────────────────────────────────────────────────

function AttachmentDisplay({
  asset,
  accessToken,
  onLightbox,
}: {
  asset: AssetRead;
  accessToken: string;
  onLightbox?: (url: string, mime: string) => void;
}) {
  const type = mediaType(asset.mime_type);
  const { blobUrl } = useAuthBlob(asset.id, accessToken, type === "image");

  if (type === "image") {
    return (
      <button
        type="button"
        onClick={() => blobUrl && onLightbox?.(blobUrl, asset.mime_type)}
        className="relative group w-20 h-20 rounded-lg border border-border overflow-hidden bg-surface-2 flex-shrink-0"
        title={asset.original_filename}
      >
        {blobUrl ? (
          <img src={blobUrl} alt={asset.original_filename} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full animate-pulse bg-surface-2" />
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
          <svg className="w-5 h-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
          </svg>
        </div>
        <p className="absolute bottom-0 inset-x-0 bg-black/50 text-white text-[9px] px-1 py-0.5 truncate">
          {asset.original_filename}
        </p>
      </button>
    );
  }

  if (type === "video") {
    return (
      <div className="flex items-center gap-2 bg-surface-2 border border-border rounded-lg px-3 py-2" title={asset.original_filename}>
        <Film className="w-4 h-4 text-purple-500 flex-shrink-0" />
        <span className="text-xs text-text truncate max-w-[160px]">{asset.original_filename}</span>
      </div>
    );
  }

  if (type === "pdf") {
    return (
      <div className="flex items-center gap-2 bg-surface-2 border border-border rounded-lg px-3 py-2" title={asset.original_filename}>
        <FileText className="w-4 h-4 text-red-500 flex-shrink-0" />
        <span className="text-xs text-text truncate max-w-[160px]">{asset.original_filename}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 bg-surface-2 border border-border rounded-lg px-3 py-2" title={asset.original_filename}>
      <Paperclip className="w-4 h-4 text-text-muted flex-shrink-0" />
      <span className="text-xs text-text truncate max-w-[160px]">{asset.original_filename}</span>
    </div>
  );
}

// ── Lightbox ──────────────────────────────────────────────────────────────────

function ImageLightbox({ url, onClose }: { url: string; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors"
      >
        <X className="w-5 h-5" />
      </button>
      <img
        src={url}
        alt="Önizleme"
        className="max-w-full max-h-full rounded-xl shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

// ── Comment bubble ────────────────────────────────────────────────────────────

function CommentBubble({
  comment,
  accessToken,
  onDelete,
  currentUserId,
}: {
  comment: CommentRead;
  accessToken: string;
  onDelete: (id: string) => void;
  currentUserId?: string | null;
}) {
  const isOwn = comment.author_user_id === currentUserId;
  const authorLabel =
    comment.author_name ??
    (comment.author_user_id ? `Kullanıcı ${comment.author_user_id.slice(0, 6)}` : "Anonim");
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  const images = (comment.attachments ?? []).filter((a) => mediaType(a.mime_type) === "image");
  const others = (comment.attachments ?? []).filter((a) => mediaType(a.mime_type) !== "image");

  return (
    <div className="group flex gap-2.5 py-2.5">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center text-accent text-xs font-bold">
        {authorLabel[0]?.toUpperCase() ?? "?"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="text-xs font-semibold text-text">{authorLabel}</span>
          {comment.author_job_title && (
            <span className="text-[10px] text-text-muted/70 bg-surface-2 px-1.5 py-0.5 rounded border border-border">
              {comment.author_job_title}
            </span>
          )}
          <VisibilityBadge v={comment.visibility as CommentVisibility} />
          <span className="text-[10px] text-text-muted ml-auto">{formatDate(comment.created_at)}</span>
        </div>
        <MentionAwareBody
          html={comment.body}
          mentions={comment.mentions ?? []}
          className="text-sm text-text leading-relaxed bg-surface-2 rounded-lg px-3 py-2 mt-1 [&_b]:font-semibold [&_strong]:font-semibold [&_i]:italic [&_em]:italic [&_u]:underline [&_ul]:list-disc [&_ul]:ml-4 [&_ol]:list-decimal [&_ol]:ml-4 [&_a]:text-accent [&_a]:underline [&_p]:mb-1 last:[&_p]:mb-0"
        />

        {/* Image attachments */}
        {images.length > 0 && (
          <div className="flex items-start gap-2 mt-2 flex-wrap">
            {images.map((a) => (
              <AttachmentDisplay
                key={a.id}
                asset={a}
                accessToken={accessToken}
                onLightbox={(url) => setLightboxUrl(url)}
              />
            ))}
          </div>
        )}

        {/* Non-image attachments */}
        {others.length > 0 && (
          <div className="flex flex-col gap-1 mt-2">
            {others.map((a) => (
              <AttachmentDisplay key={a.id} asset={a} accessToken={accessToken} />
            ))}
          </div>
        )}
      </div>
      {isOwn && (
        <button
          onClick={() => onDelete(comment.id)}
          className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-text-muted hover:text-red-500"
          title="Yorumu sil"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      )}
      {lightboxUrl && <ImageLightbox url={lightboxUrl} onClose={() => setLightboxUrl(null)} />}
    </div>
  );
}

// ── Thread card ───────────────────────────────────────────────────────────────

interface ThreadCardProps {
  thread: ThreadRead;
  agencyId: string;
  accessToken: string;
  currentUserId?: string | null;
  onRefresh: () => void;
  onUploadAttachment?: (file: File) => Promise<AssetRead>;
}

function ThreadCard({ thread, agencyId, accessToken, currentUserId, onRefresh, onUploadAttachment }: ThreadCardProps) {
  const [expanded, setExpanded] = useState(true);
  const [showReply, setShowReply] = useState(false);

  const handleAddComment = async (
    body: string,
    visibility: "internal" | "client_visible",
    _commentType: string,
    attachmentIds: string[],
    mentionedUserIds: string[]
  ) => {
    await commentApi.addComment(
      thread.id,
      {
        body,
        visibility,
        attachment_ids: attachmentIds.length ? attachmentIds : undefined,
        mentioned_user_ids: mentionedUserIds,
      },
      agencyId,
      accessToken
    );
    onRefresh();
  };

  const fetchMentionCandidates = async (query: string): Promise<MentionCandidate[]> => {
    const res = await mentionApi.agencyCandidates("comment", query, agencyId, accessToken);
    return res.items;
  };

  const handleDelete = async (commentId: string) => {
    try {
      await commentApi.deleteComment(thread.id, commentId, agencyId, accessToken);
      onRefresh();
    } catch {
      /* silent */
    }
  };

  const handleResolveToggle = async () => {
    try {
      if (thread.status === "open") {
        await commentApi.resolveThread(thread.id, agencyId, accessToken);
      } else {
        await commentApi.reopenThread(thread.id, agencyId, accessToken);
      }
      onRefresh();
    } catch {
      /* silent */
    }
  };

  const isResolved = thread.status === "resolved";

  return (
    <div className={`rounded-xl border transition-colors ${isResolved ? "border-border bg-surface-2/50 opacity-75" : "border-border bg-surface"}`}>
      {/* Thread header */}
      <div className="flex items-center gap-2 px-4 py-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex-1 flex items-center gap-2 text-left min-w-0"
        >
          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isResolved ? "bg-emerald-400" : "bg-blue-400"}`} />
          <span className="text-xs font-medium text-text truncate">
            {thread.comments[0]?.body.replace(/<[^>]*>/g, "").slice(0, 60) ?? "Yorum yok"}
            {(thread.comments[0]?.body.replace(/<[^>]*>/g, "").length ?? 0) > 60 && "…"}
          </span>
          <span className="text-[10px] text-text-muted flex-shrink-0">
            ({thread.comments.length})
          </span>
          <svg
            className={`w-3.5 h-3.5 text-text-muted flex-shrink-0 transition-transform ml-auto ${expanded ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <button
          onClick={handleResolveToggle}
          className={`flex-shrink-0 text-[10px] px-2 py-1 rounded border transition-colors ${
            isResolved
              ? "border-border text-text-muted hover:text-blue-600 hover:border-blue-300"
              : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
          }`}
        >
          {isResolved ? "Yeniden Aç" : "Çözüldü"}
        </button>
      </div>

      {/* Comments + reply */}
      {expanded && (
        <div className="px-4 pb-3 border-t border-border divide-y divide-border/50">
          {thread.comments.map((c) => (
            <CommentBubble
              key={c.id}
              comment={c}
              accessToken={accessToken}
              onDelete={handleDelete}
              currentUserId={currentUserId}
            />
          ))}

          {!isResolved && (
            <div className="pt-3">
              {showReply ? (
                <PremiumCommentComposer
                  onSubmit={async (body, visibility, type, ids, mentionedUserIds) => {
                    await handleAddComment(body, visibility, type, ids, mentionedUserIds);
                    setShowReply(false);
                  }}
                  onUploadAttachment={onUploadAttachment}
                  accessToken={accessToken}
                  placeholder="Yanıt yaz…"
                  showTypeSelector={false}
                  defaultVisibility="internal"
                  mentionCandidatesFetcher={fetchMentionCandidates}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setShowReply(true)}
                  className="text-xs text-text-muted hover:text-accent transition-colors flex items-center gap-1.5 py-1"
                >
                  <MessageSquare className="w-3 h-3" />
                  Cevapla
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface CommentPanelProps {
  briefId: string;
  agencyId: string;
  accessToken: string;
  currentUserId?: string | null;
  onUploadAttachment?: (file: File) => Promise<AssetRead>;
  onThreadsLoaded?: (threads: ThreadRead[]) => void;
}

export function CommentPanel({ briefId, agencyId, accessToken, currentUserId, onUploadAttachment, onThreadsLoaded }: CommentPanelProps) {
  const [threads, setThreads] = useState<ThreadRead[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await commentApi.listThreads(briefId, agencyId, accessToken);
      setThreads(data);
      onThreadsLoaded?.(data);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [briefId, agencyId, accessToken, onThreadsLoaded]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreateThread = async (
    body: string,
    visibility: "internal" | "client_visible",
    _commentType: string,
    attachmentIds: string[],
    mentionedUserIds: string[]
  ) => {
    await commentApi.createThread(
      briefId,
      {
        thread_type: "brief",
        initial_comment: body,
        visibility,
        attachment_ids: attachmentIds.length ? attachmentIds : undefined,
        mentioned_user_ids: mentionedUserIds,
      },
      agencyId,
      accessToken
    );
    await load(); // load() calls onThreadsLoaded internally
  };

  const fetchMentionCandidates = async (query: string): Promise<MentionCandidate[]> => {
    const res = await mentionApi.agencyCandidates("comment", query, agencyId, accessToken);
    return res.items;
  };

  const openThreads = threads.filter((t) => t.status === "open");
  const resolvedThreads = threads.filter((t) => t.status === "resolved");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">
          Yorumlar
          {threads.length > 0 && (
            <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-accent/10 text-accent text-[10px] font-bold">
              {threads.length}
            </span>
          )}
        </h3>
      </div>

      {/* New thread composer */}
      <PremiumCommentComposer
        onSubmit={handleCreateThread}
        onUploadAttachment={onUploadAttachment}
        accessToken={accessToken}
        placeholder="Yeni yorum, revize notu veya not ekle…"
        showTypeSelector
        defaultVisibility="internal"
        mentionCandidatesFetcher={fetchMentionCandidates}
      />

      {/* Loading */}
      {loading && (
        <div className="space-y-2 animate-pulse">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 bg-surface-2 rounded-xl" />
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && threads.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-surface/50 py-8 text-center">
          <p className="text-sm text-text-muted">Henüz yorum yok.</p>
          <p className="text-xs text-text-muted mt-1">İlk yorumu eklemek için yukarıdaki kutuyu kullanın.</p>
        </div>
      )}

      {/* Open threads */}
      {openThreads.length > 0 && (
        <div className="space-y-2">
          {openThreads.map((t) => (
            <ThreadCard
              key={t.id}
              thread={t}
              agencyId={agencyId}
              accessToken={accessToken}
              currentUserId={currentUserId}
              onRefresh={load}
              onUploadAttachment={onUploadAttachment}
            />
          ))}
        </div>
      )}

      {/* Resolved threads */}
      {resolvedThreads.length > 0 && (
        <details className="group">
          <summary className="list-none flex items-center gap-2 cursor-pointer select-none text-xs text-text-muted hover:text-text transition-colors py-1">
            <svg className="w-3.5 h-3.5 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            Çözülmüş ({resolvedThreads.length})
          </summary>
          <div className="space-y-2 mt-2">
            {resolvedThreads.map((t) => (
              <ThreadCard
                key={t.id}
                thread={t}
                agencyId={agencyId}
                accessToken={accessToken}
                currentUserId={currentUserId}
                onRefresh={load}
                onUploadAttachment={onUploadAttachment}
              />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
