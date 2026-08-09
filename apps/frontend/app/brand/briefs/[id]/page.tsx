"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import {
  brandPortalApi,
  type BriefRead,
  type BrandCommentRead,
  type BrandTimelineEntry,
  type AssetRead,
  type BrandDeliverableRead,
} from "@/lib/api-client";
import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import RichTextEditor from "@/components/forms/RichTextEditor";
import { AlertCircle, FileText } from "lucide-react";
import { BriefDetailHeader } from "@/components/brief-detail/BriefDetailHeader";
import { DeliverableWorkspace } from "@/components/brief-detail/DeliverableWorkspace";
import { BriefCommunicationPanel } from "@/components/brief-detail/BriefCommunicationPanel";
import { BriefAttachmentsSection } from "@/components/brief-detail/BriefAttachmentsSection";
import { isOverdue } from "@/components/brief-detail/shared";

type CommentType = "general" | "revision_note" | "approval_note";

// ── Skeleton ──────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="border-b border-border bg-surface/30 px-8 py-6">
        <div className="h-3 bg-surface-2 rounded w-32 mb-5" />
        <div className="h-7 bg-surface-2 rounded w-2/3 mb-3" />
        <div className="flex gap-2">
          <div className="h-6 bg-surface-2 rounded-full w-28" />
          <div className="h-6 bg-surface-2 rounded-full w-20" />
        </div>
      </div>
      <div className="max-w-[1560px] mx-auto px-8 py-6">
        <div className="grid gap-6" style={{ gridTemplateColumns: "minmax(0, 1fr) 340px" }}>
          <div className="space-y-4">
            <div className="h-32 bg-surface-2 rounded-2xl" />
            <div className="h-96 bg-surface-2 rounded-2xl" />
          </div>
          <div className="space-y-4">
            <div className="h-96 bg-surface-2 rounded-2xl" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function BrandBriefDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const searchParams = useSearchParams();
  const deepLinkDeliverableId = searchParams.get("deliverable");
  const deepLinkAnnotationId = searchParams.get("annotation");
  const deepLinkCommentId = searchParams.get("comment");

  const [brief, setBrief] = useState<BriefRead | null>(null);
  const [comments, setComments] = useState<BrandCommentRead[]>([]);
  const [timeline, setTimeline] = useState<BrandTimelineEntry[]>([]);
  const [assets, setAssets] = useState<AssetRead[]>([]);
  const [deliverables, setDeliverables] = useState<BrandDeliverableRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Comment form
  const [commentBody, setCommentBody] = useState("");
  const [commentType, setCommentType] = useState<CommentType>("general");
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);

  // Approve flow
  const [showApprovePanel, setShowApprovePanel] = useState(false);
  const [approveNote, setApproveNote] = useState("");
  const [approveSubmitting, setApproveSubmitting] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  // Revise flow
  const [showRevisePanel, setShowRevisePanel] = useState(false);
  const [reviseReason, setReviseReason] = useState("");
  const [reviseSubmitting, setReviseSubmitting] = useState(false);
  const [reviseError, setReviseError] = useState<string | null>(null);

  // Reject flow
  const [showRejectPanel, setShowRejectPanel] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectSubmitting, setRejectSubmitting] = useState(false);
  const [rejectError, setRejectError] = useState<string | null>(null);

  const commentsEndRef = useRef<HTMLDivElement>(null);

  const loadAll = useCallback(async () => {
    if (!accessToken || !id) return;
    try {
      const [briefData, commentsData, timelineData, assetsData, delivList] = await Promise.all([
        brandPortalApi.getBrief(id, accessToken),
        brandPortalApi.listBriefComments(id, accessToken),
        brandPortalApi.getBriefTimeline(id, accessToken),
        brandPortalApi.listBriefAssets(id, accessToken).catch(() => [] as AssetRead[]),
        brandPortalApi.listDeliverables(id, accessToken).catch(() => [] as BrandDeliverableRead[]),
      ]);
      setBrief(briefData);
      setComments(commentsData);
      setTimeline(timelineData);
      setAssets(assetsData);
      setDeliverables(delivList);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [accessToken, id]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleComment = async () => {
    if (!accessToken || !id || !commentBody.trim()) return;
    setCommentSubmitting(true);
    setCommentError(null);
    try {
      const newComment = await brandPortalApi.addBriefComment(id, commentBody.trim(), commentType, accessToken);
      setComments((prev) => [...prev, newComment]);
      setCommentBody("");
      setCommentType("general");
      setTimeout(() => commentsEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (err: unknown) {
      setCommentError(err instanceof Error ? err.message : "Yorum gönderilemedi.");
    } finally {
      setCommentSubmitting(false);
    }
  };

  const handleApprove = async () => {
    if (!accessToken || !id) return;
    setApproveSubmitting(true);
    setApproveError(null);
    try {
      const updated = await brandPortalApi.approveBrief(id, approveNote.trim() || null, accessToken);
      setBrief(updated);
      setShowApprovePanel(false);
      setApproveNote("");
      const [newComments, newTimeline] = await Promise.all([
        brandPortalApi.listBriefComments(id, accessToken),
        brandPortalApi.getBriefTimeline(id, accessToken),
      ]);
      setComments(newComments);
      setTimeline(newTimeline);
    } catch (err: unknown) {
      setApproveError(err instanceof Error ? err.message : "Onay gönderilemedi.");
    } finally {
      setApproveSubmitting(false);
    }
  };

  const handleRevise = async () => {
    if (!accessToken || !id || !reviseReason.trim()) return;
    setReviseSubmitting(true);
    setReviseError(null);
    try {
      const updated = await brandPortalApi.requestRevision(id, reviseReason.trim(), accessToken);
      setBrief(updated);
      setShowRevisePanel(false);
      setReviseReason("");
      const [newComments, newTimeline] = await Promise.all([
        brandPortalApi.listBriefComments(id, accessToken),
        brandPortalApi.getBriefTimeline(id, accessToken),
      ]);
      setComments(newComments);
      setTimeline(newTimeline);
    } catch (err: unknown) {
      setReviseError(err instanceof Error ? err.message : "Revizyon talebi gönderilemedi.");
    } finally {
      setReviseSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!accessToken || !id || !rejectReason.trim()) return;
    setRejectSubmitting(true);
    setRejectError(null);
    try {
      const updated = await brandPortalApi.rejectBrief(id, rejectReason.trim(), accessToken);
      setBrief(updated);
      setShowRejectPanel(false);
      setRejectReason("");
      const [newComments, newTimeline] = await Promise.all([
        brandPortalApi.listBriefComments(id, accessToken),
        brandPortalApi.getBriefTimeline(id, accessToken),
      ]);
      setComments(newComments);
      setTimeline(newTimeline);
    } catch (err: unknown) {
      setRejectError(err instanceof Error ? err.message : "Red işlemi gönderilemedi.");
    } finally {
      setRejectSubmitting(false);
    }
  };

  const deliverableAssetIds = useMemo(
    () => new Set(deliverables.flatMap((d) => d.assets.map((a) => a.id))),
    [deliverables]
  );

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) return <PageSkeleton />;

  if (error || !brief) {
    return (
      <div className="p-8 flex flex-col items-center justify-center py-24 text-center">
        <div className="w-14 h-14 bg-danger/10 rounded-2xl flex items-center justify-center mb-4">
          <AlertCircle className="w-7 h-7 text-danger" />
        </div>
        <p className="text-sm font-medium text-text mb-1">Brief Bulunamadı</p>
        <p className="text-xs text-text-muted mb-5">Bu brief mevcut değil veya erişim yetkiniz yok.</p>
        <Link href="/brand/briefs" className="text-sm text-accent hover:underline">
          Listeye Dön
        </Link>
      </div>
    );
  }

  const overdue = isOverdue(brief.deadline, brief.status);
  // Brand can approve/revise on:
  // - in_review (legacy agency flow, non-brand-portal source)
  // - ready_for_review (new brand-portal flow — agency delivered work for brand review)
  const canAct =
    (brief.status === "in_review" && brief.source !== "brand_portal") ||
    brief.status === "ready_for_review";

  return (
    <div className="min-h-screen">
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm">
        <BriefDetailHeader
          brief={brief}
          overdue={overdue}
          canAct={canAct}
          approve={{
            open: showApprovePanel,
            value: approveNote,
            setValue: setApproveNote,
            submitting: approveSubmitting,
            error: approveError,
            onSubmit: handleApprove,
            onCancel: () => setShowApprovePanel(false),
          }}
          revise={{
            open: showRevisePanel,
            value: reviseReason,
            setValue: setReviseReason,
            submitting: reviseSubmitting,
            error: reviseError,
            onSubmit: handleRevise,
            onCancel: () => setShowRevisePanel(false),
          }}
          reject={{
            open: showRejectPanel,
            value: rejectReason,
            setValue: setRejectReason,
            submitting: rejectSubmitting,
            error: rejectError,
            onSubmit: handleReject,
            onCancel: () => setShowRejectPanel(false),
          }}
          onOpenApprove={() => { setShowApprovePanel(true); setShowRevisePanel(false); setShowRejectPanel(false); }}
          onOpenRevise={() => { setShowRevisePanel(true); setShowApprovePanel(false); setShowRejectPanel(false); }}
          onOpenReject={() => { setShowRejectPanel(true); setShowApprovePanel(false); setShowRevisePanel(false); }}
        />
      </div>

      <div className="max-w-[1560px] mx-auto px-6 lg:px-8 py-6">
        <div className="grid gap-5 lg:gap-6 items-start grid-cols-1 lg:[grid-template-columns:minmax(0,1fr)_340px]">
          {/* ── Main workspace ── */}
          <div className="min-w-0 space-y-5">
            {(brief.description_html || brief.description) && (
              <div className="bg-surface border border-border rounded-2xl p-5">
                <h2 className="text-[11px] font-semibold text-text-muted uppercase tracking-wide mb-2.5 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-accent" />
                  Brief Özeti
                </h2>
                {brief.description_html ? (
                  <RichTextEditor
                    value={brief.description_html}
                    readOnly
                    className="text-sm text-text-muted"
                  />
                ) : (
                  <p className="text-sm text-text-muted leading-relaxed whitespace-pre-wrap">{brief.description}</p>
                )}
              </div>
            )}

            {deliverables.length > 0 && (
              <DeliverableWorkspace
                deliverables={deliverables}
                accessToken={accessToken ?? ""}
                onUpdate={(updated) => setDeliverables((prev) => prev.map((d) => d.id === updated.id ? updated : d))}
                deepLinkDeliverableId={deepLinkDeliverableId}
                deepLinkAnnotationId={deepLinkAnnotationId}
              />
            )}

            <BriefAttachmentsSection
              assets={assets}
              excludeAssetIds={deliverableAssetIds}
              accessToken={accessToken ?? ""}
            />
          </div>

          {/* ── Communication panel ── */}
          <div className="lg:sticky lg:top-[7.5rem] self-start">
            <BriefCommunicationPanel
              comments={comments}
              timeline={timeline}
              commentBody={commentBody}
              setCommentBody={setCommentBody}
              commentType={commentType}
              setCommentType={setCommentType}
              commentSubmitting={commentSubmitting}
              commentError={commentError}
              onSubmitComment={handleComment}
              commentsEndRef={commentsEndRef}
              highlightCommentId={deepLinkCommentId}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
