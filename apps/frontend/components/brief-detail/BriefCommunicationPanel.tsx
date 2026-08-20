"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { cn } from "@/lib/utils";
import type { BrandCommentRead, BrandTimelineEntry } from "@/lib/api-client";
import { Tabs } from "@/components/ui/tabs";
import { MessageSquare, Clock, Send, Loader2 } from "lucide-react";
import { fmtRelative, COMMENT_TYPE_CFG, TIMELINE_CFG } from "./shared";
import { useLocale } from "@/context/locale-context";

type CommentType = "general" | "revision_note" | "approval_note";

function CommentItem({ comment, highlighted, itemRef }: { comment: BrandCommentRead; highlighted: boolean; itemRef?: RefObject<HTMLDivElement> }) {
  const { t } = useLocale();
  const cfg = COMMENT_TYPE_CFG[comment.comment_type] ?? COMMENT_TYPE_CFG.general;
  const initials = (comment.author_name ?? "?").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div
      ref={itemRef}
      className={cn(
        "rounded-xl border p-3.5 transition-shadow",
        cfg.bg,
        cfg.border,
        highlighted && "ring-2 ring-accent ring-offset-2 ring-offset-surface"
      )}
    >
      <div className="flex items-start gap-2.5">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0"
          style={{ background: "var(--gradient-accent)" }}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-text">{comment.author_name ?? t("briefs.comments.user")}</span>
            <span className={cn("w-1.5 h-1.5 rounded-full", cfg.dot)} />
            <span className="text-[11px] text-text-muted">{cfg.label}</span>
            <span className="text-[11px] text-text-muted ml-auto flex-shrink-0">{fmtRelative(comment.created_at)}</span>
          </div>
          <p className="text-[13px] text-text leading-relaxed">{comment.body}</p>
        </div>
      </div>
    </div>
  );
}

function TimelineItem({ entry, isLast }: { entry: BrandTimelineEntry; isLast: boolean }) {
  const tc = TIMELINE_CFG[entry.color] ?? TIMELINE_CFG.muted;

  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className={cn("w-2.5 h-2.5 rounded-full ring-4 flex-shrink-0 mt-0.5", tc.color, tc.ring)} />
        {!isLast && <div className="w-px flex-1 bg-border mt-1.5" />}
      </div>
      <div className="pb-4 flex-1 min-w-0">
        <p className="text-xs font-medium text-text">{entry.label}</p>
        {entry.actor && <p className="text-[11px] text-text-muted mt-0.5">{entry.actor}</p>}
        {entry.note && (
          <p className="text-[11px] text-text-muted mt-1 italic line-clamp-2">&quot;{entry.note}&quot;</p>
        )}
        <p className="text-[11px] text-text-muted/60 mt-1">{fmtRelative(entry.timestamp)}</p>
      </div>
    </div>
  );
}

interface BriefCommunicationPanelProps {
  comments: BrandCommentRead[];
  timeline: BrandTimelineEntry[];
  commentBody: string;
  setCommentBody: (v: string) => void;
  commentType: CommentType;
  setCommentType: (t: CommentType) => void;
  commentSubmitting: boolean;
  commentError: string | null;
  onSubmitComment: () => void;
  commentsEndRef: RefObject<HTMLDivElement>;
  highlightCommentId?: string | null;
}

export function BriefCommunicationPanel({
  comments,
  timeline,
  commentBody,
  setCommentBody,
  commentType,
  setCommentType,
  commentSubmitting,
  commentError,
  onSubmitComment,
  commentsEndRef,
  highlightCommentId,
}: BriefCommunicationPanelProps) {
  const { t } = useLocale();
  const [tab, setTab] = useState<"comments" | "activity">("comments");
  const highlightedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!highlightCommentId) return;
    setTab("comments");
    highlightedRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightCommentId]);

  return (
    <div className="bg-surface border border-border rounded-2xl overflow-hidden flex flex-col max-h-[calc(100vh-7rem)]">
      <Tabs
        items={[
          { value: "comments", label: t("briefs.comments.title"), count: comments.length },
          { value: "activity", label: t("briefs.activity.title") },
        ]}
        value={tab}
        onChange={(v) => setTab(v as "comments" | "activity")}
        className="px-3 pt-1 flex-shrink-0"
      />

      {tab === "comments" ? (
        <>
          <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
            {comments.length === 0 ? (
              <div className="py-10 text-center">
                <MessageSquare className="w-6 h-6 text-text-muted/30 mx-auto mb-2" />
                <p className="text-xs text-text-muted">{t("briefs.comments.emptyFirst")}</p>
              </div>
            ) : (
              <>
                {comments.map((c) => (
                  <CommentItem
                    key={c.id}
                    comment={c}
                    highlighted={c.id === highlightCommentId}
                    itemRef={c.id === highlightCommentId ? highlightedRef : undefined}
                  />
                ))}
                <div ref={commentsEndRef} />
              </>
            )}
          </div>

          <div className="border-t border-border p-3 space-y-2 flex-shrink-0">
            <div className="flex gap-1 bg-surface-2 p-1 rounded-lg">
              {(["general", "revision_note", "approval_note"] as CommentType[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setCommentType(t)}
                  className={cn(
                    "flex-1 py-1 text-[11px] font-medium rounded-md transition-colors",
                    commentType === t ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"
                  )}
                >
                  {COMMENT_TYPE_CFG[t].label}
                </button>
              ))}
            </div>
            <textarea
              rows={3}
              placeholder={t("briefs.comments.placeholder")}
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-lg text-xs text-text placeholder:text-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/15 focus:border-accent/60 resize-none transition-all"
            />
            {commentError && <p className="text-xs text-danger">{commentError}</p>}
            <button
              onClick={onSubmitComment}
              disabled={commentSubmitting || !commentBody.trim()}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gradient-accent text-white text-xs font-medium hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {commentSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              {t("briefs.actions.send")}
            </button>
          </div>
        </>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto p-4">
          {timeline.length === 0 ? (
            <div className="py-10 text-center">
              <Clock className="w-6 h-6 text-text-muted/30 mx-auto mb-2" />
              <p className="text-xs text-text-muted">{t("briefs.activity.empty")}</p>
            </div>
          ) : (
            timeline.map((entry, idx) => (
              <TimelineItem key={entry.id} entry={entry} isLast={idx === timeline.length - 1} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
