"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  brandPortalApi,
  brandAnnotationApi,
  brandPreviewApi,
  mentionApi,
  ApiError,
  type BrandDeliverableRead,
  type AnnotationRead,
  type AnnotationCreate,
  type MentionCandidate,
  type PreviewConfigRead,
  type PreviewSlotRead,
} from "@/lib/api-client";
import AnnotationCanvas from "@/components/media/AnnotationCanvas";
import { NewPinComposer, AnnotationDetailPopover } from "@/components/media/AnnotationPopoverContent";
import { useAuthBlob, mediaType, downloadWithAuth, Lightbox } from "@/components/media/MediaPreview";
import { PlatformPreviewShell } from "@/components/preview/PlatformPreviewShell";
import { PreviewValidationPanel } from "@/components/preview/PreviewValidationPanel";
import {
  CheckCircle,
  RotateCcw,
  AlertCircle,
  Package2,
  Loader2,
  FileText,
  ImageIcon,
  Smartphone,
  Eye,
  EyeOff,
} from "lucide-react";
import { DeliverableToolbar } from "./DeliverableToolbar";
import { DeliverableVersionStrip } from "./DeliverableVersionStrip";
import { fmtDate, DELIVERABLE_STATUS_CFG, DELIVERABLE_TYPE_LABEL } from "./shared";
import { useBreakpoint } from "@/hooks/useBreakpoint";
import { useToast } from "@/components/ui/toast";
import { useLocale } from "@/context/locale-context";

// ── Non-image / non-video fallback for the main preview area ────────────────

function MainAssetFallback({
  assetId,
  filename,
  sizeBytes,
  accessToken,
}: {
  assetId: string;
  filename: string;
  sizeBytes: number | null;
  accessToken: string;
}) {
  const { t } = useLocale();
  return (
    <button
      type="button"
      onClick={() => downloadWithAuth(assetId, filename, accessToken)}
      className="w-full min-h-[420px] flex flex-col items-center justify-center gap-3 bg-surface-2 hover:bg-hover transition-colors"
      title={t("briefs.deliverable.clickToDownload")}
    >
      <div className="w-14 h-14 rounded-xl bg-surface flex items-center justify-center border border-border">
        <FileText className="w-6 h-6 text-text-muted" />
      </div>
      <div className="text-center">
        <p className="text-sm text-text font-medium">{filename}</p>
        {sizeBytes != null && <p className="text-xs text-text-muted mt-0.5">{t("briefs.deliverable.sizeDownload", { size: (sizeBytes / 1024).toFixed(1) })}</p>}
      </div>
    </button>
  );
}

// ── Single deliverable's preview + annotation + approve/revise pane ─────────

interface DeliverablePreviewPaneProps {
  d: BrandDeliverableRead;
  accessToken: string;
  onUpdate: (d: BrandDeliverableRead) => void;
  onOpenCountChange: (count: number) => void;
  deepLinkAnnotationId?: string | null;
  /** Backend-computed (see app/services/deliverable_versioning.py): false
   * only when another deliverable in this brief shares this one's title and
   * was submitted more recently — i.e. this row was actually superseded,
   * not merely older by creation order. Independent deliverables (distinct
   * titles) are always true. False opens the platform preview read-only. */
  isLatestVersion?: boolean;
}

function DeliverablePreviewPane({ d, accessToken, onUpdate, onOpenCountChange, deepLinkAnnotationId, isLatestVersion = true }: DeliverablePreviewPaneProps) {
  const { t } = useLocale();
  const [annotations, setAnnotations] = useState<AnnotationRead[]>([]);
  const [loadingAnns, setLoadingAnns] = useState(true);
  const [selectedAssetIndex, setSelectedAssetIndex] = useState(0);
  const [annotationMode, setAnnotationMode] = useState(false);
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | null>(null);
  const [pulseAnnotationId, setPulseAnnotationId] = useState<string | null>(null);
  const [newPinData, setNewPinData] = useState<{ x: number; y: number } | null>(null);
  const [newPinBody, setNewPinBody] = useState("");
  const [newPinMentionedIds, setNewPinMentionedIds] = useState<string[]>([]);
  const [savingPin, setSavingPin] = useState(false);
  const [pinError, setPinError] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState<Record<string, string>>({});
  const [replyMentionedIds, setReplyMentionedIds] = useState<Record<string, string[]>>({});
  const [replyingId, setReplyingId] = useState<string | null>(null);
  const [reopeningId, setReopeningId] = useState<string | null>(null);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const sceneRef = useRef<HTMLDivElement>(null);
  const revisionPanelRef = useRef<HTMLDivElement>(null);
  const { isMobile } = useBreakpoint();
  const { confirm } = useToast();

  const [approving, setApproving] = useState(false);
  const [revising, setRevising] = useState(false);
  const [revisionNote, setRevisionNote] = useState("");
  const [showRevision, setShowRevision] = useState(false);

  // ── Platform preview (Social Media Preview Center) — read-only for brands ──
  const [viewMode, setViewMode] = useState<"raw" | "platform">("raw");
  const [previewConfig, setPreviewConfig] = useState<PreviewConfigRead | null>(null);
  const [previewSlots, setPreviewSlots] = useState<PreviewSlotRead[]>([]);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [previewUnavailable, setPreviewUnavailable] = useState(false);
  const [platformActiveAssetId, setPlatformActiveAssetId] = useState<string | null>(null);

  useEffect(() => {
    brandAnnotationApi.list(d.id, accessToken).then((list) => {
      setAnnotations(list);
      setLoadingAnns(false);
    }).catch(() => setLoadingAnns(false));
  }, [d.id, accessToken]);

  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    setPreviewUnavailable(false);
    setPreviewConfig(null);
    setPreviewSlots([]);
    brandPreviewApi.getConfig(d.brief_id, d.id, accessToken)
      .then(async (cfg) => {
        if (cancelled) return;
        setPreviewConfig(cfg);
        const slots = await brandPreviewApi.listSlots(d.brief_id, d.id, accessToken);
        if (!cancelled) setPreviewSlots(slots);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setPreviewUnavailable(true);
        else setPreviewUnavailable(true);
      })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => { cancelled = true; };
  }, [d.id, d.brief_id, accessToken]);

  useEffect(() => {
    if (loadingAnns) return;
    onOpenCountChange(annotations.filter((a) => a.status === "open").length);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [annotations, loadingAnns]);

  // Deep-link from a notification: jump to the right asset, open its popover, pulse it.
  useEffect(() => {
    if (loadingAnns || !deepLinkAnnotationId) return;
    const target = annotations.find((a) => a.id === deepLinkAnnotationId);
    if (!target) return;
    const idx = d.assets.findIndex((a) => a.id === target.asset_id);
    if (idx >= 0) setSelectedAssetIndex(idx);
    setActiveAnnotationId(target.id);
    setPulseAnnotationId(target.id);
    sceneRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = setTimeout(() => setPulseAnnotationId(null), 2500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadingAnns, deepLinkAnnotationId]);

  const selectedAsset = d.assets[selectedAssetIndex] ?? null;
  const assetType = selectedAsset ? mediaType(selectedAsset.mime_type) : null;
  const canAct = d.status === "submitted";

  const handleAddPin = async () => {
    if (!newPinData || !newPinBody.trim()) return;
    setSavingPin(true);
    setPinError(null);
    try {
      const data: Omit<AnnotationCreate, "visibility"> = {
        asset_id: viewMode === "platform" ? platformActiveAssetId : (selectedAsset?.id ?? null),
        version_number: d.version_number,
        x_percent: newPinData.x,
        y_percent: newPinData.y,
        annotation_type: "revision",
        body: newPinBody.trim(),
        mentioned_user_ids: newPinMentionedIds,
      };
      const created = await brandAnnotationApi.create(d.id, data, accessToken);
      setAnnotations((prev) => [...prev, created]);
      setNewPinData(null);
      setNewPinBody("");
      setNewPinMentionedIds([]);
      setActiveAnnotationId(created.id);
    } catch (err: unknown) {
      setPinError(err instanceof Error ? err.message : t("briefs.error.annotationSave"));
    } finally {
      setSavingPin(false);
    }
  };

  const cancelNewPin = () => {
    setNewPinData(null);
    setNewPinBody("");
    setNewPinMentionedIds([]);
    setPinError(null);
  };

  const fetchBrandMentionCandidatesForNewAnnotation = (query: string): Promise<MentionCandidate[]> =>
    mentionApi.brandCandidates("comment", d.id, query, accessToken).then((r) => r.items);

  const fetchBrandMentionCandidatesForReply = (annotationId: string) => (query: string): Promise<MentionCandidate[]> =>
    mentionApi.brandCandidates("annotation", annotationId, query, accessToken).then((r) => r.items);

  const addNewPinMention = (candidate: MentionCandidate) =>
    setNewPinMentionedIds((prev) => (prev.includes(candidate.user_id) ? prev : [...prev, candidate.user_id]));

  const addReplyMention = (annotationId: string) => (candidate: MentionCandidate) =>
    setReplyMentionedIds((prev) => {
      const existing = prev[annotationId] ?? [];
      if (existing.includes(candidate.user_id)) return prev;
      return { ...prev, [annotationId]: [...existing, candidate.user_id] };
    });

  const handleReply = async (annotationId: string) => {
    const body = replyBody[annotationId]?.trim();
    if (!body) return;
    setReplyingId(annotationId);
    try {
      const reply = await brandAnnotationApi.reply(
        d.id,
        annotationId,
        { body, mentioned_user_ids: replyMentionedIds[annotationId] ?? [] },
        accessToken
      );
      setAnnotations((prev) => prev.map((a) => a.id === annotationId ? { ...a, replies: [...a.replies, reply] } : a));
      setReplyBody((prev) => ({ ...prev, [annotationId]: "" }));
      setReplyMentionedIds((prev) => ({ ...prev, [annotationId]: [] }));
    } finally {
      setReplyingId(null);
    }
  };

  const handleReopen = async (annotationId: string) => {
    setReopeningId(annotationId);
    try {
      const updated = await brandAnnotationApi.reopen(d.id, annotationId, accessToken);
      setAnnotations((prev) => prev.map((a) => a.id === annotationId ? updated : a));
    } finally {
      setReopeningId(null);
    }
  };

  const handleApprove = async () => {
    if (approving) return;
    const ok = await confirm({
      title: t("briefs.deliverable.confirmTitle"),
      message: t("briefs.deliverable.confirmMessage"),
      confirmLabel: t("briefs.actions.approve"),
      cancelLabel: t("briefs.actions.cancel"),
    });
    if (!ok) return;
    setApproving(true);
    try {
      const updated = await brandPortalApi.approveDeliverable(d.brief_id, d.id, null, accessToken);
      onUpdate(updated);
    } finally {
      setApproving(false);
    }
  };

  const openRevisionPanel = () => {
    setShowRevision(true);
    requestAnimationFrame(() => revisionPanelRef.current?.scrollIntoView({ block: "center", behavior: "smooth" }));
  };

  const handleRevise = async () => {
    const reason = revisionNote.trim();
    if (!reason) return;
    setRevising(true);
    try {
      const updated = await brandPortalApi.requestDeliverableRevision(d.brief_id, d.id, reason, accessToken);
      onUpdate(updated);
      setShowRevision(false);
      setRevisionNote("");
    } finally {
      setRevising(false);
    }
  };

  const visibleAnnotations = loadingAnns
    ? []
    : annotations.filter((a) => a.asset_id === selectedAsset?.id || a.asset_id === null);

  return (
    <div className={cn(isMobile && canAct && "pb-20")}>
      {(d.revision_note || d.approve_note || canAct) && (
        <div className="px-5 pt-4 space-y-2.5">
          {d.revision_note && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
              <p className="text-[11px] font-semibold text-amber-700 mb-0.5">{t("briefs.comments.revisionNote")}</p>
              <p className="text-xs text-amber-700">{d.revision_note}</p>
            </div>
          )}
          {d.approve_note && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
              <p className="text-[11px] font-semibold text-emerald-700 mb-0.5">{t("briefs.comments.approvalNote")}</p>
              <p className="text-xs text-emerald-700">{d.approve_note}</p>
            </div>
          )}
          {canAct && (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 px-4 py-2.5">
              <p className="text-xs text-text-muted">{t("briefs.deliverable.reviewHelp")}</p>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={handleApprove}
                  disabled={approving}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 text-emerald-600 text-[12px] font-semibold rounded-lg hover:bg-emerald-500/20 disabled:opacity-50 transition-colors border border-emerald-500/20"
                >
                  {approving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                  {t(approving ? "briefs.actions.approving" : "briefs.actions.approve")}
                </button>
                <button
                  onClick={() => setShowRevision((v) => !v)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500/10 text-amber-600 text-[12px] font-semibold rounded-lg hover:bg-amber-500/20 transition-colors border border-amber-500/20"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  {t("briefs.comment.revision")}
                </button>
              </div>
            </div>
          )}
          {showRevision && (
            <div ref={revisionPanelRef} className="space-y-2 pl-2 border-l-2 border-amber-500/30">
              <textarea
                value={revisionNote}
                onChange={(e) => setRevisionNote(e.target.value)}
                placeholder={t("briefs.deliverable.revisionPlaceholder")}
                rows={2}
                className="w-full px-3 py-2 text-xs bg-surface-2 border border-border rounded-lg resize-none focus:outline-none focus:border-amber-400 text-text placeholder:text-text-muted"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleRevise}
                  disabled={revising || !revisionNote.trim()}
                  className="px-3 py-1.5 text-xs font-semibold text-white bg-amber-500 hover:bg-amber-600 rounded-lg disabled:opacity-50 transition-colors"
                >
                  {t(revising ? "briefs.actions.sending" : "briefs.actions.requestRevision")}
                </button>
                <button
                  onClick={() => setShowRevision(false)}
                  className="px-3 py-1.5 text-xs text-text-muted hover:text-text border border-border rounded-lg transition-colors"
                >
                  {t("briefs.actions.cancel")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {isMobile && canAct && (
        <div
          className="lg:hidden fixed inset-x-0 z-20 bg-surface/95 backdrop-blur-md border-t border-border px-4 py-2.5 flex items-center gap-2"
          style={{ bottom: "calc(3.5rem + env(safe-area-inset-bottom, 0px))" }}
        >
          <button
            data-testid="sticky-approve-btn"
            onClick={handleApprove}
            disabled={approving}
            className="flex-1 flex items-center justify-center gap-1.5 min-h-[44px] px-3 bg-emerald-500 text-white text-[13px] font-semibold rounded-lg hover:bg-emerald-600 disabled:opacity-50 transition-colors"
          >
            {approving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
            {t(approving ? "briefs.actions.approving" : "briefs.actions.approve")}
          </button>
          <button
            data-testid="sticky-revision-btn"
            onClick={openRevisionPanel}
            className="flex-1 flex items-center justify-center gap-1.5 min-h-[44px] px-3 bg-amber-500/10 text-amber-600 text-[13px] font-semibold rounded-lg border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            {t("briefs.actions.requestRevision")}
          </button>
        </div>
      )}

      {d.assets.length > 0 && selectedAsset && (
        <div className="mt-4" ref={sceneRef}>
          {!previewLoading && !previewUnavailable && previewConfig && (
            <div className="px-5 pb-3 flex items-center gap-1.5" role="tablist" aria-label={t("briefs.deliverable.viewMode")}>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "raw"}
                onClick={() => setViewMode("raw")}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors",
                  viewMode === "raw" ? "bg-accent text-white border-accent" : "bg-surface text-text-muted border-border",
                )}
              >
                <ImageIcon className="w-3.5 h-3.5" /> {t("briefs.deliverable.raw")}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "platform"}
                onClick={() => setViewMode("platform")}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors",
                  viewMode === "platform" ? "bg-accent text-white border-accent" : "bg-surface text-text-muted border-border",
                )}
              >
                <Smartphone className="w-3.5 h-3.5" /> {t("briefs.deliverable.platformPreview")}
              </button>
            </div>
          )}

          {viewMode === "platform" && previewConfig ? (
            <div className="px-5 pb-3 space-y-3">
              {isLatestVersion && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => { setAnnotationMode((m) => !m); cancelNewPin(); }}
                    className={cn(
                      "flex items-center gap-1.5 pl-2.5 pr-3 py-1.5 text-[12.5px] font-semibold rounded-full transition-colors",
                      annotationMode
                        ? "bg-accent text-white shadow-sm"
                        : "bg-gradient-accent text-white hover:opacity-90 shadow-sm"
                    )}
                  >
                    {annotationMode ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    {t(annotationMode ? "briefs.deliverable.annotationClose" : "briefs.deliverable.annotationAdd")}
                  </button>
                </div>
              )}
              <PlatformPreviewShell
                config={previewConfig}
                slots={previewSlots}
                accessToken={accessToken}
                annotations={annotations}
                activeAnnotationId={activeAnnotationId}
                onAnnotationClick={(ann) => setActiveAnnotationId((id) => id === ann.id ? null : ann.id)}
                annotationMode={annotationMode}
                onCanvasClick={(x, y) => setNewPinData({ x, y })}
                onExitAnnotationMode={() => { setAnnotationMode(false); cancelNewPin(); }}
                newPinDraft={newPinData}
                renderNewPinComposer={() => (
                  <NewPinComposer
                    value={newPinBody}
                    onChange={setNewPinBody}
                    onSave={handleAddPin}
                    onCancel={cancelNewPin}
                    saving={savingPin}
                    error={pinError}
                    mentionCandidatesFetcher={fetchBrandMentionCandidatesForNewAnnotation}
                    onMentionInsert={addNewPinMention}
                  />
                )}
                onCloseNewPinComposer={cancelNewPin}
                renderAnnotationPopover={(ann) => (
                  <AnnotationDetailPopover
                    annotation={ann}
                    fallbackAuthorLabel={t("briefs.annotation.agency")}
                    replyValue={replyBody[ann.id] ?? ""}
                    onReplyChange={(v) => setReplyBody((prev) => ({ ...prev, [ann.id]: v }))}
                    onReply={() => handleReply(ann.id)}
                    replying={replyingId === ann.id}
                    onReopen={() => handleReopen(ann.id)}
                    reopening={reopeningId === ann.id}
                    mentionCandidatesFetcher={fetchBrandMentionCandidatesForReply(ann.id)}
                    onMentionInsert={addReplyMention(ann.id)}
                  />
                )}
                onCloseAnnotationPopover={() => setActiveAnnotationId(null)}
                onActiveAssetChange={setPlatformActiveAssetId}
                readOnly={!isLatestVersion}
              />
              <PreviewValidationPanel warnings={previewConfig.warnings} />
            </div>
          ) : (
          <>
          {d.assets.length > 1 && (
            <div className="flex gap-1.5 overflow-x-auto px-5 pb-3">
              {d.assets.map((a, idx) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setSelectedAssetIndex(idx)}
                  className={cn(
                    "flex-shrink-0 w-11 h-11 rounded-lg border-2 overflow-hidden transition-all",
                    idx === selectedAssetIndex ? "border-accent" : "border-border"
                  )}
                >
                  <AssetTabThumb assetId={a.id} mime={a.mime_type} accessToken={accessToken} />
                </button>
              ))}
            </div>
          )}

          <div className="bg-surface-2 rounded-xl mx-5 overflow-hidden border border-border/60">
            <DeliverableToolbar
              filename={selectedAsset.original_filename ?? selectedAsset.filename}
              versionNumber={d.version_number}
              uploadedAt={d.submitted_at ?? d.created_at}
              onDownload={() => downloadWithAuth(selectedAsset.id, selectedAsset.filename, accessToken)}
              onMaximize={() => setLightboxOpen(true)}
              annotationMode={annotationMode}
              onToggleAnnotationMode={() => { setAnnotationMode((m) => !m); cancelNewPin(); }}
              showAnnotationAction={assetType === "image"}
            />

            {assetType === "image" ? (
              <>
                {annotationMode && !newPinData && !activeAnnotationId && (
                  <p className="px-4 pt-2.5 text-[11px] text-accent font-medium">
                    {t("briefs.deliverable.annotationHint")}
                  </p>
                )}
                {/*
                  Explicit height (not min/max) so the child <img>'s h-full percentage
                  resolves to a real box instead of falling back to `auto` — without this,
                  object-fit: contain has nothing to constrain against and tall images get
                  silently clipped by the container's overflow.
                */}
                <div
                  className="relative w-full bg-surface-2"
                  style={{ height: "clamp(520px, 62vh, 760px)" }}
                >
                  <div className="absolute inset-0 p-4 sm:p-6">
                    <AnnotationCanvas
                      assetId={selectedAsset.id}
                      accessToken={accessToken}
                      annotations={visibleAnnotations}
                      activeAnnotationId={activeAnnotationId}
                      annotationMode={annotationMode}
                      onCanvasClick={(x, y) => setNewPinData({ x, y })}
                      onAnnotationClick={(ann) => setActiveAnnotationId((id) => id === ann.id ? null : ann.id)}
                      onExitAnnotationMode={() => { setAnnotationMode(false); cancelNewPin(); }}
                      className="w-full h-full"
                      newPinDraft={newPinData}
                      onCloseNewPinComposer={cancelNewPin}
                      renderNewPinComposer={() => (
                        <NewPinComposer
                          value={newPinBody}
                          onChange={setNewPinBody}
                          onSave={handleAddPin}
                          onCancel={cancelNewPin}
                          saving={savingPin}
                          error={pinError}
                          mentionCandidatesFetcher={fetchBrandMentionCandidatesForNewAnnotation}
                          onMentionInsert={addNewPinMention}
                        />
                      )}
                      onCloseAnnotationPopover={() => setActiveAnnotationId(null)}
                      renderAnnotationPopover={(ann) => (
                        <AnnotationDetailPopover
                          annotation={ann}
                          fallbackAuthorLabel={t("briefs.annotation.agency")}
                          replyValue={replyBody[ann.id] ?? ""}
                          onReplyChange={(v) => setReplyBody((prev) => ({ ...prev, [ann.id]: v }))}
                          onReply={() => handleReply(ann.id)}
                          replying={replyingId === ann.id}
                          onReopen={() => handleReopen(ann.id)}
                          reopening={reopeningId === ann.id}
                          mentionCandidatesFetcher={fetchBrandMentionCandidatesForReply(ann.id)}
                          onMentionInsert={addReplyMention(ann.id)}
                        />
                      )}
                      pulseAnnotationId={pulseAnnotationId}
                    />
                  </div>
                </div>
                {lightboxOpen && (
                  <Lightbox asset={selectedAsset} accessToken={accessToken} onClose={() => setLightboxOpen(false)} />
                )}
              </>
            ) : (
              <>
                <MainAssetFallback
                  assetId={selectedAsset.id}
                  filename={selectedAsset.original_filename ?? selectedAsset.filename}
                  sizeBytes={selectedAsset.size_bytes}
                  accessToken={accessToken}
                />
                {lightboxOpen && (
                  <Lightbox asset={selectedAsset} accessToken={accessToken} onClose={() => setLightboxOpen(false)} />
                )}
              </>
            )}
          </div>
          </>
          )}

          {/* Annotation list — a secondary index; the popover above is the primary detail view */}
          {!loadingAnns && annotations.length > 0 && (
            <div className="space-y-1.5 mx-5 mt-3">
              <p className="text-[11px] font-semibold text-text-muted uppercase tracking-wide px-1">{t("briefs.deliverable.annotations", { count: annotations.length })}</p>
              {annotations.map((ann) => (
                <button
                  key={ann.id}
                  type="button"
                  onClick={() => {
                    const idx = d.assets.findIndex((a) => a.id === ann.asset_id);
                    if (idx >= 0) setSelectedAssetIndex(idx);
                    setActiveAnnotationId((id) => id === ann.id ? null : ann.id);
                  }}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-lg border transition-all hover:border-accent/30",
                    ann.id === activeAnnotationId ? "border-accent/40 bg-accent/5" : "border-border bg-surface",
                    ann.status === "resolved" && "opacity-60"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-warning/20 text-warning flex items-center justify-center text-[10px] font-bold flex-shrink-0">{ann.label_number}</span>
                    <span className="text-xs text-text line-clamp-1 flex-1">{ann.body}</span>
                    {ann.status === "resolved" && <CheckCircle className="w-3 h-3 text-success flex-shrink-0" />}
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="h-4" />
        </div>
      )}
    </div>
  );
}

function AssetTabThumb({ assetId, mime, accessToken }: { assetId: string; mime: string; accessToken: string }) {
  const type = mediaType(mime);
  const { blobUrl, loading } = useAuthBlob(assetId, accessToken, type === "image" || type === "video");
  if (loading) return <div className="w-full h-full bg-surface-2 animate-pulse" />;
  if (type === "image" && blobUrl) return <img src={blobUrl} alt="" className="w-full h-full object-cover" />;
  if (type === "video" && blobUrl) return <video src={blobUrl} className="w-full h-full object-cover" muted />;
  return (
    <div className="w-full h-full flex items-center justify-center bg-surface-2">
      <FileText className="w-3.5 h-3.5 text-text-muted" />
    </div>
  );
}

// ── Workspace shell ───────────────────────────────────────────────────────────

interface DeliverableWorkspaceProps {
  deliverables: BrandDeliverableRead[];
  accessToken: string;
  onUpdate: (d: BrandDeliverableRead) => void;
  /** Deep-link from a notification: pick this deliverable/annotation once, then open+pulse it. */
  deepLinkDeliverableId?: string | null;
  deepLinkAnnotationId?: string | null;
}

export function DeliverableWorkspace({ deliverables, accessToken, onUpdate, deepLinkDeliverableId, deepLinkAnnotationId }: DeliverableWorkspaceProps) {
  const { t } = useLocale();
  const sorted = useMemo(
    () => [...deliverables].sort((a, b) => {
      const ta = new Date(a.submitted_at ?? a.created_at).getTime();
      const tb = new Date(b.submitted_at ?? b.created_at).getTime();
      return ta - tb;
    }),
    [deliverables]
  );

  const [selectedId, setSelectedId] = useState<string | null>(() => sorted[sorted.length - 1]?.id ?? null);
  const appliedDeepLinkRef = useRef(false);

  useEffect(() => {
    if (sorted.length === 0) return;
    if (!selectedId || !sorted.some((d) => d.id === selectedId)) {
      setSelectedId(sorted[sorted.length - 1].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sorted]);

  // Deep-link deliverable selection applies once (avoids fighting the user's own navigation afterwards).
  useEffect(() => {
    if (appliedDeepLinkRef.current || !deepLinkDeliverableId) return;
    if (sorted.some((d) => d.id === deepLinkDeliverableId)) {
      setSelectedId(deepLinkDeliverableId);
      appliedDeepLinkRef.current = true;
    }
  }, [sorted, deepLinkDeliverableId]);

  if (deliverables.length === 0) return null;

  const selected = sorted.find((d) => d.id === selectedId) ?? sorted[sorted.length - 1];
  const approvedCount = deliverables.filter((d) => d.status === "approved").length;
  const openCount = deliverables.reduce((sum, d) => sum + d.open_annotation_count, 0);
  const cfg = DELIVERABLE_STATUS_CFG[selected.status];

  return (
    <div data-testid="deliverable-workspace" className="bg-surface border border-border rounded-2xl overflow-hidden shadow-card">
      <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
            <Package2 className="w-4 h-4 text-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text">{t("briefs.deliverable.title")}</p>
            <p className="text-xs text-text-muted truncate">
              {t("briefs.deliverable.summary", { count: deliverables.length, version: selected.version_number, approved: approvedCount })}
              {openCount > 0 && ` · ${t("briefs.deliverable.openAnnotations", { count: openCount })}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {selected.open_annotation_count > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
              <AlertCircle className="w-3 h-3" />
              {t("briefs.deliverable.openPoints", { count: selected.open_annotation_count })}
            </span>
          )}
          {cfg && (
            <span className={cn("inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-semibold border", cfg.className)}>
              {cfg.label}
            </span>
          )}
        </div>
      </div>

      <div className="px-5 pt-3 flex items-center gap-2 text-xs text-text-muted">
        <span className="font-medium text-text">{selected.title}</span>
        <span>· {DELIVERABLE_TYPE_LABEL[selected.deliverable_type] ?? selected.deliverable_type}</span>
        {selected.revision_count > 0 && <span className="text-amber-500">· {t("briefs.deliverable.revisionCount", { count: selected.revision_count })}</span>}
        {selected.submitted_at && <span>· {fmtDate(selected.submitted_at)}</span>}
      </div>

      <DeliverablePreviewPane
        key={selected.id}
        d={selected}
        accessToken={accessToken}
        onUpdate={onUpdate}
        onOpenCountChange={(count) => onUpdate({ ...selected, open_annotation_count: count })}
        deepLinkAnnotationId={selected.id === deepLinkDeliverableId || !deepLinkDeliverableId ? deepLinkAnnotationId : null}
        isLatestVersion={selected.is_latest_version}
      />

      <DeliverableVersionStrip
        deliverables={sorted}
        selectedId={selected.id}
        onSelect={setSelectedId}
        accessToken={accessToken}
      />
    </div>
  );
}
