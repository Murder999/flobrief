"use client";

import { cn } from "@/lib/utils";
import type { AnnotationRead, MentionCandidate } from "@/lib/api-client";
import { CheckCircle2, RotateCcw, Send, Loader2, X } from "lucide-react";
import { MentionTextArea } from "@/components/mentions/MentionTextArea";
import { MentionAwareBody } from "@/components/mentions/MentionAwareBody";

const MAX_BODY_LENGTH = 10_000;

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Annotation bodies are stored as plain text (no rich HTML authored) — escape
 * for safe use as MentionAwareBody's `html` input, preserving line breaks. */
function textToSafeHtml(text: string): string {
  if (typeof document === "undefined") return text;
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML.replace(/\n/g, "<br/>");
}

// ── New pin composer: shown in a popover anchored to the just-clicked point ──

interface NewPinComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  error: string | null;
  /** Agency-only type/visibility selectors, rendered between the textarea and the actions. */
  extraFields?: React.ReactNode;
  mentionCandidatesFetcher?: (query: string) => Promise<MentionCandidate[]>;
  onMentionInsert?: (candidate: MentionCandidate) => void;
}

export function NewPinComposer({
  value,
  onChange,
  onSave,
  onCancel,
  saving,
  error,
  extraFields,
  mentionCandidatesFetcher,
  onMentionInsert,
}: NewPinComposerProps) {
  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-text flex items-center gap-1.5">
          <span className="w-5 h-5 rounded-full bg-amber-500 text-white flex items-center justify-center text-[10px] font-bold flex-shrink-0">+</span>
          Revizyon Noktası Ekle
        </p>
        <button type="button" onClick={onCancel} className="text-text-muted hover:text-text transition-colors flex-shrink-0" aria-label="Kapat">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <MentionTextArea
        value={value}
        onChange={onChange}
        mentionCandidatesFetcher={mentionCandidatesFetcher}
        onMentionInsert={onMentionInsert}
        rows={3}
        placeholder="Bu noktadaki revizyon talebini yazın… (@ ile etiketle)"
        maxLength={MAX_BODY_LENGTH}
        autoFocus
        aria-label="Revizyon talebi"
        submitOn="mod-enter"
        onSubmitShortcut={onSave}
        className="w-full text-xs bg-surface-2 border border-border rounded-lg px-2.5 py-2 text-text placeholder:text-text-muted focus:outline-none focus:border-amber-400 resize-none"
      />
      <div className="flex items-center justify-between text-[10px] text-text-muted">
        <span>{error ? <span className="text-danger">{error}</span> : "Ctrl+Enter ile kaydet"}</span>
        <span>{value.length}/{MAX_BODY_LENGTH}</span>
      </div>

      {extraFields}

      <div className="flex gap-2 pt-0.5">
        <button
          type="button"
          onClick={onSave}
          disabled={saving || !value.trim()}
          className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold text-white bg-amber-500 hover:bg-amber-600 rounded-lg disabled:opacity-50 transition-colors"
        >
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
          {saving ? "Kaydediliyor…" : "Kaydet"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="px-2.5 py-1.5 text-[11px] border border-border text-text-muted hover:text-text rounded-lg transition-colors disabled:opacity-50"
        >
          Vazgeç
        </button>
      </div>
    </div>
  );
}

// ── Existing-marker detail popover: body, author, date, status, replies, actions ──

interface AnnotationDetailPopoverProps {
  annotation: AnnotationRead;
  fallbackAuthorLabel: string;
  statusBadge?: React.ReactNode;
  replyValue: string;
  onReplyChange: (v: string) => void;
  onReply: () => void;
  replying: boolean;
  onResolve?: () => void;
  resolving?: boolean;
  onReopen?: () => void;
  reopening?: boolean;
  mentionCandidatesFetcher?: (query: string) => Promise<MentionCandidate[]>;
  onMentionInsert?: (candidate: MentionCandidate) => void;
}

export function AnnotationDetailPopover({
  annotation,
  fallbackAuthorLabel,
  statusBadge,
  replyValue,
  onReplyChange,
  onReply,
  replying,
  onResolve,
  resolving,
  onReopen,
  reopening,
  mentionCandidatesFetcher,
  onMentionInsert,
}: AnnotationDetailPopoverProps) {
  const isResolved = annotation.status === "resolved";

  return (
    <div className="space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="w-5 h-5 rounded-full bg-warning/20 text-warning flex items-center justify-center text-[10px] font-bold flex-shrink-0">
            {annotation.label_number}
          </span>
          <span className="text-[11px] font-semibold text-text truncate">
            {annotation.created_by_name ?? fallbackAuthorLabel}
          </span>
        </div>
        <span className="flex-shrink-0 flex items-center gap-1.5">
          {statusBadge}
          {isResolved ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-success" aria-label="Çözüldü" />
          ) : null}
        </span>
      </div>

      <p className="text-[11px] text-text-muted">{fmtDateTime(annotation.created_at)}</p>

      {annotation.body && (
        <MentionAwareBody
          html={annotation.body_html || textToSafeHtml(annotation.body)}
          mentions={annotation.mentions ?? []}
          className="text-xs text-text leading-relaxed bg-surface-2 rounded-lg px-2.5 py-2 whitespace-pre-wrap"
        />
      )}

      {annotation.replies.length > 0 && (
        <div className="space-y-1.5">
          {annotation.replies.map((r) => (
            <div key={r.id} className="flex gap-2 pl-2 border-l-2 border-border">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-[10px] font-semibold text-text">{r.author_name ?? fallbackAuthorLabel}</span>
                  <span className="text-[10px] text-text-muted">{fmtDateTime(r.created_at)}</span>
                </div>
                <MentionAwareBody
                  html={r.body_html || textToSafeHtml(r.body)}
                  mentions={r.mentions ?? []}
                  className="text-xs text-text-muted leading-snug whitespace-pre-wrap"
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {isResolved ? (
        onReopen && (
          <button
            type="button"
            onClick={onReopen}
            disabled={reopening}
            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-semibold text-amber-600 border border-amber-300 rounded-lg hover:bg-amber-50 disabled:opacity-50 transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            {reopening ? "Açılıyor…" : "Yeniden Aç"}
          </button>
        )
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <MentionTextArea
              value={replyValue}
              onChange={onReplyChange}
              mentionCandidatesFetcher={mentionCandidatesFetcher}
              onMentionInsert={onMentionInsert}
              submitOn="enter"
              onSubmitShortcut={onReply}
              placeholder="Yanıtla… (@ ile etiketle)"
              aria-label={`#${annotation.label_number} numaralı revizyona yanıt yaz`}
              className="flex-1 text-[11px] bg-surface-2 border border-border rounded-lg px-2 py-1.5 text-text placeholder:text-text-muted focus:outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={onReply}
              disabled={replying || !replyValue.trim()}
              className="p-1.5 rounded-lg text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors flex-shrink-0"
              aria-label="Yanıtı gönder"
            >
              <Send className="w-3 h-3" />
            </button>
          </div>
          {onResolve && (
            <button
              type="button"
              onClick={onResolve}
              disabled={resolving}
              className={cn(
                "inline-flex items-center gap-1 text-[11px] font-semibold transition-colors",
                "text-success hover:text-success/80 disabled:opacity-50",
              )}
            >
              <CheckCircle2 className="w-3 h-3" />
              {resolving ? "İşleniyor…" : "Çözüldü Yap"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
