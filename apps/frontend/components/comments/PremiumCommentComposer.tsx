"use client";

import { useRef, useState } from "react";
import { Lock, Globe, Send, Paperclip, X, Image as ImageIcon, FileText, Film } from "lucide-react";
import RichTextEditor from "@/components/forms/RichTextEditor";
import { cn } from "@/lib/utils";
import type { AssetRead, MentionCandidate } from "@/lib/api-client";
import { useAuthBlob, mediaType } from "@/components/media/MediaPreview";
import { useLocale } from "@/context/locale-context";

interface PremiumCommentComposerProps {
  onSubmit: (
    body: string,
    visibility: "internal" | "client_visible",
    commentType: "general" | "revision" | "approval_note",
    attachmentIds: string[],
    mentionedUserIds: string[]
  ) => Promise<void>;
  onUploadAttachment?: (file: File) => Promise<AssetRead>;
  accessToken?: string;
  placeholder?: string;
  defaultVisibility?: "internal" | "client_visible";
  showTypeSelector?: boolean;
  className?: string;
  mentionCandidatesFetcher?: (query: string) => Promise<MentionCandidate[]>;
}

function AttachmentThumb({ asset, accessToken, onRemove, removeLabel }: { asset: AssetRead; accessToken: string; onRemove: () => void; removeLabel: string }) {
  const type = mediaType(asset.mime_type);
  const { blobUrl } = useAuthBlob(asset.id, accessToken, type === "image");
  return (
    <div className="relative group flex-shrink-0">
      <div className="w-16 h-16 rounded-lg border border-border bg-surface-2 overflow-hidden flex items-center justify-center">
        {type === "image" && blobUrl ? (
          <img src={blobUrl} alt={asset.original_filename} className="w-full h-full object-cover" />
        ) : type === "video" ? (
          <Film className="w-6 h-6 text-text-muted" />
        ) : type === "pdf" ? (
          <FileText className="w-6 h-6 text-text-muted" />
        ) : (
          <Paperclip className="w-6 h-6 text-text-muted" />
        )}
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="absolute -top-1.5 -right-1.5 w-4.5 h-4.5 bg-danger text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
        title={removeLabel}
      >
        <X className="w-2.5 h-2.5" />
      </button>
      <p className="text-[9px] text-text-muted mt-0.5 truncate w-16 text-center">{asset.original_filename}</p>
    </div>
  );
}

export default function PremiumCommentComposer({
  onSubmit,
  onUploadAttachment,
  accessToken: accessTokenProp,
  placeholder,
  defaultVisibility = "internal",
  showTypeSelector = true,
  className,
  mentionCandidatesFetcher,
}: PremiumCommentComposerProps) {
  const { t } = useLocale();
  const editorPlaceholder = placeholder ?? t("briefs.comments.composerPlaceholder");
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<"internal" | "client_visible">(defaultVisibility);
  const [commentType, setCommentType] = useState<"general" | "revision" | "approval_note">("general");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [attachments, setAttachments] = useState<AssetRead[]>([]);
  const [uploading, setUploading] = useState(false);
  const [mentionedUserIds, setMentionedUserIds] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const accessToken = accessTokenProp ?? "";

  const isEmpty = !body || body.replace(/<[^>]*>/g, "").trim().length === 0;

  const handleAttach = async (file: File) => {
    if (!onUploadAttachment) return;
    setUploading(true);
    setError("");
    try {
      const asset = await onUploadAttachment(file);
      setAttachments((prev) => [...prev, asset]);
    } catch (e: unknown) {
      const msg = (e as { message?: string })?.message ?? t("briefs.error.file");
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleSubmit = async () => {
    if (isEmpty) return;
    setSubmitting(true);
    setError("");
    try {
      await onSubmit(body, visibility, commentType, attachments.map((a) => a.id), mentionedUserIds);
      setBody("");
      setAttachments([]);
      setMentionedUserIds([]);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err?.message ?? t("briefs.error.comment"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={cn("bg-surface rounded-xl border border-border overflow-hidden", className)}>
      <RichTextEditor
        value={body}
        onChange={setBody}
        placeholder={editorPlaceholder}
        minHeight={96}
        mentionCandidatesFetcher={mentionCandidatesFetcher}
        onMentionInsert={(candidate) =>
          setMentionedUserIds((prev) =>
            prev.includes(candidate.user_id) ? prev : [...prev, candidate.user_id]
          )
        }
      />

      {/* Attachment previews */}
      {attachments.length > 0 && (
        <div className="flex items-start gap-2 px-4 py-2 border-t border-border flex-wrap">
          {attachments.map((a) => (
            <AttachmentThumb
              key={a.id}
              asset={a}
              accessToken={accessToken}
              onRemove={() => removeAttachment(a.id)}
              removeLabel={t("briefs.actions.remove")}
            />
          ))}
        </div>
      )}

      {/* Footer bar */}
      <div className="flex items-center gap-3 px-4 py-3 border-t border-border bg-surface-2/40 flex-wrap">
        {/* Visibility toggle */}
        <div className="flex items-center gap-0.5 bg-surface rounded-lg border border-border p-0.5">
          <button
            type="button"
            onClick={() => setVisibility("internal")}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium transition-all",
              visibility === "internal"
                ? "bg-amber-50 border border-amber-300 text-amber-800"
                : "text-text-muted hover:text-text"
            )}
          >
            <Lock className="w-3 h-3" />
            {t("briefs.comments.internal")}
          </button>
          <button
            type="button"
            onClick={() => setVisibility("client_visible")}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium transition-all",
              visibility === "client_visible"
                ? "bg-blue-50 border border-blue-300 text-blue-800"
                : "text-text-muted hover:text-text"
            )}
          >
            <Globe className="w-3 h-3" />
            {t("briefs.comments.customerVisible")}
          </button>
        </div>

        {showTypeSelector && (
          <select
            value={commentType}
            onChange={(e) => setCommentType(e.target.value as typeof commentType)}
            className="text-[11px] border border-border rounded-lg px-2 py-1.5 bg-surface text-text-muted focus:outline-none focus:border-accent"
          >
            <option value="general">{t("briefs.comments.general")}</option>
            <option value="revision">{t("briefs.comments.revisionRequest")}</option>
            <option value="approval_note">{t("briefs.comments.approvalNote")}</option>
          </select>
        )}

        {/* File attach */}
        {onUploadAttachment && (
          <>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              title={t("briefs.actions.addFile")}
              className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-text-muted hover:text-accent border border-border hover:border-accent rounded-lg transition-colors disabled:opacity-40"
            >
              {uploading ? (
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
              ) : (
                <Paperclip className="w-3 h-3" />
              )}
              {uploading ? t("briefs.actions.uploading") : t("briefs.actions.addFile")}
            </button>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              title={t("briefs.actions.addImage")}
              className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-text-muted hover:text-accent border border-border hover:border-accent rounded-lg transition-colors disabled:opacity-40"
            >
              <ImageIcon className="w-3 h-3" />
              {t("briefs.actions.imageVideo")}
            </button>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.zip"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) { void handleAttach(f); e.target.value = ""; }
              }}
            />
          </>
        )}

        <div className="flex-1" />

        {error && <span className="text-[11px] text-danger truncate max-w-[200px]">{error}</span>}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting || isEmpty}
          className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-accent hover:bg-accent-hover rounded-lg disabled:opacity-40 transition-colors"
        >
          <Send className="w-3 h-3" />
          {submitting ? t("briefs.actions.sending") : t("briefs.actions.send")}
        </button>
      </div>
    </div>
  );
}
