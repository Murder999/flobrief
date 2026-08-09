"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast";
import { Modal } from "@/components/ui/modal";
import { useWorkspace } from "@/context/workspace-context";
import {
  briefApi,
  templateApi,
  approvalApi,
  assetApi,
  participantApi,
  agencyApi,
  deliverableApi,
  brandIdentityApi,
  annotationApi,
  commentApi,
  mentionApi,
  type MentionCandidate,
  type BriefDetail,
  type BriefStatus,
  type BriefPriority,
  type TemplateDetail,
  type BriefFieldValueIn,
  type ApprovalRead,
  type BriefVersionSummary,
  type AssetRead,
  type BriefParticipantRead,
  type BrandRead,
  type DeliverableRead,
  type DeliverableCreate,
  type DeliverableType,
  type BrandDNASummary,
  type AnnotationRead,
  type AnnotationCreate,
  type ThreadRead,
  deliverablePreviewApi,
  type PreviewConfigRead,
  type PreviewSlotRead,
} from "@/lib/api-client";
import { UserCircle2, Inbox, Package2, FileText, Link2, MessageSquare, Activity, ChevronDown, ChevronRight, Plus, Upload, CheckCircle2, Trash2, Send, Eye, EyeOff, ZoomIn, Video, Image as ImageIcon, Clock, Square, Smartphone } from "lucide-react";
import { timeEntryApi, type ActiveTimerRead } from "@/lib/api-client";
import { BriefEstimateBadge } from "@/components/time-tracking/BriefEstimateBadge";
import { ManualEntryModal } from "@/components/time-tracking/ManualEntryModal";
import { emitTimerChanged, onTimerChanged } from "@/lib/timer-events";
import { BriefStatusBadge, BriefPriorityBadge } from "@/components/briefs/brief-status-badge";
import { CommentPanel } from "@/components/comments/comment-panel";
import { AssetUploader } from "@/components/assets/asset-uploader";
import { AssetList } from "@/components/assets/asset-list";
import RichTextEditor from "@/components/forms/RichTextEditor";
import AnnotationCanvas from "@/components/media/AnnotationCanvas";
import { NewPinComposer, AnnotationDetailPopover } from "@/components/media/AnnotationPopoverContent";
import { useAuthBlob, mediaType, fmtSize, downloadWithAuth, Lightbox } from "@/components/media/MediaPreview";
import { PlatformPreviewShell } from "@/components/preview/PlatformPreviewShell";
import { PreviewValidationPanel } from "@/components/preview/PreviewValidationPanel";
import { PreviewConfigEditor } from "@/components/preview/PreviewConfigEditor";

const STATUS_LABEL: Record<BriefStatus, string> = {
  draft: "Taslak",
  submitted: "Gönderildi",
  in_review: "İncelemede",
  accepted: "Kabul Edildi",
  in_production: "Üretimde",
  ready_for_review: "İncelemeye Hazır",
  revision_requested: "Revizyon İstendi",
  approved: "Onaylandı",
  completed: "Tamamlandı",
  scheduled: "Takvime Alındı",
  archived: "Arşivlendi",
};

const ROLE_LABELS: Record<string, string> = {
  brand_manager: "Marka Yöneticisi",
  task_owner: "Görev Sahibi",
  designer: "Tasarımcı",
  social_media_manager: "Sosyal Medya Yön.",
  developer: "Geliştirici",
  brand_representative: "Marka Temsilcisi",
  external_approver: "Harici Onaylayıcı",
  viewer: "İzleyici",
};

// Roles that hold brief:create on the backend (see app/core/rbac.py) — the
// same permission POST /briefs/{id}/deliverables requires. Hiding the button
// for other roles is a UX convenience only; the backend enforces it too.
const DELIVERABLE_CREATE_ROLES = new Set(["owner", "admin", "brand_manager", "designer", "social_media_manager"]);

const NEXT_STATUSES_AGENCY: Partial<Record<BriefStatus, BriefStatus[]>> = {
  draft: ["in_review", "submitted"],
  in_review: ["accepted", "revision_requested", "approved"],
  submitted: ["accepted"],
  accepted: ["in_production"],
  in_production: ["ready_for_review"],
  ready_for_review: ["revision_requested", "approved"],
  revision_requested: ["in_production", "ready_for_review"],
  approved: ["completed", "scheduled"],
};

const NEXT_STATUSES_BRAND_REQUEST: Partial<Record<BriefStatus, BriefStatus[]>> = {
  submitted: ["accepted"],
  accepted: ["in_production"],
  in_production: ["ready_for_review"],
  ready_for_review: [],
  revision_requested: ["in_production"],
  approved: ["completed", "scheduled"],
};

const ACTION_LABEL: Record<BriefStatus, string> = {
  draft: "Taslağa Al",
  submitted: "Talebi Gönder",
  in_review: "İncelemeye Gönder",
  accepted: "Talebi Kabul Et",
  in_production: "Üretime Başla",
  ready_for_review: "İncelemeye Sun",
  revision_requested: "Revizyon İste",
  approved: "Onayla",
  completed: "Tamamla",
  scheduled: "Takvime Al",
  archived: "Arşivle",
};

const DELIVERABLE_TYPE_LABELS: Record<DeliverableType, string> = {
  image: "Görsel",
  video: "Video",
  text: "Metin / Kopya",
  document: "Doküman",
  link: "Link",
  other: "Diğer",
};

const DELIVERABLE_STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  draft:              { label: "Taslak",                 className: "status-neutral" },
  submitted:          { label: "İncelemeye Gönderildi",  className: "status-info" },
  revision_requested: { label: "Revizyon İstendi",       className: "status-warning" },
  approved:           { label: "Onaylandı",              className: "status-success" },
  rejected:           { label: "Reddedildi",             className: "status-danger" },
  archived:           { label: "Arşivlendi",             className: "status-neutral opacity-60" },
};

type TabKey = "genel" | "brief" | "referanslar" | "uretim" | "yorumlar" | "aktivite";

// ── DeliverableThumbnail ──────────────────────────────────────────────────────

function DeliverableThumbnail({ asset, accessToken }: { asset: AssetRead; accessToken: string }) {
  const type = mediaType(asset.mime_type);
  const { blobUrl, loading } = useAuthBlob(asset.id, accessToken, type === "image" || type === "video");
  if (loading) {
    return (
      <div className="aspect-video bg-surface-2 flex items-center justify-center">
        <svg className="w-4 h-4 animate-spin text-text-muted/40" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      </div>
    );
  }
  if (type === "image" && blobUrl) {
    return <img src={blobUrl} alt="" className="aspect-video w-full object-cover" />;
  }
  if (type === "video" && blobUrl) {
    return <video src={blobUrl} className="aspect-video w-full object-cover" muted />;
  }
  return (
    <div className="aspect-video bg-surface-2 flex items-center justify-center">
      {type === "video" ? <Video className="w-6 h-6 text-text-muted/40" /> : <ImageIcon className="w-6 h-6 text-text-muted/40" />}
    </div>
  );
}

// ── VideoPlayer ───────────────────────────────────────────────────────────────

function VideoPlayer({ assetId, accessToken }: { assetId: string; accessToken: string }) {
  const { blobUrl, loading } = useAuthBlob(assetId, accessToken);
  if (loading) {
    return (
      <div className="flex items-center justify-center bg-black/80 rounded-xl aspect-video">
        <svg className="w-6 h-6 animate-spin text-white/40" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      </div>
    );
  }
  if (!blobUrl) return <div className="aspect-video bg-black/80 rounded-xl flex items-center justify-center"><p className="text-sm text-white/40">Video yüklenemedi</p></div>;
  return <video src={blobUrl} controls className="w-full rounded-xl bg-black" style={{ maxHeight: 480 }} />;
}

// ── CommentAttachmentPreview ──────────────────────────────────────────────────

function CommentAttachmentPreview({ asset, accessToken, thumbnailOnly }: { asset: AssetRead; accessToken: string; thumbnailOnly?: boolean }) {
  const type = mediaType(asset.mime_type);
  const { blobUrl, loading } = useAuthBlob(asset.id, accessToken, type === "image");
  const [lightbox, setLightbox] = useState(false);

  if (thumbnailOnly) {
    return (
      <div className="w-full h-full bg-surface-2 flex items-center justify-center">
        {type === "image" && blobUrl ? (
          <img src={blobUrl} alt={asset.original_filename} className="w-full h-full object-cover" />
        ) : type === "image" && loading ? (
          <div className="w-full h-full animate-pulse bg-surface-2" />
        ) : type === "video" ? (
          <Video className="w-5 h-5 text-purple-400" />
        ) : (
          <FileText className="w-5 h-5 text-red-400" />
        )}
      </div>
    );
  }

  if (type === "image") {
    return (
      <>
        <div className="relative group aspect-video rounded-lg border border-border overflow-hidden bg-surface-2 w-full">
          <button
            type="button"
            onClick={() => setLightbox(true)}
            className="absolute inset-0 w-full h-full"
            title={asset.original_filename}
          >
            {loading ? (
              <div className="absolute inset-0 bg-surface-2 animate-pulse" />
            ) : blobUrl ? (
              <img src={blobUrl} alt={asset.original_filename} className="w-full h-full object-cover" />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <ImageIcon className="w-6 h-6 text-text-muted/40" />
              </div>
            )}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
          </button>
          <p className="absolute bottom-0 left-0 right-9 bg-gradient-to-t from-black/60 to-transparent text-white text-[9px] px-1.5 py-1 truncate pointer-events-none">
            {asset.original_filename}
          </p>
          <button
            type="button"
            onClick={() => downloadWithAuth(asset.id, asset.filename, accessToken)}
            className="absolute bottom-1 right-1 p-1.5 rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors opacity-0 group-hover:opacity-100"
            title="İndir"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        </div>
        {lightbox && (
          <Lightbox asset={asset} accessToken={accessToken} onClose={() => setLightbox(false)} />
        )}
      </>
    );
  }

  if (type === "video") {
    return (
      <button
        type="button"
        onClick={() => downloadWithAuth(asset.id, asset.filename, accessToken)}
        className="w-full aspect-video rounded-lg border border-border bg-surface-2 hover:bg-hover flex flex-col items-center justify-center gap-1 transition-colors"
        title="İndirmek için tıklayın"
      >
        <Video className="w-6 h-6 text-purple-400" />
        <p className="text-[10px] text-text-muted text-center px-1 truncate max-w-full">{asset.original_filename}</p>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => downloadWithAuth(asset.id, asset.filename, accessToken)}
      className="w-full aspect-video rounded-lg border border-border bg-surface-2 hover:bg-hover flex flex-col items-center justify-center gap-1 transition-colors"
      title="İndirmek için tıklayın"
    >
      <FileText className="w-6 h-6 text-red-400" />
      <p className="text-[10px] text-text-muted text-center px-1 truncate max-w-full">{asset.original_filename}</p>
    </button>
  );
}

// ── CommentPreviewGallery ─────────────────────────────────────────────────────

function CommentPreviewGallery({
  assets,
  accessToken,
  onGoToComments,
}: {
  assets: AssetRead[];
  accessToken: string;
  onGoToComments: () => void;
}) {
  const [activeIndex, setActiveIndex] = useState(assets.length > 0 ? assets.length - 1 : 0);
  const [lightbox, setLightbox] = useState(false);
  const activeAsset = assets[activeIndex] ?? null;
  const type = activeAsset ? mediaType(activeAsset.mime_type) : null;
  const { blobUrl, loading } = useAuthBlob(
    activeAsset?.id ?? "",
    accessToken,
    !!activeAsset && (type === "image" || type === "video")
  );

  // When new assets arrive (e.g. after comment submit), auto-select latest
  useEffect(() => {
    if (assets.length > 0) setActiveIndex(assets.length - 1);
  }, [assets.length]);

  if (assets.length === 0) {
    return (
      <div className="bg-surface border border-border rounded-2xl p-10 text-center">
        <div className="w-14 h-14 rounded-2xl bg-surface-2 border border-border flex items-center justify-center mx-auto mb-5">
          <Package2 className="w-7 h-7 text-text-muted/40" />
        </div>
        <h3 className="text-sm font-semibold text-text mb-2">Henüz teslim görseli eklenmedi.</h3>
        <p className="text-xs text-text-muted leading-relaxed max-w-xs mx-auto mb-6">
          Yorumlar &amp; Revize Notları bölümünden görsel, video veya PDF ekleyip yorum gönderdiğinizde burada önizleme olarak görünür.
        </p>
        <button
          type="button"
          onClick={onGoToComments}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-accent border border-accent/30 hover:bg-accent/5 rounded-xl transition-colors"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Yorumlar bölümüne git
        </button>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border rounded-2xl overflow-hidden">
      {/* Main preview */}
      <div className="relative bg-black/80 min-h-[300px] max-h-[480px] flex items-center justify-center">
        {loading && (
          <div className="flex items-center justify-center p-12">
            <svg className="w-6 h-6 animate-spin text-white/30" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          </div>
        )}
        {!loading && type === "image" && blobUrl && (
          <button type="button" onClick={() => setLightbox(true)} className="cursor-zoom-in" title="Büyütmek için tıklayın">
            <img src={blobUrl} alt={activeAsset!.original_filename} className="max-w-full max-h-[480px] object-contain" />
          </button>
        )}
        {!loading && type === "video" && blobUrl && (
          <video src={blobUrl} controls className="max-w-full max-h-[480px]" />
        )}
        {!loading && (type === "pdf" || type === "file") && (
          <div className="flex flex-col items-center gap-3 py-12">
            <FileText className="w-12 h-12 text-white/40" />
            <p className="text-sm text-white/60">{activeAsset!.original_filename}</p>
          </div>
        )}
        {/* Action buttons */}
        <div className="absolute top-3 right-3 flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => downloadWithAuth(activeAsset!.id, activeAsset!.filename, accessToken)}
            className="p-1.5 rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
            title="İndir"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        </div>
        {/* File info overlay */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-4 py-3 pointer-events-none">
          <p className="text-xs font-medium text-white truncate">{activeAsset!.original_filename}</p>
          <p className="text-[10px] text-white/50 mt-0.5">
            {new Date(activeAsset!.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
      </div>
      {lightbox && activeAsset && type === "image" && (
        <Lightbox asset={activeAsset} accessToken={accessToken} onClose={() => setLightbox(false)} />
      )}

      {/* Thumbnails strip (when more than 1) */}
      {assets.length > 1 && (
        <div className="flex gap-2 p-3 overflow-x-auto border-t border-border/50 bg-surface-2/30">
          {assets.map((a, i) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setActiveIndex(i)}
              className={`flex-shrink-0 w-16 h-16 rounded-lg border overflow-hidden transition-all ${i === activeIndex ? "border-accent shadow-sm" : "border-border hover:border-accent/40"}`}
            >
              <CommentAttachmentPreview asset={a} accessToken={accessToken} thumbnailOnly />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── AnnotationItem ─────────────────────────────────────────────────────────────

const ANN_TYPE_LABELS: Record<string, string> = {
  general: "Genel",
  revision: "Revizyon",
  approval_note: "Onay Notu",
};

const ANN_TYPE_COLORS: Record<string, string> = {
  revision: "text-warning bg-warning/10 border-warning/20",
  approval_note: "text-success bg-success/10 border-success/20",
  general: "text-accent bg-accent/10 border-accent/20",
};

function AnnotationItem({
  ann,
  isActive,
  onActivate,
}: {
  ann: AnnotationRead;
  isActive: boolean;
  onActivate: () => void;
}) {
  const typeColor = ANN_TYPE_COLORS[ann.annotation_type] ?? ANN_TYPE_COLORS.general;
  const isResolved = ann.status === "resolved";

  return (
    <div
      className={`rounded-xl border transition-all ${isActive ? "border-accent/40 bg-accent/[0.03]" : "border-border bg-surface"} ${isResolved ? "opacity-70" : ""}`}
    >
      {/*
        Summary row only — clicking it opens the same anchored popover the
        marker opens (via activeAnnotationId); it never expands inline itself.
      */}
      <button
        type="button"
        className="w-full text-left px-3 py-2.5 flex items-start gap-2.5"
        onClick={onActivate}
        aria-expanded={isActive}
      >
        <span className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold border ${typeColor}`}>
          {ann.label_number}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium border ${typeColor}`}>
              {ANN_TYPE_LABELS[ann.annotation_type]}
            </span>
            {ann.visibility === "internal" && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-50 border border-amber-200 text-amber-700">
                <EyeOff className="w-2.5 h-2.5" />
                Dahili
              </span>
            )}
            {isResolved && (
              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-medium bg-success/10 border border-success/20 text-success">
                <CheckCircle2 className="w-2.5 h-2.5" />
                Çözüldü
              </span>
            )}
          </div>
          <p className="text-xs text-text leading-snug line-clamp-2">{ann.body}</p>
          {ann.replies.length > 0 && (
            <p className="text-[10px] text-text-muted mt-0.5">{ann.replies.length} yanıt</p>
          )}
        </div>
      </button>
    </div>
  );
}

// ── DeliverableWorkspace ──────────────────────────────────────────────────────

interface DeliverableWorkspaceProps {
  deliverables: DeliverableRead[];
  selectedDeliverable: DeliverableRead | null;
  selectedAssetIndex: number;
  annotations: AnnotationRead[];
  activeAnnotationId: string | null;
  annotationMode: boolean;
  newPinData: { x: number; y: number } | null;
  newAnnotationBody: string;
  newAnnotationType: "general" | "revision" | "approval_note";
  newAnnotationVisibility: "internal" | "client_visible";
  savingAnnotation: boolean;
  annotationError: string | null;
  replyBody: Record<string, string>;
  pulseAnnotationId: string | null;
  showNewDeliverable: boolean;
  briefId: string;
  agencyId: string;
  accessToken: string;
  briefStatus: BriefStatus;
  isArchived: boolean;
  canCreateDeliverable: boolean;
  onSelectDeliverable: (d: DeliverableRead) => void;
  onSelectAsset: (index: number) => void;
  onToggleAnnotationMode: () => void;
  onExitAnnotationMode: () => void;
  onCanvasClick: (x: number, y: number) => void;
  onAnnotationClick: (ann: AnnotationRead) => void;
  onCloseAnnotationPopover: () => void;
  onNewAnnotationBodyChange: (v: string) => void;
  onNewAnnotationTypeChange: (v: "general" | "revision" | "approval_note") => void;
  onNewAnnotationVisibilityChange: (v: "internal" | "client_visible") => void;
  onCreateAnnotation: () => void;
  onCancelNewPin: () => void;
  onResolveAnnotation: (id: string) => void;
  onReplyBodyChange: (annotationId: string, val: string) => void;
  onAddReply: (annotationId: string) => void;
  onNewAnnotationMentionInsert: (candidate: MentionCandidate) => void;
  onReplyMentionInsert: (annotationId: string, candidate: MentionCandidate) => void;
  onDeliverableCreated: (d: DeliverableRead) => void;
  onDeliverableUpdated: (d: DeliverableRead) => void;
  onDeliverableDeleted: (id: string) => void;
  onShowNewDeliverable: () => void;
  onHideNewDeliverable: () => void;
}

function DeliverableWorkspace({
  deliverables,
  selectedDeliverable,
  selectedAssetIndex,
  annotations,
  activeAnnotationId,
  annotationMode,
  newPinData,
  newAnnotationBody,
  newAnnotationType,
  newAnnotationVisibility,
  savingAnnotation,
  annotationError,
  replyBody,
  pulseAnnotationId,
  showNewDeliverable,
  briefId,
  agencyId,
  accessToken,
  briefStatus,
  isArchived,
  canCreateDeliverable,
  onSelectDeliverable,
  onSelectAsset,
  onToggleAnnotationMode,
  onExitAnnotationMode,
  onCanvasClick,
  onAnnotationClick,
  onCloseAnnotationPopover,
  onNewAnnotationBodyChange,
  onNewAnnotationTypeChange,
  onNewAnnotationVisibilityChange,
  onCreateAnnotation,
  onCancelNewPin,
  onResolveAnnotation,
  onNewAnnotationMentionInsert,
  onReplyMentionInsert,
  onReplyBodyChange,
  onAddReply,
  onDeliverableCreated,
  onDeliverableDeleted,
  onShowNewDeliverable,
  onHideNewDeliverable,
}: DeliverableWorkspaceProps) {
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [quickUploading, setQuickUploading] = useState(false);
  const [expandedPreview, setExpandedPreview] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const quickFileRef = useRef<HTMLInputElement>(null);
  const { confirm, toast } = useToast();

  const fetchAgencyMentionCandidates = (sourceType: "annotation" | "annotation_reply") => (query: string): Promise<MentionCandidate[]> =>
    mentionApi.agencyCandidates(sourceType, query, agencyId, accessToken).then((r) => r.items);

  const inferDeliverableType = (mime: string): DeliverableType => {
    if (mime.startsWith("image/")) return "image";
    if (mime.startsWith("video/")) return "video";
    if (mime === "application/pdf") return "document";
    return "other";
  };

  const handleQuickUpload = async (file: File) => {
    setQuickUploading(true);
    try {
      const dType = inferDeliverableType(file.type);
      const titleName = file.name.replace(/\.[^/.]+$/, "") || file.name;
      const d = await deliverableApi.create(briefId, { title: titleName, deliverable_type: dType, description: null }, accessToken, agencyId);
      await deliverableApi.uploadAsset(briefId, d.id, file, accessToken, agencyId);
      const updated = await deliverableApi.get(briefId, d.id, accessToken, agencyId);
      onDeliverableCreated(updated);
      onSelectDeliverable(updated);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? "Dosya yüklenemedi.";
      toast(msg, "error");
    } finally {
      setQuickUploading(false);
    }
  };

  const canEdit = selectedDeliverable
    ? (selectedDeliverable.status === "draft" || selectedDeliverable.status === "revision_requested")
    : false;

  const selectedAsset = selectedDeliverable?.assets[selectedAssetIndex] ?? null;
  const assetType = selectedAsset ? mediaType(selectedAsset.mime_type) : null;

  // ── Platform preview (Social Media Preview Center) ─────────────────────────
  const [viewMode, setViewMode] = useState<"raw" | "platform">("raw");
  const [previewConfig, setPreviewConfig] = useState<PreviewConfigRead | null>(null);
  const [previewSlots, setPreviewSlots] = useState<PreviewSlotRead[]>([]);
  const [previewLoading, setPreviewLoading] = useState(true);

  useEffect(() => {
    if (!selectedDeliverable) return;
    let cancelled = false;
    setPreviewLoading(true);
    setPreviewConfig(null);
    setPreviewSlots([]);
    deliverablePreviewApi.getConfig(briefId, selectedDeliverable.id, accessToken, agencyId)
      .then(async (cfg) => {
        if (cancelled) return;
        setPreviewConfig(cfg);
        const slots = await deliverablePreviewApi.listSlots(briefId, selectedDeliverable.id, accessToken, agencyId);
        if (!cancelled) setPreviewSlots(slots);
      })
      .catch(() => {
        // 404 just means no preview config has been created yet for this
        // deliverable — an expected, non-error state when canEdit is true
        // (the agency simply hasn't configured one yet). Any other fetch
        // failure just leaves previewConfig null; the toggle still renders
        // for canEdit so the agency can create a fresh config.
      })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => { cancelled = true; };
  }, [selectedDeliverable, briefId, agencyId, accessToken]);

  const handlePlatformActiveAssetChange = (assetId: string | null) => {
    if (!assetId || !selectedDeliverable) return;
    const idx = selectedDeliverable.assets.findIndex((a) => a.id === assetId);
    if (idx >= 0 && idx !== selectedAssetIndex) onSelectAsset(idx);
  };

  const openAnnotations = annotations.filter((a) => a.status === "open");
  const resolvedAnnotations = annotations.filter((a) => a.status === "resolved");
  const revisionAnnotations = annotations.filter((a) => a.annotation_type === "revision" && a.status === "open");

  const handleUpload = async (file: File) => {
    if (!selectedDeliverable) return;
    setUploading(true);
    try {
      const asset = await deliverableApi.uploadAsset(briefId, selectedDeliverable.id, file, accessToken, agencyId);
      onDeliverableDeleted(selectedDeliverable.id);
      const updated = await deliverableApi.get(briefId, selectedDeliverable.id, accessToken, agencyId);
      onDeliverableCreated(updated);
      onSelectDeliverable(updated);
      void asset;
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? "Dosya yüklenemedi.";
      toast(msg, "error");
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedDeliverable) return;
    setSubmitting(true);
    try {
      const updated = await deliverableApi.submit(briefId, selectedDeliverable.id, accessToken, agencyId);
      onDeliverableDeleted(selectedDeliverable.id);
      onDeliverableCreated(updated);
      onSelectDeliverable(updated);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedDeliverable) return;
    const ok = await confirm({ title: "Teslimat Sil", message: `"${selectedDeliverable.title}" silinecek. Emin misiniz?`, confirmLabel: "Sil", destructive: true });
    if (!ok) return;
    setDeleting(true);
    try {
      await deliverableApi.delete(briefId, selectedDeliverable.id, accessToken, agencyId);
      onDeliverableDeleted(selectedDeliverable.id);
    } finally {
      setDeleting(false);
    }
  };

  if (deliverables.length === 0 && !showNewDeliverable) {
    return (
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOver(false); }}
        onDrop={async (e) => {
          e.preventDefault();
          setDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) await handleQuickUpload(file);
        }}
        className={`rounded-2xl border-2 border-dashed transition-all duration-200 p-12 text-center ${
          dragOver ? "border-accent bg-accent/5 scale-[1.01]" : "border-border bg-surface hover:border-accent/40"
        }`}
      >
        <input
          ref={quickFileRef}
          type="file"
          className="hidden"
          accept="image/*,video/*,.pdf"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleQuickUpload(f); }}
        />
        {quickUploading ? (
          <div className="flex flex-col items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto">
              <svg className="w-7 h-7 animate-spin text-accent" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
            </div>
            <div>
              <p className="font-semibold text-text">Yükleniyor…</p>
              <p className="text-sm text-text-muted mt-0.5">Dosya yüklendikten sonra önizleme görünecek</p>
            </div>
          </div>
        ) : (
          <>
            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5 transition-colors ${dragOver ? "bg-accent/15" : "bg-surface-2 border border-border"}`}>
              <Upload className={`w-8 h-8 transition-colors ${dragOver ? "text-accent" : "text-text-muted/40"}`} />
            </div>
            <h3 className="text-base font-semibold text-text mb-2">
              {dragOver ? "Dosyayı bırakın" : "Henüz teslim yüklenmedi"}
            </h3>
            <p className="text-sm text-text-muted mb-1 max-w-sm mx-auto leading-relaxed">
              Görsel, video veya metin teslimi ekleyerek markaya incelemeye gönderebilirsiniz.
            </p>
            <p className="text-xs text-text-muted/50 mb-7">
              JPG, PNG, WEBP, GIF, MP4, WEBM, PDF desteklenir
            </p>
            {!isArchived && (
              <div className="flex items-center justify-center gap-3 flex-wrap">
                <button
                  onClick={() => quickFileRef.current?.click()}
                  className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-accent hover:bg-accent-hover rounded-xl shadow-sm transition-colors"
                >
                  <Upload className="w-4 h-4" />
                  Dosya Seç & Yükle
                </button>
              </div>
            )}
            <p className="text-xs text-text-muted/40 mt-4">veya dosyayı bu alana sürükle &amp; bırak</p>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      {/* LEFT: Deliverable list */}
      <div className="lg:col-span-2 space-y-2">
        {/* Client-side hiding is a UX convenience only — the backend also
            enforces brief:create permission on POST /deliverables regardless
            of what's shown here. */}
        {!isArchived && canCreateDeliverable && (
          <button
            type="button"
            onClick={onShowNewDeliverable}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-semibold text-accent border border-dashed border-accent/40 hover:border-accent hover:bg-accent/5 rounded-xl transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Yeni Teslim Ekle
          </button>
        )}
        {deliverables.map((d) => {
          const cfg = DELIVERABLE_STATUS_CONFIG[d.status] ?? { label: d.status, className: "status-neutral" };
          const isSelected = d.id === selectedDeliverable?.id;
          const firstAsset = d.assets[0];
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => onSelectDeliverable(d)}
              className={`w-full text-left rounded-xl border overflow-hidden transition-all ${
                isSelected ? "border-accent shadow-sm bg-accent/[0.02]" : "border-border hover:border-accent/40 bg-surface"
              }`}
            >
              {firstAsset ? (
                <DeliverableThumbnail asset={firstAsset} accessToken={accessToken} />
              ) : (
                <div className="aspect-video bg-surface-2 flex items-center justify-center">
                  <Package2 className="w-6 h-6 text-text-muted/30" />
                </div>
              )}
              <div className="px-3 py-2">
                <p className={`text-xs font-semibold truncate ${isSelected ? "text-accent" : "text-text"}`}>{d.title}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium ${cfg.className}`}>{cfg.label}</span>
                  <span className="text-[10px] text-text-muted">v{d.version_number}</span>
                  {d.revision_count > 0 && <span className="text-[10px] text-warning">· Rev.{d.revision_count}</span>}
                  {d.assets.length > 0 && <span className="text-[10px] text-text-muted">· {d.assets.length} dosya</span>}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* RIGHT: Preview + annotations */}
      <div className="lg:col-span-3 space-y-3">
        {selectedDeliverable ? (
          <>
            {/* Deliverable header */}
            <div className="bg-surface border border-border rounded-xl p-3 flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-text truncate">{selectedDeliverable.title}</p>
                  <span className="text-[10px] text-text-muted flex-shrink-0">{DELIVERABLE_TYPE_LABELS[selectedDeliverable.deliverable_type] ?? selectedDeliverable.deliverable_type}</span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${(DELIVERABLE_STATUS_CONFIG[selectedDeliverable.status] ?? {}).className ?? ""}`}>
                    {(DELIVERABLE_STATUS_CONFIG[selectedDeliverable.status] ?? {}).label ?? selectedDeliverable.status}
                  </span>
                  <span className="text-[10px] text-text-muted">Versiyon {selectedDeliverable.version_number}</span>
                  {revisionAnnotations.length > 0 && (
                    <span className="text-[10px] text-warning">{revisionAnnotations.length} açık revizyon</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {canEdit && (
                  <>
                    <button
                      onClick={() => fileRef.current?.click()}
                      disabled={uploading}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium border border-border text-text-muted hover:border-accent hover:text-accent rounded-lg transition-colors disabled:opacity-50"
                    >
                      <Upload className="w-3 h-3" />
                      {uploading ? "Yükleniyor…" : "Dosya Ekle"}
                    </button>
                    <input ref={fileRef} type="file" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }} />
                    <button
                      onClick={handleSubmit}
                      disabled={submitting}
                      className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold bg-accent text-white rounded-lg hover:bg-accent-hover disabled:opacity-50 transition-colors"
                    >
                      <Send className="w-3 h-3" />
                      {submitting ? "Gönderiliyor…" : "Onaya Gönder"}
                    </button>
                  </>
                )}
                {canEdit && (
                  <button onClick={handleDelete} disabled={deleting} className="p-1.5 text-text-muted hover:text-danger transition-colors" title="Sil">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>

            {/* Revision note */}
            {selectedDeliverable.revision_note && (
              <div className="status-warning rounded-xl px-4 py-3 flex items-start gap-2">
                <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                <div>
                  <p className="text-xs font-semibold mb-0.5">Revizyon Talebi</p>
                  <p className="text-xs">{selectedDeliverable.revision_note}</p>
                </div>
              </div>
            )}

            {/* Asset preview area */}
            {selectedDeliverable.assets.length > 0 ? (
              <>
                {/* Asset tabs */}
                {selectedDeliverable.assets.length > 1 && (
                  <div className="flex items-center gap-1 overflow-x-auto pb-1">
                    {selectedDeliverable.assets.map((a, idx) => (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => onSelectAsset(idx)}
                        className={`flex-shrink-0 w-14 h-14 rounded-lg border-2 overflow-hidden transition-all ${
                          idx === selectedAssetIndex ? "border-accent shadow-sm" : "border-border hover:border-accent/40"
                        }`}
                      >
                        <DeliverableThumbnail asset={a} accessToken={accessToken} />
                      </button>
                    ))}
                  </div>
                )}

                {/* Main preview */}
                <div className="bg-surface border border-border rounded-xl overflow-hidden">
                  {/* Toolbar */}
                  <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-surface-2/30">
                    <div className="flex items-center gap-2 text-xs text-text-muted">
                      {selectedAsset && (
                        <>
                          <span className="font-medium text-text truncate max-w-[160px]">{selectedAsset.original_filename ?? selectedAsset.filename}</span>
                          {selectedAsset.size_bytes && <span>{fmtSize(selectedAsset.size_bytes)}</span>}
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {assetType === "image" && selectedAsset && (
                        <button
                          type="button"
                          onClick={() => setExpandedPreview(true)}
                          className="p-1.5 text-text-muted hover:text-accent transition-colors"
                          title="Büyüt"
                        >
                          <ZoomIn className="w-4 h-4" />
                        </button>
                      )}
                      {selectedAsset && (
                        <button
                          type="button"
                          onClick={() => downloadWithAuth(selectedAsset.id, selectedAsset.filename, accessToken)}
                          className="p-1.5 text-text-muted hover:text-accent transition-colors"
                          title="İndir"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                          </svg>
                        </button>
                      )}
                      {assetType === "image" && (
                        <button
                          type="button"
                          onClick={onToggleAnnotationMode}
                          className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold rounded-lg transition-colors ${
                            annotationMode
                              ? "bg-accent text-white shadow-sm"
                              : "bg-accent/10 border border-accent/30 text-accent hover:bg-accent/20"
                          }`}
                        >
                          {annotationMode ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                          {annotationMode ? "Revizyon Modunu Kapat" : "Revizyon Noktası Belirle"}
                        </button>
                      )}
                    </div>
                  </div>

                  {!previewLoading && (previewConfig || canEdit) && (
                    <div className="flex items-center gap-1.5 px-4 py-2 border-b border-border" role="tablist" aria-label="Görüntüleme modu">
                      <button
                        type="button"
                        role="tab"
                        aria-selected={viewMode === "raw"}
                        onClick={() => setViewMode("raw")}
                        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors ${
                          viewMode === "raw" ? "bg-accent text-white border-accent" : "bg-surface text-text-muted border-border"
                        }`}
                      >
                        <ImageIcon className="w-3.5 h-3.5" /> Ham Dosya
                      </button>
                      <button
                        type="button"
                        role="tab"
                        aria-selected={viewMode === "platform"}
                        onClick={() => setViewMode("platform")}
                        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium border transition-colors ${
                          viewMode === "platform" ? "bg-accent text-white border-accent" : "bg-surface text-text-muted border-border"
                        }`}
                      >
                        <Smartphone className="w-3.5 h-3.5" /> Platform Önizlemesi
                      </button>
                    </div>
                  )}

                  {viewMode === "platform" ? (
                    <div className="p-4 space-y-3">
                      {canEdit && selectedDeliverable && (
                        <PreviewConfigEditor
                          briefId={briefId}
                          deliverableId={selectedDeliverable.id}
                          agencyId={agencyId}
                          accessToken={accessToken}
                          assets={selectedDeliverable.assets}
                          config={previewConfig}
                          slots={previewSlots}
                          onConfigSaved={setPreviewConfig}
                          onSlotsSaved={setPreviewSlots}
                        />
                      )}
                      {previewConfig && (
                      <>
                      {assetType === "image" && (
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={onToggleAnnotationMode}
                            className={`flex items-center gap-1.5 pl-2.5 pr-3 py-1.5 text-[12.5px] font-semibold rounded-full transition-colors ${
                              annotationMode
                                ? "bg-accent text-white shadow-sm"
                                : "bg-gradient-accent text-white hover:opacity-90 shadow-sm"
                            }`}
                          >
                            {annotationMode ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            {annotationMode ? "Revizyon Modunu Kapat" : "Revizyon Noktası Belirle"}
                          </button>
                        </div>
                      )}
                      <PlatformPreviewShell
                        config={previewConfig}
                        slots={previewSlots}
                        accessToken={accessToken}
                        annotations={annotations}
                        activeAnnotationId={activeAnnotationId}
                        onAnnotationClick={onAnnotationClick}
                        annotationMode={annotationMode}
                        onCanvasClick={onCanvasClick}
                        onExitAnnotationMode={onExitAnnotationMode}
                        newPinDraft={newPinData}
                        renderNewPinComposer={() => (
                          <NewPinComposer
                            value={newAnnotationBody}
                            onChange={onNewAnnotationBodyChange}
                            onSave={onCreateAnnotation}
                            onCancel={onCancelNewPin}
                            saving={savingAnnotation}
                            error={annotationError}
                            mentionCandidatesFetcher={fetchAgencyMentionCandidates("annotation")}
                            onMentionInsert={onNewAnnotationMentionInsert}
                            extraFields={
                              <div className="flex items-center gap-2">
                                <select
                                  value={newAnnotationType}
                                  onChange={(e) => onNewAnnotationTypeChange(e.target.value as "general" | "revision" | "approval_note")}
                                  className="flex-1 text-[11px] bg-surface border border-border rounded-lg px-2 py-1.5 text-text focus:outline-none focus:border-accent"
                                >
                                  <option value="general">Genel</option>
                                  <option value="revision">Revizyon</option>
                                  <option value="approval_note">Onay Notu</option>
                                </select>
                                <select
                                  value={newAnnotationVisibility}
                                  onChange={(e) => onNewAnnotationVisibilityChange(e.target.value as "internal" | "client_visible")}
                                  className="flex-1 text-[11px] bg-surface border border-border rounded-lg px-2 py-1.5 text-text focus:outline-none focus:border-accent"
                                >
                                  <option value="client_visible">Müşteri Görür</option>
                                  <option value="internal">Dahili</option>
                                </select>
                              </div>
                            }
                          />
                        )}
                        onCloseNewPinComposer={onCancelNewPin}
                        renderAnnotationPopover={(ann) => (
                          <AnnotationDetailPopover
                            annotation={ann}
                            fallbackAuthorLabel="Ajans"
                            statusBadge={
                              ann.visibility === "internal" ? (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-50 border border-amber-200 text-amber-700">Dahili</span>
                              ) : undefined
                            }
                            replyValue={replyBody[ann.id] ?? ""}
                            onReplyChange={(v) => onReplyBodyChange(ann.id, v)}
                            onReply={() => onAddReply(ann.id)}
                            replying={false}
                            onResolve={() => onResolveAnnotation(ann.id)}
                            mentionCandidatesFetcher={fetchAgencyMentionCandidates("annotation_reply")}
                            onMentionInsert={(c) => onReplyMentionInsert(ann.id, c)}
                          />
                        )}
                        onCloseAnnotationPopover={onCloseAnnotationPopover}
                        onActiveAssetChange={handlePlatformActiveAssetChange}
                      />
                      <PreviewValidationPanel warnings={previewConfig.warnings} />
                      </>
                      )}
                    </div>
                  ) : (
                  <>
                  {/* Preview content */}
                  {assetType === "image" && selectedAsset ? (
                    // Explicit height (not min/max) so the child <img>'s h-full percentage
                    // resolves to a real box instead of falling back to `auto` — without this,
                    // object-fit: contain has nothing to constrain against and tall images get
                    // silently clipped by the container's overflow.
                    <div className="relative w-full bg-surface-2" style={{ height: "clamp(520px, 62vh, 760px)" }}>
                      <div className="absolute inset-0 p-4 sm:p-6">
                        <AnnotationCanvas
                          assetId={selectedAsset.id}
                          accessToken={accessToken}
                          annotations={annotations.filter((a) => a.asset_id === selectedAsset.id || a.asset_id === null)}
                          activeAnnotationId={activeAnnotationId}
                          annotationMode={annotationMode}
                          onCanvasClick={onCanvasClick}
                          onAnnotationClick={onAnnotationClick}
                          onExitAnnotationMode={onExitAnnotationMode}
                          className="w-full h-full"
                          newPinDraft={newPinData}
                          onCloseNewPinComposer={onCancelNewPin}
                          renderNewPinComposer={() => (
                            <NewPinComposer
                              value={newAnnotationBody}
                              onChange={onNewAnnotationBodyChange}
                              onSave={onCreateAnnotation}
                              onCancel={onCancelNewPin}
                              saving={savingAnnotation}
                              error={annotationError}
                              mentionCandidatesFetcher={fetchAgencyMentionCandidates("annotation")}
                              onMentionInsert={onNewAnnotationMentionInsert}
                              extraFields={
                                <div className="flex items-center gap-2">
                                  <select
                                    value={newAnnotationType}
                                    onChange={(e) => onNewAnnotationTypeChange(e.target.value as "general" | "revision" | "approval_note")}
                                    className="flex-1 text-[11px] bg-surface border border-border rounded-lg px-2 py-1.5 text-text focus:outline-none focus:border-accent"
                                  >
                                    <option value="general">Genel</option>
                                    <option value="revision">Revizyon</option>
                                    <option value="approval_note">Onay Notu</option>
                                  </select>
                                  <select
                                    value={newAnnotationVisibility}
                                    onChange={(e) => onNewAnnotationVisibilityChange(e.target.value as "internal" | "client_visible")}
                                    className="flex-1 text-[11px] bg-surface border border-border rounded-lg px-2 py-1.5 text-text focus:outline-none focus:border-accent"
                                  >
                                    <option value="client_visible">Müşteri Görür</option>
                                    <option value="internal">Dahili</option>
                                  </select>
                                </div>
                              }
                            />
                          )}
                          onCloseAnnotationPopover={onCloseAnnotationPopover}
                          renderAnnotationPopover={(ann) => (
                            <AnnotationDetailPopover
                              annotation={ann}
                              fallbackAuthorLabel="Ajans"
                              statusBadge={
                                ann.visibility === "internal" ? (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-50 border border-amber-200 text-amber-700">Dahili</span>
                                ) : undefined
                              }
                              replyValue={replyBody[ann.id] ?? ""}
                              onReplyChange={(v) => onReplyBodyChange(ann.id, v)}
                              onReply={() => onAddReply(ann.id)}
                              replying={false}
                              onResolve={() => onResolveAnnotation(ann.id)}
                              mentionCandidatesFetcher={fetchAgencyMentionCandidates("annotation_reply")}
                              onMentionInsert={(c) => onReplyMentionInsert(ann.id, c)}
                            />
                          )}
                          pulseAnnotationId={pulseAnnotationId}
                        />
                      </div>
                    </div>
                  ) : (
                  <div className="p-4">
                    {assetType === "video" && selectedAsset ? (
                      <VideoPlayer assetId={selectedAsset.id} accessToken={accessToken} />
                    ) : selectedAsset ? (
                      <div className="flex items-center gap-4 py-4">
                        <div className="w-12 h-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center flex-shrink-0">
                          <svg className="w-6 h-6 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-text">{selectedAsset.original_filename ?? selectedAsset.filename}</p>
                          {selectedAsset.size_bytes && <p className="text-xs text-text-muted mt-0.5">{fmtSize(selectedAsset.size_bytes)}</p>}
                        </div>
                        <button
                          type="button"
                          onClick={() => downloadWithAuth(selectedAsset.id, selectedAsset.filename, accessToken)}
                          className="ml-auto px-3 py-1.5 text-xs font-semibold border border-border text-text-muted hover:border-accent hover:text-accent rounded-lg transition-colors"
                        >
                          İndir
                        </button>
                      </div>
                    ) : null}
                  </div>
                  )}
                  </>
                  )}
                </div>

                {expandedPreview && selectedAsset && (
                  <Lightbox asset={selectedAsset} accessToken={accessToken} onClose={() => setExpandedPreview(false)} />
                )}

                {/* Annotations list */}
                {annotations.length > 0 && (
                  <div className="bg-surface border border-border rounded-xl overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                      <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                        Yorum Noktaları
                      </h4>
                      <div className="flex items-center gap-2 text-[10px] text-text-muted">
                        {openAnnotations.length > 0 && <span className="status-warning px-1.5 py-0.5 rounded">{openAnnotations.length} açık</span>}
                        {resolvedAnnotations.length > 0 && <span className="status-success px-1.5 py-0.5 rounded">{resolvedAnnotations.length} çözüldü</span>}
                      </div>
                    </div>
                    <div className="p-3 space-y-2 max-h-80 overflow-y-auto">
                      {annotations.map((ann) => (
                        <AnnotationItem
                          key={ann.id}
                          ann={ann}
                          isActive={ann.id === activeAnnotationId}
                          onActivate={() => {
                            const idx = selectedDeliverable?.assets.findIndex((a) => a.id === ann.asset_id) ?? -1;
                            if (idx >= 0) onSelectAsset(idx);
                            onAnnotationClick(ann);
                          }}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              /* No assets empty state */
              <div className="bg-surface border-2 border-dashed border-border rounded-xl p-8 text-center">
                <Upload className="w-8 h-8 text-text-muted/40 mx-auto mb-3" />
                <p className="text-sm font-medium text-text-muted mb-1">Bu teslimat için henüz dosya yüklenmedi</p>
                <p className="text-xs text-text-muted/60 mb-4">Görsel, video veya doküman ekleyin.</p>
                {canEdit && (
                  <button
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-border text-text-muted hover:border-accent hover:text-accent rounded-lg transition-colors"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    {uploading ? "Yükleniyor…" : "Dosya Ekle"}
                  </button>
                )}
                <input ref={fileRef} type="file" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }} />
              </div>
            )}

            {selectedDeliverable.approved_at && (
              <div className="status-success rounded-xl px-4 py-3 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                <p className="text-xs font-semibold">
                  Onaylandı — {new Date(selectedDeliverable.approved_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <ZoomIn className="w-8 h-8 text-text-muted/30 mb-3" />
            <p className="text-sm text-text-muted">Sol taraftan bir teslimat seçin</p>
          </div>
        )}
      </div>

      <Modal isOpen={showNewDeliverable} onClose={onHideNewDeliverable} title="Yeni Teslim Ekle">
        <NewDeliverableForm
          briefId={briefId}
          agencyId={agencyId}
          accessToken={accessToken}
          onCreated={onDeliverableCreated}
          onCancel={onHideNewDeliverable}
        />
      </Modal>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse">
      <div className="border-b border-border px-4 sm:px-8 py-6">
        <div className="h-4 bg-surface-2 rounded w-20 mb-4" />
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1 space-y-3">
            <div className="h-8 bg-surface-2 rounded w-2/3" />
            <div className="h-4 bg-surface-2 rounded w-1/4" />
            <div className="flex gap-2 mt-2">
              <div className="h-6 bg-surface-2 rounded-full w-20" />
              <div className="h-6 bg-surface-2 rounded-full w-16" />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="h-8 bg-surface-2 rounded-lg w-24" />
          </div>
        </div>
      </div>
      <div className="px-4 sm:px-8 py-6 grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="sm:col-span-2 space-y-4">
          <div className="h-40 bg-surface-2 rounded-xl" />
          <div className="h-64 bg-surface-2 rounded-xl" />
        </div>
        <div className="space-y-4">
          <div className="h-48 bg-surface-2 rounded-xl" />
          <div className="h-32 bg-surface-2 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

function approvalStatusColor(status: ApprovalRead["status"]) {
  switch (status) {
    case "approved":            return "status-success";
    case "revision_requested":  return "status-warning";
    case "pending":             return "status-info";
    case "cancelled":           return "status-neutral";
    case "expired":             return "status-danger";
  }
}

function approvalStatusLabel(status: ApprovalRead["status"]) {
  switch (status) {
    case "approved": return "Onaylandı";
    case "revision_requested": return "Revizyon İstendi";
    case "pending": return "Onay Bekliyor";
    case "cancelled": return "İptal Edildi";
    case "expired": return "Süresi Doldu";
  }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover transition-colors font-medium flex-shrink-0"
    >
      {copied ? (
        <svg className="w-3 h-3 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
      {copied ? "Kopyalandı" : "Kopyala"}
    </button>
  );
}

interface ApprovalPanelProps {
  briefId: string;
  agencyId: string;
  accessToken: string;
  briefStatus: BriefStatus;
  approvals: ApprovalRead[];
  versions: BriefVersionSummary[];
  onSent: () => void;
  onRevoked: () => void;
}

function ApprovalPanel({ briefId, agencyId, accessToken, briefStatus, approvals, versions, onSent, onRevoked }: ApprovalPanelProps) {
  const [sending, setSending] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [newApprovalUrl, setNewApprovalUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showVersions, setShowVersions] = useState(false);
  const { confirm } = useToast();

  const pendingApproval = approvals.find((a) => a.status === "pending");
  const canSend = briefStatus === "draft" || briefStatus === "revision_requested";

  const handleSend = async () => {
    setSending(true);
    setError("");
    try {
      const res = await approvalApi.sendToApproval(briefId, agencyId, accessToken);
      setNewApprovalUrl(res.approval_url);
      onSent();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Gönderim başarısız.");
    } finally {
      setSending(false);
    }
  };

  const handleRevoke = async (approvalId: string) => {
    const ok = await confirm({
      title: "Onay Talebini İptal Et",
      message: "Bu onay talebini iptal etmek istediğinizden emin misiniz?",
      confirmLabel: "İptal Et",
      destructive: true,
    });
    if (!ok) return;
    setRevoking(true);
    try {
      await approvalApi.revokeApproval(briefId, approvalId, agencyId, accessToken);
      onRevoked();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "İptal başarısız.");
    } finally {
      setRevoking(false);
    }
  };

  return (
    <div className="bg-surface rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Onay Durumu</h3>
      </div>
      <div className="p-4 space-y-3">
        {canSend && !pendingApproval && (
          <div>
            <p className="text-xs text-text-muted mb-2">Markaya onay için özel link gönderilebilir.</p>
            <button
              onClick={handleSend}
              disabled={sending}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-accent hover:bg-accent-hover text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-60"
            >
              {sending ? (
                <><svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" /></svg>Gönderiliyor…</>
              ) : (
                <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>Onaya Gönder</>
              )}
            </button>
            {error && <p className="mt-2 text-[11px] text-danger">{error}</p>}
          </div>
        )}

        {newApprovalUrl && (
          <div className="status-success rounded-lg p-3 space-y-2">
            <p className="text-[11px] font-semibold">Onay linki oluşturuldu</p>
            <div className="flex items-center gap-2 bg-surface rounded border border-border px-2 py-1.5">
              <code className="flex-1 text-[11px] text-text-muted truncate">{newApprovalUrl}</code>
              <CopyButton text={newApprovalUrl} />
            </div>
          </div>
        )}

        {pendingApproval && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${approvalStatusColor(pendingApproval.status)}`}>
                {approvalStatusLabel(pendingApproval.status)}
              </span>
              <button onClick={() => handleRevoke(pendingApproval.id)} disabled={revoking} className="text-[11px] text-danger hover:text-danger/80 transition-colors">
                {revoking ? "İptal ediliyor…" : "Geri Al"}
              </button>
            </div>
            <p className="text-[11px] text-text-muted">
              {new Date(pendingApproval.created_at).toLocaleDateString("tr-TR")} tarihinde gönderildi
            </p>
            {error && <p className="text-[11px] text-danger">{error}</p>}
          </div>
        )}

        {approvals.filter((a) => a.status !== "pending").length > 0 && (
          <div className="pt-2 border-t border-border space-y-2">
            <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide">Geçmiş</p>
            {approvals.filter((a) => a.status !== "pending").slice(0, 3).map((a) => (
              <div key={a.id} className="flex items-center gap-2">
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${approvalStatusColor(a.status)}`}>{approvalStatusLabel(a.status)}</span>
                {a.approved_by_name && <span className="text-[11px] text-text-muted truncate">{a.approved_by_name}</span>}
                {a.decided_at && <span className="text-[11px] text-text-muted ml-auto flex-shrink-0">{new Date(a.decided_at).toLocaleDateString("tr-TR")}</span>}
              </div>
            ))}
          </div>
        )}

        {versions.length > 0 && (
          <div className="pt-2 border-t border-border">
            <button onClick={() => setShowVersions(!showVersions)} className="flex items-center justify-between w-full text-[11px] text-text-muted hover:text-text transition-colors">
              <span className="font-medium">Versiyonlar ({versions.length})</span>
              <svg className={`w-3.5 h-3.5 transition-transform ${showVersions ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
            </button>
            {showVersions && (
              <div className="mt-2 space-y-1.5">
                {versions.map((v) => (
                  <div key={v.id} className="flex items-center gap-2">
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-accent/10 text-accent text-[10px] font-bold">{v.version_number}</span>
                    <span className="text-[11px] text-text-muted">{new Date(v.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" })}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Deliverable card component ────────────────────────────────────────────────

interface DeliverableCardProps {
  d: DeliverableRead;
  briefId: string;
  agencyId: string;
  accessToken: string;
  onUpdate: (updated: DeliverableRead) => void;
  onDelete: (id: string) => void;
}

function DeliverableCard({ d, briefId, agencyId, accessToken, onUpdate, onDelete }: DeliverableCardProps) {
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { confirm } = useToast();
  const cfg = DELIVERABLE_STATUS_CONFIG[d.status] ?? { label: d.status, className: "bg-surface-2 text-text-muted border-border" };

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const updated = await deliverableApi.uploadAsset(briefId, d.id, file, accessToken, agencyId);
      onUpdate({ ...d, assets: [...d.assets, updated] });
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const updated = await deliverableApi.submit(briefId, d.id, accessToken, agencyId);
      onUpdate(updated);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    const ok = await confirm({ title: "Deliverable Sil", message: `"${d.title}" silinecek. Emin misiniz?`, confirmLabel: "Sil", destructive: true });
    if (!ok) return;
    setDeleting(true);
    try {
      await deliverableApi.delete(briefId, d.id, accessToken, agencyId);
      onDelete(d.id);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-surface-2/40 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
          d.status === "approved" ? "bg-success-subtle text-success" :
          d.status === "submitted" ? "bg-info-subtle text-info" :
          d.status === "revision_requested" ? "bg-warning-subtle text-warning" :
          "bg-surface-2 text-text-muted"
        }`}>
          <Package2 className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-text truncate">{d.title}</p>
            <span className="text-[10px] text-text-muted flex-shrink-0">{DELIVERABLE_TYPE_LABELS[d.deliverable_type] ?? d.deliverable_type}</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${cfg.className}`}>{cfg.label}</span>
            {d.assets.length > 0 && <span className="text-[10px] text-text-muted">{d.assets.length} dosya</span>}
            {d.revision_count > 0 && <span className="text-[10px] text-warning">Rev. {d.revision_count}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {(d.status === "draft" || d.status === "revision_requested") && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); handleSubmit(); }}
                disabled={submitting}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-accent text-white text-[11px] font-semibold rounded-lg hover:bg-accent-hover disabled:opacity-50 transition-colors"
              >
                <Send className="w-3 h-3" />
                {submitting ? "Gönderiliyor…" : "Gönder"}
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); fileRef.current?.click(); }}
                disabled={uploading}
                className="flex items-center gap-1.5 px-2.5 py-1.5 border border-border text-text-muted text-[11px] rounded-lg hover:border-accent hover:text-accent disabled:opacity-50 transition-colors"
              >
                <Upload className="w-3 h-3" />
                {uploading ? "Yükleniyor…" : "Dosya Ekle"}
              </button>
              <input ref={fileRef} type="file" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); }} />
              <button
                onClick={(e) => { e.stopPropagation(); handleDelete(); }}
                disabled={deleting}
                className="p-1.5 text-text-muted hover:text-danger transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          )}
          {expanded ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3 space-y-3">
          {d.description && (
            <p className="text-xs text-text-muted leading-relaxed">{d.description}</p>
          )}
          {d.revision_note && (
            <div className="status-warning rounded-lg px-3 py-2">
              <p className="text-[11px] font-semibold mb-0.5">Revizyon Notu</p>
              <p className="text-xs">{d.revision_note}</p>
            </div>
          )}
          {d.approve_note && (
            <div className="status-success rounded-lg px-3 py-2">
              <p className="text-[11px] font-semibold mb-0.5">Onay Notu</p>
              <p className="text-xs">{d.approve_note}</p>
            </div>
          )}
          {d.assets.length > 0 && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold text-text-muted uppercase tracking-wide">Dosyalar</p>
              <div className="grid grid-cols-2 gap-2">
                {d.assets.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 px-2.5 py-2 bg-surface-2 rounded-lg border border-border">
                    <svg className="w-3.5 h-3.5 text-text-muted flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    <span className="text-[11px] text-text truncate flex-1">{a.original_filename}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {d.submitted_at && (
            <p className="text-[10px] text-text-muted">
              Gönderildi: {new Date(d.submitted_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}
            </p>
          )}
          {d.approved_at && (
            <p className="text-[10px] text-success">
              Onaylandı: {new Date(d.approved_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── New deliverable form ──────────────────────────────────────────────────────

interface NewDeliverableFormProps {
  briefId: string;
  agencyId: string;
  accessToken: string;
  onCreated: (d: DeliverableRead) => void;
  onCancel: () => void;
}

function NewDeliverableForm({ briefId, agencyId, accessToken, onCreated, onCancel }: NewDeliverableFormProps) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState<DeliverableType>("other");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) { setError("Başlık zorunlu"); return; }
    setSaving(true);
    setError("");
    try {
      const data: DeliverableCreate = { title: title.trim(), deliverable_type: type, description: description || null };
      const created = await deliverableApi.create(briefId, data, accessToken, agencyId);
      onCreated(created);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message ?? "Oluşturulamadı");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-surface border border-accent/30 rounded-xl p-4 space-y-3">
      <p className="text-sm font-semibold text-text">Yeni Deliverable</p>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Başlık (örn: Instagram Carousel Görseli)"
            className="w-full px-3 py-2 text-sm bg-surface-2 border border-border rounded-lg focus:outline-none focus:border-accent text-text placeholder:text-text-muted"
          />
        </div>
        <div>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as DeliverableType)}
            className="w-full px-3 py-2 text-sm bg-surface-2 border border-border rounded-lg focus:outline-none focus:border-accent text-text"
          >
            {(Object.entries(DELIVERABLE_TYPE_LABELS) as [DeliverableType, string][]).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Kısa açıklama (opsiyonel)"
            rows={1}
            className="w-full px-3 py-2 text-sm bg-surface-2 border border-border rounded-lg focus:outline-none focus:border-accent text-text placeholder:text-text-muted resize-none"
          />
        </div>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} className="px-3 py-1.5 text-xs text-text-muted hover:text-text border border-border rounded-lg transition-colors">İptal</button>
        <button type="submit" disabled={saving} className="px-3 py-1.5 text-xs font-semibold text-white bg-accent hover:bg-accent-hover rounded-lg disabled:opacity-50 transition-colors">
          {saving ? "Oluşturuluyor…" : "Oluştur"}
        </button>
      </div>
    </form>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function BriefDetailPage() {
  const { id: briefId } = useParams<{ id: string }>();
  const { accessToken, user } = useAuth();
  const { activeAgency } = useWorkspace();
  const currentAgencyId = activeAgency?.id ?? null;
  const canCreateDeliverable = DELIVERABLE_CREATE_ROLES.has(activeAgency?.member_role ?? "");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { confirm, toast } = useToast();
  const deepLinkTabAppliedRef = useRef(false);
  const deepLinkPulsedRef = useRef(false);

  // Time tracking quick-start affordance
  const [activeTimer, setActiveTimer] = useState<ActiveTimerRead | null>(null);
  const [timerBusy, setTimerBusy] = useState(false);
  const [manualEntryModalOpen, setManualEntryModalOpen] = useState(false);

  const [brief, setBrief] = useState<BriefDetail | null>(null);
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [brand, setBrand] = useState<BrandRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusChanging, setStatusChanging] = useState(false);
  const [archiving, setArchiving] = useState(false);

  const [approvals, setApprovals] = useState<ApprovalRead[]>([]);
  const [versions, setVersions] = useState<BriefVersionSummary[]>([]);
  const [assets, setAssets] = useState<AssetRead[]>([]);
  const [participants, setParticipants] = useState<BriefParticipantRead[]>([]);
  const [deliverables, setDeliverables] = useState<DeliverableRead[]>([]);
  const [showNewDeliverable, setShowNewDeliverable] = useState(false);

  // Annotation state
  const [selectedDeliverable, setSelectedDeliverable] = useState<DeliverableRead | null>(null);
  const [selectedAssetIndex, setSelectedAssetIndex] = useState(0);
  const [annotations, setAnnotations] = useState<AnnotationRead[]>([]);
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | null>(null);
  const [annotationMode, setAnnotationMode] = useState(false);
  const [newPinData, setNewPinData] = useState<{ x: number; y: number } | null>(null);
  const [newAnnotationBody, setNewAnnotationBody] = useState("");
  const [newAnnotationMentionedIds, setNewAnnotationMentionedIds] = useState<string[]>([]);
  const [newAnnotationType, setNewAnnotationType] = useState<"general" | "revision" | "approval_note">("general");
  const [newAnnotationVisibility, setNewAnnotationVisibility] = useState<"internal" | "client_visible">("client_visible");
  const [savingAnnotation, setSavingAnnotation] = useState(false);
  const [annotationError, setAnnotationError] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState<Record<string, string>>({});
  const [replyMentionedIds, setReplyMentionedIds] = useState<Record<string, string[]>>({});
  const [pulseAnnotationId, setPulseAnnotationId] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<TabKey>("genel");
  const [dnaSummary, setDnaSummary] = useState<BrandDNASummary | null>(null);
  const [commentPreviewAssets, setCommentPreviewAssets] = useState<AssetRead[]>([]);
  const commentSectionRef = useRef<HTMLDivElement>(null);

  const handleThreadsLoaded = useCallback((threads: ThreadRead[]) => {
    const seen = new Set<string>();
    const assets: AssetRead[] = [];
    for (const thread of threads) {
      for (const comment of thread.comments) {
        for (const a of (comment.attachments ?? [])) {
          const mime = a.mime_type ?? "";
          const isMedia = mime.startsWith("image/") || mime.startsWith("video/") || mime === "application/pdf";
          if (isMedia && !seen.has(a.id)) {
            seen.add(a.id);
            assets.push(a);
          }
        }
      }
    }
    setCommentPreviewAssets(assets);
  }, []);

  const loadBrief = useCallback(async () => {
    if (!accessToken || !currentAgencyId) return;
    setLoading(true);
    setError(null);
    try {
      const b = await briefApi.get(briefId, currentAgencyId, accessToken);
      setBrief(b);

      const [tmpl, appr, vers, assetList, partList, delivList] = await Promise.all([
        (b.template_id
          ? templateApi.get(b.template_id, currentAgencyId, accessToken)
          : Promise.resolve(null)
        ).catch(() => null),
        approvalApi.listApprovals(briefId, currentAgencyId, accessToken).catch(() => []),
        approvalApi.listVersions(briefId, currentAgencyId, accessToken).catch(() => []),
        assetApi.listByBrief(briefId, currentAgencyId, accessToken).catch(() => []),
        participantApi.list(briefId, currentAgencyId, accessToken).catch(() => []),
        deliverableApi.list(briefId, accessToken, currentAgencyId).catch(() => []),
      ]);

      setTemplate(tmpl);
      setApprovals(appr);
      setVersions(vers);
      setAssets(assetList);
      setParticipants(partList);
      setDeliverables(delivList);

      if (b.brand_id) {
        agencyApi.listBrands(currentAgencyId, accessToken)
          .then((brands) => setBrand(brands.find((br) => br.id === b.brand_id) ?? null))
          .catch(() => null);
        brandIdentityApi.getDNASummary(b.brand_id, currentAgencyId, accessToken)
          .then((s) => setDnaSummary(s))
          .catch(() => setDnaSummary(null));
      }
    } catch {
      setError("Brief yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, currentAgencyId, briefId]);

  useEffect(() => {
    loadBrief();
  }, [loadBrief]);

  const handleChangeStatus = async (newStatus: BriefStatus) => {
    if (!accessToken || !currentAgencyId || !brief) return;
    setStatusChanging(true);
    try {
      const updated = await briefApi.changeStatus(briefId, { status: newStatus }, currentAgencyId, accessToken);
      setBrief(updated);
    } finally {
      setStatusChanging(false);
    }
  };

  const handleArchive = async () => {
    if (!accessToken || !currentAgencyId || !brief) return;
    const ok = await confirm({
      title: "Brief'i Arşivle",
      message: "Bu brief'i arşivlemek istediğinizden emin misiniz?",
      confirmLabel: "Arşivle",
      destructive: true,
    });
    if (!ok) return;
    setArchiving(true);
    try {
      await briefApi.archive(briefId, currentAgencyId, accessToken);
      router.push("/dashboard/briefs");
    } finally {
      setArchiving(false);
    }
  };

  const handleSaveFields = async (values: BriefFieldValueIn[]) => {
    if (!accessToken || !currentAgencyId) return;
    const updated = await briefApi.updateFieldValues(briefId, { values }, currentAgencyId, accessToken);
    setBrief(updated);
  };
  void handleSaveFields;

  const loadAnnotations = useCallback(async (d: DeliverableRead) => {
    if (!accessToken || !currentAgencyId) return;
    try {
      const list = await annotationApi.list(briefId, d.id, accessToken, currentAgencyId);
      setAnnotations(list);
    } catch {
      setAnnotations([]);
    }
  }, [accessToken, currentAgencyId, briefId]);

  const handleSelectDeliverable = useCallback((d: DeliverableRead) => {
    setSelectedDeliverable(d);
    setSelectedAssetIndex(0);
    setActiveAnnotationId(null);
    setAnnotationMode(false);
    setNewPinData(null);
    loadAnnotations(d);
  }, [loadAnnotations]);

  // Auto-select first deliverable when switching to Üretim tab
  const handleTabChange = useCallback((tab: TabKey) => {
    setActiveTab(tab);
    if (tab === "uretim" && deliverables.length > 0 && !selectedDeliverable) {
      handleSelectDeliverable(deliverables[0]);
    }
  }, [deliverables, selectedDeliverable, handleSelectDeliverable]);

  // Auto-select first deliverable on page load so previews are immediately visible
  useEffect(() => {
    if (deliverables.length > 0 && !selectedDeliverable) {
      handleSelectDeliverable(deliverables[0]);
    }
  }, [deliverables, selectedDeliverable, handleSelectDeliverable]);

  // Deep-link from a notification: ?tab=uretim / ?panel=comments switches tab once.
  useEffect(() => {
    if (deepLinkTabAppliedRef.current) return;
    const tab = searchParams.get("tab");
    const panel = searchParams.get("panel");
    if (tab === "uretim") {
      setActiveTab("uretim");
      deepLinkTabAppliedRef.current = true;
    } else if (panel === "comments") {
      setActiveTab("yorumlar");
      deepLinkTabAppliedRef.current = true;
    }
  }, [searchParams]);

  // Deep-link ?deliverable={id}: select it once its data has loaded.
  useEffect(() => {
    const deliverableId = searchParams.get("deliverable");
    if (!deliverableId || deliverables.length === 0 || selectedDeliverable?.id === deliverableId) return;
    const target = deliverables.find((d) => d.id === deliverableId);
    if (target) handleSelectDeliverable(target);
  }, [searchParams, deliverables, selectedDeliverable, handleSelectDeliverable]);

  // Deep-link ?annotation={id}: once its deliverable's annotations are loaded, focus + pulse it once.
  useEffect(() => {
    if (deepLinkPulsedRef.current) return;
    const annotationId = searchParams.get("annotation");
    if (!annotationId || annotations.length === 0) return;
    const target = annotations.find((a) => a.id === annotationId);
    if (!target) return;
    deepLinkPulsedRef.current = true;
    const idx = selectedDeliverable?.assets.findIndex((a) => a.id === target.asset_id) ?? -1;
    if (idx >= 0) setSelectedAssetIndex(idx);
    setActiveAnnotationId(target.id);
    setPulseAnnotationId(target.id);
    setTimeout(() => setPulseAnnotationId(null), 2500);
  }, [searchParams, annotations, selectedDeliverable]);

  // Time tracking quick-start: reflects the caller's own active timer (if
  // any), regardless of which brief it's bound to — the server is always
  // the source of truth for whether one is running.
  useEffect(() => {
    if (!accessToken || !currentAgencyId) return;
    const refetchActiveTimer = () => {
      timeEntryApi
        .getActive(currentAgencyId, accessToken)
        .then(setActiveTimer)
        .catch(() => {});
    };
    refetchActiveTimer();
    // Kept in sync with the sidebar GlobalTimerWidget (and vice versa) —
    // stopping/starting a timer from either surface must be reflected in
    // both without a page reload.
    return onTimerChanged(refetchActiveTimer);
  }, [accessToken, currentAgencyId]);

  const timerBoundToThisBrief = activeTimer?.brief_id === briefId;

  const handleToggleTimer = async () => {
    if (!accessToken || !currentAgencyId) return;
    setTimerBusy(true);
    try {
      if (activeTimer && timerBoundToThisBrief) {
        const result = await timeEntryApi.stop(
          activeTimer.id,
          {},
          currentAgencyId,
          accessToken
        );
        setActiveTimer(null);
        emitTimerChanged();
        toast(
          `Zamanlayıcı durduruldu (${Math.round((result.entry.duration_seconds ?? 0) / 60)} dk)`,
          "success"
        );
      } else if (!activeTimer) {
        const entry = await timeEntryApi.start(
          { brief_id: briefId, brand_id: brief?.brand_id ?? undefined, category: "other" },
          currentAgencyId,
          accessToken
        );
        setActiveTimer({
          id: entry.id,
          brief_id: entry.brief_id,
          brand_id: entry.brand_id,
          deliverable_id: entry.deliverable_id,
          task_id: entry.task_id,
          category: entry.category,
          description: entry.description,
          billable: entry.billable,
          started_at: entry.started_at,
        });
        emitTimerChanged();
        toast("Zaman kaydı başlatıldı", "success");
      } else {
        toast("Başka bir zamanlayıcı zaten çalışıyor", "warning");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : "Zamanlayıcı işlemi başarısız", "error");
    } finally {
      setTimerBusy(false);
    }
  };

  const handleCreateAnnotation = async () => {
    if (!accessToken || !currentAgencyId || !selectedDeliverable || !newPinData || !newAnnotationBody.trim()) return;
    const selectedAsset = selectedDeliverable.assets[selectedAssetIndex];
    setSavingAnnotation(true);
    setAnnotationError(null);
    try {
      const data: AnnotationCreate = {
        asset_id: selectedAsset?.id ?? null,
        version_number: selectedDeliverable.version_number,
        x_percent: newPinData.x,
        y_percent: newPinData.y,
        annotation_type: newAnnotationType,
        visibility: newAnnotationVisibility,
        body: newAnnotationBody.trim(),
        mentioned_user_ids: newAnnotationMentionedIds,
      };
      const created = await annotationApi.create(briefId, selectedDeliverable.id, data, accessToken, currentAgencyId);
      setAnnotations((prev) => [...prev, created]);
      setNewPinData(null);
      setNewAnnotationBody("");
      setNewAnnotationMentionedIds([]);
      setActiveAnnotationId(created.id);
    } catch (err: unknown) {
      setAnnotationError(err instanceof Error ? err.message : "Revizyon noktası kaydedilemedi.");
    } finally {
      setSavingAnnotation(false);
    }
  };

  const handleResolveAnnotation = async (annotationId: string) => {
    if (!accessToken || !currentAgencyId || !selectedDeliverable) return;
    try {
      const updated = await annotationApi.resolve(selectedDeliverable.id, annotationId, accessToken, currentAgencyId);
      setAnnotations((prev) => prev.map((a) => a.id === annotationId ? updated : a));
    } catch {
      // silent
    }
  };

  const handleAddReply = async (annotationId: string) => {
    const body = replyBody[annotationId]?.trim();
    if (!accessToken || !currentAgencyId || !selectedDeliverable || !body) return;
    try {
      const reply = await annotationApi.reply(
        selectedDeliverable.id, annotationId,
        { body, visibility: "internal", mentioned_user_ids: replyMentionedIds[annotationId] ?? [] },
        accessToken, currentAgencyId
      );
      setAnnotations((prev) => prev.map((a) =>
        a.id === annotationId
          ? { ...a, replies: [...a.replies, reply] }
          : a
      ));
      setReplyBody((prev) => ({ ...prev, [annotationId]: "" }));
      setReplyMentionedIds((prev) => ({ ...prev, [annotationId]: [] }));
    } catch {
      // silent
    }
  };

  const handleNewAnnotationMentionInsert = (candidate: MentionCandidate) =>
    setNewAnnotationMentionedIds((prev) => (prev.includes(candidate.user_id) ? prev : [...prev, candidate.user_id]));

  const handleReplyMentionInsert = (annotationId: string, candidate: MentionCandidate) =>
    setReplyMentionedIds((prev) => {
      const existing = prev[annotationId] ?? [];
      if (existing.includes(candidate.user_id)) return prev;
      return { ...prev, [annotationId]: [...existing, candidate.user_id] };
    });

  if (loading) return <Skeleton />;

  if (error || !brief) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="rounded-xl border border-danger/20 bg-danger/5 px-5 py-4 text-sm text-danger">
          {error ?? "Brief bulunamadı."}
          <button onClick={loadBrief} className="ml-3 underline">Tekrar dene</button>
        </div>
      </div>
    );
  }

  const nextStatuses = (
    brief.source === "brand_portal" ? NEXT_STATUSES_BRAND_REQUEST : NEXT_STATUSES_AGENCY
  )[brief.status as BriefStatus] ?? [];
  const deadline = brief.deadline
    ? new Date(brief.deadline).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })
    : null;
  const isOverdue =
    brief.deadline &&
    new Date(brief.deadline) < new Date() &&
    brief.status !== "approved" &&
    brief.status !== "archived";
  const canSendApproval = brief.status === "draft" || brief.status === "revision_requested";

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "genel", label: "Genel", icon: <Activity className="w-3.5 h-3.5" /> },
    { key: "brief", label: "Brief Detayı", icon: <FileText className="w-3.5 h-3.5" /> },
    { key: "referanslar", label: "Referanslar", icon: <Link2 className="w-3.5 h-3.5" /> },
    { key: "uretim", label: "Teslimler", icon: <Package2 className="w-3.5 h-3.5" />, count: deliverables.length },
  ];

  return (
    <div className="min-h-screen">
      {/* ── Hero ─────────────────────────────────────────────────── */}
      <div className={`border-b bg-surface/30 transition-colors ${brief.status === "approved" ? "border-success/30 bg-success/[0.02]" : "border-border"}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-8 pt-5 pb-0">
          <button
            onClick={() => router.push("/dashboard/briefs")}
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text transition-colors mb-4"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Brief&apos;ler
          </button>

          {brief.status === "approved" && (
            <div className="status-success flex items-center gap-2 mb-4 px-4 py-2.5 rounded-xl">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <p className="text-sm font-semibold">Brief marka tarafından onaylandı.</p>
            </div>
          )}

          <div className="flex items-start justify-between gap-6 mb-4">
            <div className="flex-1 min-w-0">
              {brand && <p className="text-xs font-semibold text-accent mb-1 uppercase tracking-wide">{brand.name}</p>}
              <h1 className={`text-2xl font-bold leading-tight ${brief.status === "approved" ? "text-success" : "text-text"}`}>{brief.title}</h1>
              {brief.description && (
                <p className="text-sm text-text-muted mt-1.5 line-clamp-2 max-w-2xl">{brief.description}</p>
              )}
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <BriefStatusBadge status={brief.status as BriefStatus} />
                <BriefPriorityBadge priority={brief.priority as BriefPriority} />
                <BriefEstimateBadge briefId={briefId} />
                {brief.source === "brand_portal" && (
                  <span className="status-info inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold">
                    <UserCircle2 className="w-3 h-3" />
                    Marka Tarafından Gönderildi
                  </span>
                )}
                {deadline && (
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${isOverdue ? "bg-danger/10 border-danger/20 text-danger" : "bg-surface-2 border-border text-text-muted"}`}>
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    {deadline}{isOverdue ? " · Gecikti" : ""}
                  </span>
                )}
                <span className="text-xs text-text-muted">Güncellendi {new Date(brief.updated_at).toLocaleDateString("tr-TR")}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
              {brief.status !== "archived" && (
                <button
                  onClick={handleToggleTimer}
                  disabled={timerBusy || (!!activeTimer && !timerBoundToThisBrief)}
                  title={
                    activeTimer && !timerBoundToThisBrief
                      ? "Başka bir zamanlayıcı zaten çalışıyor"
                      : undefined
                  }
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition-colors disabled:opacity-50 ${
                    activeTimer && timerBoundToThisBrief
                      ? "border-danger/40 text-danger hover:bg-danger/10"
                      : "border-border text-text-muted hover:border-accent hover:text-accent"
                  }`}
                >
                  {activeTimer && timerBoundToThisBrief ? (
                    <>
                      <Square className="w-3.5 h-3.5" />
                      Zaman Kaydını Durdur
                    </>
                  ) : (
                    <>
                      <Clock className="w-3.5 h-3.5" />
                      Zaman Kaydı Başlat
                    </>
                  )}
                </button>
              )}
              {brief.status !== "archived" && (
                <button
                  onClick={() => setManualEntryModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border border-border text-text-muted hover:border-accent hover:text-accent transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Manuel Kayıt Ekle
                </button>
              )}
              {nextStatuses.map((s) => (
                <button
                  key={s}
                  onClick={() => handleChangeStatus(s)}
                  disabled={statusChanging}
                  className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors disabled:opacity-50 ${
                    s === "accepted" ? "border-success/40 text-success hover:bg-success/10 hover:border-success" :
                    s === "approved" ? "border-success/40 text-success hover:bg-success/10 hover:border-success" :
                    "border-border text-text-muted hover:border-accent hover:text-accent"
                  }`}
                >
                  {ACTION_LABEL[s]}
                </button>
              ))}
              {brief.status !== "archived" && canSendApproval && (
                <button
                  onClick={() => { setActiveTab("genel"); setTimeout(() => document.querySelector("[data-approval-panel]")?.scrollIntoView({ behavior: "smooth" }), 100); }}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
                  Onaya Gönder
                </button>
              )}
              {brief.status !== "archived" && (
                <>
                  <button
                    onClick={() => router.push(`/dashboard/briefs/${briefId}/edit`)}
                    className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    Düzenle
                  </button>
                  <button
                    onClick={handleArchive}
                    disabled={archiving}
                    className="px-3 py-2 text-xs font-medium rounded-lg border border-border text-text-muted hover:border-danger/40 hover:text-danger disabled:opacity-50 transition-colors"
                  >
                    {archiving ? "…" : "Arşivle"}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Tab bar */}
          <div className="flex items-center gap-0.5 -mb-px overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => handleTabChange(tab.key)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? "border-accent text-accent"
                    : "border-transparent text-text-muted hover:text-text"
                }`}
              >
                {tab.icon}
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className={`inline-flex items-center justify-center w-4 h-4 text-[10px] rounded-full font-bold ${activeTab === tab.key ? "bg-accent text-white" : "bg-surface-2 text-text-muted"}`}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Tab content ──────────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-5">

            {/* GENEL TAB */}
            {activeTab === "genel" && (
              <>
                {participants.length > 0 && (
                  <div className="bg-surface border border-border rounded-xl p-5">
                    <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">Ekip & Sorumlular</h3>
                    <div className="flex flex-wrap gap-2">
                      {participants.map((p) => (
                        <div key={p.id} className="flex items-center gap-2 px-3 py-2 bg-surface-2 rounded-xl border border-border">
                          <div className="w-7 h-7 rounded-full bg-accent/15 flex items-center justify-center text-xs font-bold text-accent flex-shrink-0">
                            {(p.user_name ?? p.user_id)[0].toUpperCase()}
                          </div>
                          <div>
                            <p className="text-xs font-medium text-text">{p.user_name ?? "—"}</p>
                            <p className="text-[10px] text-text-muted">{ROLE_LABELS[p.participant_role ?? "viewer"] ?? "İzleyici"}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {(brief.description_html || brief.description) && (
                  <div className="bg-surface border border-border rounded-xl p-5">
                    <h3 className="text-sm font-semibold text-text mb-3">Brief Özeti</h3>
                    {brief.description_html ? (
                      <RichTextEditor value={brief.description_html} readOnly />
                    ) : (
                      <p className="text-sm text-text-muted leading-relaxed whitespace-pre-wrap">{brief.description}</p>
                    )}
                  </div>
                )}

                {brief.source === "brand_portal" && brief.meta && (
                  <div className="status-info rounded-xl overflow-hidden">
                    <div className="flex items-center gap-2 px-5 py-3.5 border-b border-info/15">
                      <Inbox className="w-4 h-4" />
                      <h3 className="text-sm font-semibold">Marka Talebi Özeti</h3>
                    </div>
                    <div className="divide-y divide-blue-500/10">
                      {brief.meta.campaign_goal && (
                        <div className="px-5 py-3 grid grid-cols-3 gap-3">
                          <p className="text-xs font-medium text-text-muted col-span-1 pt-0.5">Kampanya Amacı</p>
                          <p className="text-xs text-text col-span-2">{brief.meta.campaign_goal}</p>
                        </div>
                      )}
                      {brief.meta.target_audience && (
                        <div className="px-5 py-3 grid grid-cols-3 gap-3">
                          <p className="text-xs font-medium text-text-muted col-span-1 pt-0.5">Hedef Kitle</p>
                          <p className="text-xs text-text col-span-2">{brief.meta.target_audience}</p>
                        </div>
                      )}
                      {(brief.meta.platforms ?? []).length > 0 && (
                        <div className="px-5 py-3 grid grid-cols-3 gap-3">
                          <p className="text-xs font-medium text-text-muted col-span-1 pt-0.5">Platformlar</p>
                          <div className="col-span-2 flex flex-wrap gap-1.5">
                            {(brief.meta.platforms ?? []).map((p: string) => (
                              <span key={p} className="px-2 py-0.5 rounded-full text-[11px] bg-surface border border-border text-text-muted capitalize">{p}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {brief.meta.content_type && (
                        <div className="px-5 py-3 grid grid-cols-3 gap-3">
                          <p className="text-xs font-medium text-text-muted col-span-1 pt-0.5">İçerik Tipi</p>
                          <p className="text-xs text-text col-span-2 capitalize">{brief.meta.content_type}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {(!brief.description && !template && brief.source !== "brand_portal") && (
                  <div className="bg-surface rounded-xl border border-border p-8 text-center">
                    <FileText className="w-10 h-10 text-text-muted mx-auto mb-3" />
                    <h3 className="font-semibold text-text mb-1">Brief detayı yok</h3>
                    <p className="text-sm text-text-muted">Bu brief için henüz detay girilmemiş.</p>
                  </div>
                )}

                {/* ═══ Yorumlara Eklenen Görseller ═══ */}
                {currentAgencyId && accessToken && (
                  <div className="space-y-3 pt-1">
                    <div>
                      <h3 className="text-base font-semibold text-text flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-accent/70" />
                        Yorumlara Eklenen Görseller
                        {commentPreviewAssets.length > 0 && (
                          <span className="text-xs font-normal text-text-muted bg-surface-2 border border-border px-2 py-0.5 rounded-full">
                            {commentPreviewAssets.length} medya
                          </span>
                        )}
                      </h3>
                      <p className="text-xs text-text-muted mt-0.5">
                        Sohbet yorumlarına eklenen dosyalar. Asıl teslim edilen çalışma ve revizyon
                        noktaları için <button type="button" onClick={() => setActiveTab("uretim")} className="text-accent hover:underline font-medium">Teslimler</button> sekmesine bakın.
                      </p>
                    </div>
                    <CommentPreviewGallery
                      assets={commentPreviewAssets}
                      accessToken={accessToken}
                      onGoToComments={() => commentSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                    />
                  </div>
                )}

                {/* ═══ Yorumlar & Revize Notları ═══ */}
                {currentAgencyId && accessToken && (
                  <div ref={commentSectionRef} className="space-y-3 pt-1">
                    <div>
                      <h3 className="text-base font-semibold text-text flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-accent/70" />
                        Yorumlar &amp; Revize Notları
                      </h3>
                      <p className="text-xs text-text-muted mt-0.5">
                        Dahili notlar yalnızca ajans ekibine görünür. Müşteri Görür notlar marka tarafından da okunabilir.
                      </p>
                    </div>
                    <div className="bg-surface rounded-xl border border-border overflow-hidden">
                      <CommentPanel
                        briefId={briefId}
                        agencyId={currentAgencyId}
                        accessToken={accessToken}
                        currentUserId={user?.id}
                        onUploadAttachment={(file) =>
                          commentApi.uploadAttachment(briefId, file, currentAgencyId, accessToken)
                        }
                        onThreadsLoaded={handleThreadsLoaded}
                      />
                    </div>
                    {brief.status !== "archived" && canSendApproval && (
                      <div className="bg-surface rounded-xl border border-border overflow-hidden">
                        <ApprovalPanel
                          briefId={briefId}
                          agencyId={currentAgencyId}
                          accessToken={accessToken}
                          briefStatus={brief.status as BriefStatus}
                          approvals={approvals}
                          versions={versions}
                          onSent={loadBrief}
                          onRevoked={loadBrief}
                        />
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {/* BRIEF DETAYI TAB */}
            {activeTab === "brief" && (
              <>
                {template && template.sections.length > 0 ? (
                  <div className="space-y-4">
                    {template.sections.map((section) => {
                      const sectionValues = brief.field_values.filter((fv) =>
                        section.fields.some((f) => f.id === fv.template_field_id)
                      );
                      if (sectionValues.length === 0) return null;
                      return (
                        <div key={section.id} className="bg-surface border border-border rounded-xl overflow-hidden">
                          <div className="px-5 py-3 border-b border-border bg-surface-2/30">
                            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide">{section.title}</h3>
                          </div>
                          <div className="divide-y divide-border">
                            {sectionValues.map((fv) => {
                              const field = section.fields.find((f) => f.id === fv.template_field_id);
                              return (
                                <div key={fv.id} className="px-5 py-4 grid grid-cols-3 gap-3">
                                  <p className="text-xs font-medium text-text-muted col-span-1 pt-0.5">{field?.label ?? "Alan"}</p>
                                  <div className="col-span-2">
                                    <p className="text-sm text-text leading-relaxed">
                                      {typeof fv.value === "string" ? fv.value : JSON.stringify(fv.value)}
                                    </p>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="bg-surface rounded-xl border border-border p-8 text-center">
                    <FileText className="w-10 h-10 text-text-muted mx-auto mb-3" />
                    <h3 className="font-semibold text-text mb-1">Şablon yok</h3>
                    <p className="text-sm text-text-muted">Bu brief bir şablona bağlı değil.</p>
                  </div>
                )}
              </>
            )}

            {/* REFERANSLAR TAB */}
            {activeTab === "referanslar" && (
              <>
                {brief.source === "brand_portal" && brief.meta && (
                  <>
                    {(brief.meta.reference_links ?? []).length > 0 && (
                      <div className="bg-surface border border-border rounded-xl p-5">
                        <h3 className="text-sm font-semibold text-text mb-3">Referans Linkler</h3>
                        <div className="space-y-2">
                          {(brief.meta.reference_links ?? []).map((link: string, i: number) => (
                            <a key={i} href={link} target="_blank" rel="noopener noreferrer"
                              className="flex items-center gap-2 px-3 py-2 bg-surface-2 rounded-lg border border-border hover:border-accent group transition-colors">
                              <Link2 className="w-3.5 h-3.5 text-text-muted group-hover:text-accent" />
                              <span className="text-xs text-accent truncate">{link}</span>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                    {(brief.meta.cta || brief.meta.brand_tone || brief.meta.publish_date || brief.meta.additional_notes) && (
                      <div className="bg-surface border border-border rounded-xl overflow-hidden">
                        <div className="px-5 py-3 border-b border-border">
                          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Ek Bilgiler</h3>
                        </div>
                        <div className="divide-y divide-border">
                          {brief.meta.cta && (
                            <div className="px-5 py-3 grid grid-cols-3 gap-3">
                              <p className="text-xs font-medium text-text-muted col-span-1">CTA</p>
                              <p className="text-xs text-text col-span-2">{brief.meta.cta}</p>
                            </div>
                          )}
                          {brief.meta.brand_tone && (
                            <div className="px-5 py-3 grid grid-cols-3 gap-3">
                              <p className="text-xs font-medium text-text-muted col-span-1">Marka Tonu</p>
                              <p className="text-xs text-text col-span-2">{brief.meta.brand_tone}</p>
                            </div>
                          )}
                          {brief.meta.publish_date && (
                            <div className="px-5 py-3 grid grid-cols-3 gap-3">
                              <p className="text-xs font-medium text-text-muted col-span-1">Yayın Tarihi</p>
                              <p className="text-xs text-text col-span-2">{new Date(brief.meta.publish_date).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}</p>
                            </div>
                          )}
                          {brief.meta.additional_notes && (
                            <div className="px-5 py-3 grid grid-cols-3 gap-3">
                              <p className="text-xs font-medium text-text-muted col-span-1">Ek Notlar</p>
                              <p className="text-xs text-text col-span-2 whitespace-pre-wrap">{brief.meta.additional_notes}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}

                {currentAgencyId && accessToken && (
                  <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
                    <h3 className="text-sm font-semibold text-text">Dosyalar & Ekler</h3>
                    {brief.status !== "archived" && (
                      <AssetUploader briefId={briefId} agencyId={currentAgencyId} accessToken={accessToken} onUploaded={(asset) => setAssets((prev) => [...prev, asset])} />
                    )}
                    <AssetList assets={assets} agencyId={currentAgencyId} accessToken={accessToken} onDeleted={(id) => setAssets((prev) => prev.filter((a) => a.id !== id))} />
                  </div>
                )}

                {!brief.meta?.reference_links?.length && !assets.length && brief.source !== "brand_portal" && (
                  <div className="bg-surface rounded-xl border border-border p-8 text-center">
                    <Link2 className="w-10 h-10 text-text-muted mx-auto mb-3" />
                    <h3 className="font-semibold text-text mb-1">Referans yok</h3>
                    <p className="text-sm text-text-muted">Dosya yükleyerek veya link ekleyerek referans ekleyebilirsiniz.</p>
                  </div>
                )}
              </>
            )}

            {/* TESLİMLER (ÜRETİM) TAB — Premium Workspace */}
            {activeTab === "uretim" && currentAgencyId && accessToken && (
              <DeliverableWorkspace
                deliverables={deliverables}
                selectedDeliverable={selectedDeliverable}
                selectedAssetIndex={selectedAssetIndex}
                annotations={annotations}
                activeAnnotationId={activeAnnotationId}
                annotationMode={annotationMode}
                newPinData={newPinData}
                newAnnotationBody={newAnnotationBody}
                newAnnotationType={newAnnotationType}
                newAnnotationVisibility={newAnnotationVisibility}
                savingAnnotation={savingAnnotation}
                annotationError={annotationError}
                replyBody={replyBody}
                pulseAnnotationId={pulseAnnotationId}
                showNewDeliverable={showNewDeliverable}
                briefId={briefId}
                agencyId={currentAgencyId}
                accessToken={accessToken}
                briefStatus={brief.status as BriefStatus}
                isArchived={brief.status === "archived"}
                canCreateDeliverable={canCreateDeliverable}
                onSelectDeliverable={handleSelectDeliverable}
                onSelectAsset={setSelectedAssetIndex}
                onToggleAnnotationMode={() => { setAnnotationMode((m) => !m); setNewPinData(null); setAnnotationError(null); }}
                onExitAnnotationMode={() => { setAnnotationMode(false); setNewPinData(null); setAnnotationError(null); }}
                onCanvasClick={(x, y) => setNewPinData({ x, y })}
                onAnnotationClick={(ann) => { setActiveAnnotationId((id) => id === ann.id ? null : ann.id); setAnnotationMode(false); setNewPinData(null); }}
                onCloseAnnotationPopover={() => setActiveAnnotationId(null)}
                onNewAnnotationBodyChange={setNewAnnotationBody}
                onNewAnnotationTypeChange={setNewAnnotationType}
                onNewAnnotationVisibilityChange={setNewAnnotationVisibility}
                onCreateAnnotation={handleCreateAnnotation}
                onCancelNewPin={() => { setNewPinData(null); setNewAnnotationBody(""); setNewAnnotationMentionedIds([]); setAnnotationError(null); }}
                onResolveAnnotation={handleResolveAnnotation}
                onReplyBodyChange={(id, val) => setReplyBody((prev) => ({ ...prev, [id]: val }))}
                onAddReply={handleAddReply}
                onNewAnnotationMentionInsert={handleNewAnnotationMentionInsert}
                onReplyMentionInsert={handleReplyMentionInsert}
                onDeliverableCreated={(d) => { setDeliverables((prev) => [...prev, d]); setShowNewDeliverable(false); handleSelectDeliverable(d); }}
                onDeliverableUpdated={(updated) => { setDeliverables((prev) => prev.map((x) => x.id === updated.id ? updated : x)); setSelectedDeliverable(updated); }}
                onDeliverableDeleted={(id) => { setDeliverables((prev) => prev.filter((x) => x.id !== id)); if (selectedDeliverable?.id === id) { setSelectedDeliverable(null); setAnnotations([]); } }}
                onShowNewDeliverable={() => setShowNewDeliverable(true)}
                onHideNewDeliverable={() => setShowNewDeliverable(false)}
              />
            )}

            {/* YORUMLAR TAB */}
            {activeTab === "yorumlar" && currentAgencyId && accessToken && (
              <div className="bg-surface rounded-xl border border-border overflow-hidden">
                <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text">İç Yorumlar</h3>
                  <span className="text-xs text-text-muted bg-surface-2 px-2 py-0.5 rounded-full border border-border">Yalnızca ajans görür</span>
                </div>
                <div className="p-5">
                  <CommentPanel
                    briefId={briefId}
                    agencyId={currentAgencyId}
                    accessToken={accessToken}
                    currentUserId={user?.id}
                    onUploadAttachment={(file) =>
                      commentApi.uploadAttachment(briefId, file, currentAgencyId, accessToken)
                    }
                    onThreadsLoaded={handleThreadsLoaded}
                  />
                </div>
                {brief.status !== "archived" && canSendApproval && (
                  <div className="border-t border-border p-4">
                    <ApprovalPanel
                      briefId={briefId}
                      agencyId={currentAgencyId}
                      accessToken={accessToken}
                      briefStatus={brief.status as BriefStatus}
                      approvals={approvals}
                      versions={versions}
                      onSent={loadBrief}
                      onRevoked={loadBrief}
                    />
                  </div>
                )}
              </div>
            )}

          </div>

          {/* Right sidebar */}
          <div className="lg:col-span-1">
            <div className="sticky top-4 space-y-4">
              {/* Meta info */}
              <div className="bg-surface rounded-xl border border-border p-4 space-y-2.5">
                <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Bilgiler</h4>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-text-muted">Oluşturulma</span>
                  <span className="text-text font-medium">{new Date(brief.created_at).toLocaleDateString("tr-TR")}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-text-muted">Durum</span>
                  <BriefStatusBadge status={brief.status as BriefStatus} />
                </div>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-text-muted">Öncelik</span>
                  <BriefPriorityBadge priority={brief.priority as BriefPriority} />
                </div>
                {brand && (
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">Marka</span>
                    <span className="text-text font-medium">{brand.name}</span>
                  </div>
                )}
                {assets.length > 0 && (
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">Dosyalar</span>
                    <span className="text-text font-medium">{assets.length}</span>
                  </div>
                )}
                {deliverables.length > 0 && (
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">Deliverable</span>
                    <span className="text-text font-medium">{deliverables.length} ({deliverables.filter(d => d.status === "approved").length} onaylı)</span>
                  </div>
                )}
                {participants.length > 0 && (
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">Ekip</span>
                    <span className="text-text font-medium">{participants.length} kişi</span>
                  </div>
                )}
              </div>

              {/* Brand DNA Summary Card */}
              {brief.brand_id && (
                <div className={`bg-surface rounded-xl border p-4 space-y-2.5 ${
                  dnaSummary?.profile_id ? "border-accent/20" : "border-border"
                }`}>
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Marka DNA</h4>
                    {dnaSummary?.profile_id && (
                      <a
                        href={`/dashboard/brands/${brief.brand_id}`}
                        className="text-[10px] text-accent hover:underline"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Tamamını Gör
                      </a>
                    )}
                  </div>
                  {dnaSummary?.profile_id ? (
                    <>
                      {dnaSummary.status && (
                        <span className={`inline-block text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                          dnaSummary.status === "approved" ? "text-success bg-success/10" : "text-text-muted bg-surface-2"
                        }`}>
                          {dnaSummary.status === "approved" ? "Onaylandı" : dnaSummary.status === "ai_generated" ? "Analiz Edildi" : "İncelenmeli"}
                        </span>
                      )}
                      {dnaSummary.primary_colors && dnaSummary.primary_colors.length > 0 && (
                        <div>
                          <p className="text-[10px] text-text-muted/60 mb-1.5">Renkler</p>
                          <div className="flex gap-1.5 flex-wrap">
                            {dnaSummary.primary_colors.slice(0, 5).map((c, i) => (
                              c.hex && (
                                <div key={i} title={c.hex} className="w-5 h-5 rounded border border-border/50" style={{ backgroundColor: c.hex }} />
                              )
                            ))}
                          </div>
                        </div>
                      )}
                      {dnaSummary.typography && dnaSummary.typography.length > 0 && (
                        <div>
                          <p className="text-[10px] text-text-muted/60 mb-1">Fontlar</p>
                          {dnaSummary.typography.slice(0, 2).map((f, i) => (
                            f.family && (
                              <p key={i} className="text-xs text-text">{f.family}</p>
                            )
                          ))}
                        </div>
                      )}
                      {dnaSummary.dont_rules && dnaSummary.dont_rules.length > 0 && (
                        <div>
                          <p className="text-[10px] text-text-muted/60 mb-1">Dikkat</p>
                          <p className="text-[11px] text-danger/80">{dnaSummary.dont_rules[0]}</p>
                        </div>
                      )}
                      {dnaSummary.key_takeaways && dnaSummary.key_takeaways.length > 0 && (
                        <div>
                          <p className="text-[10px] text-text-muted/60 mb-1">Kritik Kural</p>
                          <p className="text-[11px] text-text">{dnaSummary.key_takeaways[0]}</p>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-text-muted/60">
                      Bu marka için DNA oluşturulmadı.{" "}
                      <a
                        href={`/dashboard/brands/${brief.brand_id}`}
                        className="text-accent hover:underline"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Ekle
                      </a>
                    </p>
                  )}
                </div>
              )}

              {/* Approval panel in sidebar */}
              {currentAgencyId && accessToken && brief.status !== "archived" && canSendApproval && (
                <ApprovalPanel
                  briefId={briefId}
                  agencyId={currentAgencyId}
                  accessToken={accessToken}
                  briefStatus={brief.status as BriefStatus}
                  approvals={approvals}
                  versions={versions}
                  onSent={loadBrief}
                  onRevoked={loadBrief}
                />
              )}

              {/* Production progress */}
              {deliverables.length > 0 && (
                <div className="bg-surface rounded-xl border border-border p-4 space-y-3">
                  <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide">Üretim Durumu</h4>
                  <div className="space-y-2">
                    {[
                      { status: "draft", label: "Taslak", color: "bg-surface-2" },
                      { status: "submitted", label: "İncelemede", color: "bg-info" },
                      { status: "revision_requested", label: "Revizyon", color: "bg-warning" },
                      { status: "approved", label: "Onaylı", color: "bg-success" },
                    ].map(({ status, label, color }) => {
                      const count = deliverables.filter(d => d.status === status).length;
                      if (count === 0) return null;
                      return (
                        <div key={status} className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${color} flex-shrink-0`} />
                          <span className="text-xs text-text-muted flex-1">{label}</span>
                          <span className="text-xs font-semibold text-text">{count}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Activite kısa özeti — yorumlar artık ana içerikte */}
              {deliverables.length > 0 && (
                <div className="bg-surface rounded-xl border border-border p-4">
                  <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">Üretim Özeti</h4>
                  <div className="space-y-2">
                    {deliverables.map((d) => {
                      const cfg = DELIVERABLE_STATUS_CONFIG[d.status] ?? { label: d.status, className: "status-neutral" };
                      return (
                        <div key={d.id} className="flex items-center gap-2 text-xs">
                          <span className={`inline-flex items-center w-1.5 h-1.5 rounded-full flex-shrink-0 ${d.status === "approved" ? "bg-success" : d.status === "revision_requested" ? "bg-warning" : d.status === "submitted" ? "bg-info" : "bg-surface-2 border border-border"}`} />
                          <span className="text-text flex-1 truncate">{d.title}</span>
                          <span className={`text-[10px] ${cfg.className} px-1.5 py-0.5 rounded`}>{cfg.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {currentAgencyId && accessToken && (
        <ManualEntryModal
          isOpen={manualEntryModalOpen}
          onClose={() => setManualEntryModalOpen(false)}
          agencyId={currentAgencyId}
          accessToken={accessToken}
          briefId={briefId}
          brandId={brief.brand_id}
          onCreated={() => emitTimerChanged()}
        />
      )}
    </div>
  );
}
