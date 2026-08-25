"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  publicApprovalApi,
  publicBrandingApi,
  type PublicApprovalView,
  type PublicBrandingView,
  type ApprovalCommentRead,
} from "@/lib/api-client";
import { useLocale } from "@/context/locale-context";
import { LanguageSelector } from "@/components/i18n/language-selector";
import { formatLocalizedDate } from "@/lib/i18n/format";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function _assetUrl(url: string | null): string | null {
  if (!url) return null;
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}

// ── Status helpers ─────────────────────────────────────────────────────────────

function statusLabel(
  status: PublicApprovalView["status"], locale: "en" | "tr"
): { text: string; color: string; bg: string } {
  switch (status) {
    case "approved":
      return { text: locale === "tr" ? "Onaylandı" : "Approved", color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200" };
    case "revision_requested":
      return { text: locale === "tr" ? "Revizyon İstendi" : "Revision requested", color: "text-amber-700", bg: "bg-amber-50 border-amber-200" };
    case "pending":
      return { text: locale === "tr" ? "Onay Bekliyor" : "Awaiting approval", color: "text-blue-700", bg: "bg-blue-50 border-blue-200" };
    case "cancelled":
      return { text: locale === "tr" ? "İptal Edildi" : "Cancelled", color: "text-zinc-600", bg: "bg-zinc-50 border-zinc-200" };
    case "expired":
      return { text: locale === "tr" ? "Süresi Doldu" : "Expired", color: "text-red-700", bg: "bg-red-50 border-red-200" };
  }
}

function priorityLabel(p: string, locale: "en" | "tr") {
  switch (p) {
    case "urgent": return locale === "tr" ? "Acil" : "Urgent";
    case "high": return locale === "tr" ? "Yüksek" : "High";
    case "medium": return locale === "tr" ? "Orta" : "Medium";
    case "low": return locale === "tr" ? "Düşük" : "Low";
    default: return p;
  }
}

function priorityColor(p: string) {
  switch (p) {
    case "urgent": return "bg-red-100 text-red-700";
    case "high": return "bg-orange-100 text-orange-700";
    case "medium": return "bg-blue-100 text-blue-700";
    default: return "bg-zinc-100 text-zinc-600";
  }
}

function formatDate(iso: string, locale: "en" | "tr") {
  return formatLocalizedDate(iso, locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-lg bg-zinc-100 ${className ?? ""}`} />
  );
}

function LoadingSkeleton() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-start justify-center pt-16 px-4">
      <div className="w-full max-w-2xl space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-6 w-64" />
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 p-8 space-y-4">
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-40" />
          <div className="pt-4 space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Terminal state screens ─────────────────────────────────────────────────────

function GoneScreen({ title, body }: { title: string; body: string }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center px-4">
      <div className="text-center max-w-sm space-y-4">
        <div className="mx-auto w-16 h-16 bg-zinc-100 rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-zinc-800">{title}</h1>
        <p className="text-sm text-zinc-500">{body}</p>
      </div>
    </div>
  );
}

function DecidedScreen({ approval, locale }: { approval: PublicApprovalView; locale: "en" | "tr" }) {
  const st = statusLabel(approval.status, locale);
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center px-4">
      <div className="text-center max-w-sm space-y-4">
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium ${st.bg} ${st.color}`}>
          {st.text}
        </div>
        <h1 className="text-xl font-semibold text-zinc-800">
          {locale === "tr" ? <>&ldquo;{approval.brief_title}&rdquo; briefiniz için karar verildi.</> : <>A decision was recorded for &ldquo;{approval.brief_title}&rdquo;.</>}
        </h1>
        {approval.decided_at && (
          <p className="text-sm text-zinc-500">{formatDate(approval.decided_at, locale)}</p>
        )}
      </div>
    </div>
  );
}

// ── Field renderer ─────────────────────────────────────────────────────────────

function FieldValue({ value, type, locale }: { value: unknown; type: string; locale: "en" | "tr" }) {
  if (value === null || value === undefined || value === "") {
    return <span className="text-zinc-400 italic text-sm">{locale === "tr" ? "Boş bırakıldı" : "Not provided"}</span>;
  }
  if (type === "textarea" || type === "rich_text") {
    return (
      <p className="text-sm text-zinc-700 leading-relaxed whitespace-pre-wrap">{String(value)}</p>
    );
  }
  if (Array.isArray(value)) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {(value as string[]).map((v, i) => (
          <span key={i} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            {v}
          </span>
        ))}
      </div>
    );
  }
  if (type === "date") {
    try {
      return <span className="text-sm text-zinc-700">{formatLocalizedDate(String(value), locale, { year: "numeric", month: "numeric", day: "numeric" })}</span>;
    } catch {
      return <span className="text-sm text-zinc-700">{String(value)}</span>;
    }
  }
  if (type === "url") {
    return (
      <a href={String(value)} target="_blank" rel="noopener noreferrer"
        className="text-sm text-blue-600 hover:underline break-all">
        {String(value)}
      </a>
    );
  }
  return <span className="text-sm text-zinc-700">{String(value)}</span>;
}

// ── Comment ───────────────────────────────────────────────────────────────────

function Comment({ c, locale }: { c: ApprovalCommentRead; locale: "en" | "tr" }) {
  const initials = c.author_name
    ? c.author_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()
    : "?";
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center text-white text-xs font-semibold">
        {initials}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-zinc-800">
            {c.author_name ?? (locale === "tr" ? "Anonim" : "Anonymous")}
          </span>
          <span className="text-xs text-zinc-400">{formatDate(c.created_at, locale)}</span>
        </div>
        <p className="mt-0.5 text-sm text-zinc-600 leading-relaxed">{c.comment}</p>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type PageState = "loading" | "error_gone" | "error_revoked" | "error_expired" | "decided" | "pending";

export default function ApprovalPortalPage() {
  const { locale } = useLocale();
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [state, setState] = useState<PageState>("loading");
  const [approval, setApproval] = useState<PublicApprovalView | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [branding, setBranding] = useState<PublicBrandingView | null>(null);

  // Approve form
  const [approverName, setApproverName] = useState("");
  const [approverEmail, setApproverEmail] = useState("");

  // Revision form
  const [showRevision, setShowRevision] = useState(false);
  const [revisionComment, setRevisionComment] = useState("");
  const [revisionName, setRevisionName] = useState("");
  const [revisionEmail, setRevisionEmail] = useState("");

  // Comment form
  const [commentText, setCommentText] = useState("");
  const [commentName, setCommentName] = useState("");
  const [commentEmail, setCommentEmail] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [comments, setComments] = useState<ApprovalCommentRead[]>([]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      publicApprovalApi.getByToken(token),
      publicBrandingApi.getByApprovalToken(token).catch(() => null),
    ]).then(([data, brandingData]) => {
      setApproval(data);
      setComments(data.comments ?? []);
      // Always apply branding: the API now resolves to the agency's own
      // override when is_branded=true, or the platform's default identity
      // as a fallback when it's false — either way there's real branding
      // to render, not just a bare generic page.
      if (brandingData) setBranding(brandingData);
      if (data.status === "pending") setState("pending");
      else setState("decided");
    }).catch((err) => {
      const status = err?.status ?? 0;
      if (status === 404) setState("error_gone");
      else if (status === 410) {
        const msg: string = err?.message ?? "";
        if (msg.toLowerCase().includes("revok")) setState("error_revoked");
        else setState("error_expired");
      } else {
        setErrorMsg(err?.message ?? (locale === "tr" ? "Bir hata oluştu." : "Something went wrong."));
        setState("error_gone");
      }
    });
  }, [locale, token]);

  async function handleApprove() {
    if (!token) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      await publicApprovalApi.approve(token, {
        approver_name: approverName || undefined,
        approver_email: approverEmail || undefined,
      });
      const updated = await publicApprovalApi.getByToken(token);
      setApproval(updated);
      setState("decided");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSubmitError(e?.message ?? (locale === "tr" ? "İşlem başarısız oldu." : "The action could not be completed."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevision() {
    if (!token || !revisionComment.trim()) {
      setSubmitError(locale === "tr" ? "Revizyon notu zorunludur." : "A revision note is required.");
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    try {
      await publicApprovalApi.requestRevision(token, {
        comment: revisionComment,
        approver_name: revisionName || undefined,
        approver_email: revisionEmail || undefined,
      });
      const updated = await publicApprovalApi.getByToken(token);
      setApproval(updated);
      setState("decided");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSubmitError(e?.message ?? (locale === "tr" ? "İşlem başarısız oldu." : "The action could not be completed."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAddComment() {
    if (!token || !commentText.trim()) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      const newComment = await publicApprovalApi.addComment(token, {
        comment: commentText,
        author_name: commentName || undefined,
        author_email: commentEmail || undefined,
      });
      setComments((prev) => [...prev, newComment]);
      setCommentText("");
      setCommentName("");
      setCommentEmail("");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSubmitError(e?.message ?? (locale === "tr" ? "Yorum gönderilemedi." : "The comment could not be submitted."));
    } finally {
      setSubmitting(false);
    }
  }

  // ── Render states ────────────────────────────────────────────────────────────

  if (state === "loading") return <LoadingSkeleton />;

  if (state === "error_gone")
    return <GoneScreen title={locale === "tr" ? "Onay linki bulunamadı" : "Approval link not found"} body={errorMsg || (locale === "tr" ? "Bu link geçersiz veya silinmiş olabilir." : "This link may be invalid or deleted.")} />;

  if (state === "error_revoked")
    return <GoneScreen title={locale === "tr" ? "Bu onay linki iptal edildi" : "This approval link was cancelled"} body={locale === "tr" ? "Ajansınızla iletişime geçin." : "Contact your agency for a new link."} />;

  if (state === "error_expired")
    return <GoneScreen title={locale === "tr" ? "Bu onay linkinin süresi doldu" : "This approval link has expired"} body={locale === "tr" ? "Ajansınızdan yeni bir link isteyin." : "Ask your agency for a new link."} />;

  if (!approval) return null;

  if (state === "decided") return <DecidedScreen approval={approval} locale={locale} />;

  const st = statusLabel(approval.status, locale);
  const primaryColor = branding?.primary_color ?? "#6D28D9";
  const logoUrl = _assetUrl(branding?.logo_url ?? null);
  const brandDisplayName = branding?.brand_name ?? branding?.agency_name ?? "PostPiloter";

  // ── Active pending portal ─────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-md border-b border-zinc-200">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {logoUrl ? (
              <img src={logoUrl} alt={brandDisplayName} className="h-8 w-auto max-w-[100px] object-contain" />
            ) : (
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ background: `linear-gradient(135deg, ${primaryColor}, ${branding?.secondary_color ?? primaryColor})` }}
              >
                <span className="text-white text-xs font-bold">
                  {(brandDisplayName[0] ?? "F").toUpperCase()}
                </span>
              </div>
            )}
            <span className="font-semibold text-zinc-800 text-sm">{brandDisplayName}</span>
          </div>
          <span className={`inline-flex items-center px-3 py-1 rounded-full border text-xs font-medium ${st.bg} ${st.color}`}>
            {st.text}
          </span>
          <LanguageSelector compact />
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* Brief meta */}
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 p-6 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs text-zinc-500 uppercase tracking-wide font-medium mb-1">
                {approval.brand_name ?? "Brief"}
              </p>
              <h1 className="text-xl font-bold text-zinc-900 leading-snug">
                {approval.brief_title}
              </h1>
            </div>
            <span className={`flex-shrink-0 inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium ${priorityColor(approval.brief_priority)}`}>
              {priorityLabel(approval.brief_priority, locale)}
            </span>
          </div>

          {approval.brief_description && (
            <p className="text-sm text-zinc-600 leading-relaxed">{approval.brief_description}</p>
          )}

          <div className="flex flex-wrap gap-4 pt-1 text-xs text-zinc-500">
            {approval.template_name && (
              <span className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {approval.template_name}
              </span>
            )}
            {approval.brief_deadline && (
              <span className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {formatLocalizedDate(approval.brief_deadline, locale, { year: "numeric", month: "numeric", day: "numeric" })}
              </span>
            )}
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a2 2 0 012-2z" />
              </svg>
              v{approval.version_number}
            </span>
          </div>
        </div>

        {/* Brief sections */}
        {approval.sections.map((section, si) => (
          <div key={si} className="bg-white rounded-2xl shadow-sm border border-zinc-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-100 bg-zinc-50/50">
              <h2 className="font-semibold text-zinc-800 text-sm">{section.title}</h2>
              {section.description && (
                <p className="text-xs text-zinc-500 mt-0.5">{section.description}</p>
              )}
            </div>
            <div className="divide-y divide-zinc-100">
              {section.fields.map((field, fi) => (
                <div key={fi} className="px-6 py-4">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-xs font-medium text-zinc-700">{field.label}</span>
                    {field.is_required && (
                      <span className="text-xs text-red-400">*</span>
                    )}
                  </div>
                  <FieldValue value={field.value} type={field.field_type} locale={locale} />
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* Comments */}
        {comments.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 p-6 space-y-4">
            <h2 className="text-sm font-semibold text-zinc-800">{locale === "tr" ? "Yorumlar" : "Comments"}</h2>
            <div className="space-y-4">
              {comments.map((c) => (
                <Comment key={c.id} c={c} locale={locale} />
              ))}
            </div>
          </div>
        )}

        {/* Add comment */}
        <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 p-6 space-y-3">
          <h2 className="text-sm font-semibold text-zinc-800">{locale === "tr" ? "Yorum Ekle" : "Add comment"}</h2>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder={locale === "tr" ? "Adınız" : "Your name"}
              value={commentName}
              onChange={(e) => setCommentName(e.target.value)}
              className="col-span-1 text-sm border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400"
            />
            <input
              type="email"
              placeholder={locale === "tr" ? "E-posta (isteğe bağlı)" : "Email (optional)"}
              value={commentEmail}
              onChange={(e) => setCommentEmail(e.target.value)}
              className="col-span-1 text-sm border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400"
            />
          </div>
          <textarea
            rows={3}
            placeholder={locale === "tr" ? "Yorumunuzu yazın..." : "Write your comment…"}
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400"
          />
          <button
            onClick={handleAddComment}
            disabled={submitting || !commentText.trim()}
            className="text-sm font-medium text-violet-700 hover:text-violet-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {locale === "tr" ? "Yorum Gönder" : "Send comment"}
          </button>
        </div>

        {/* Action panel */}
        {!showRevision ? (
          <div className="bg-white rounded-2xl shadow-sm border border-zinc-200 p-6 space-y-4">
            <h2 className="text-sm font-semibold text-zinc-800">{locale === "tr" ? "Kararınız" : "Your decision"}</h2>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder={locale === "tr" ? "Adınız (isteğe bağlı)" : "Your name (optional)"}
                value={approverName}
                onChange={(e) => setApproverName(e.target.value)}
                className="col-span-1 text-sm border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400"
              />
              <input
                type="email"
                placeholder={locale === "tr" ? "E-posta (isteğe bağlı)" : "Email (optional)"}
                value={approverEmail}
                onChange={(e) => setApproverEmail(e.target.value)}
                className="col-span-1 text-sm border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400"
              />
            </div>
            {submitError && (
              <p className="text-xs text-red-600">{submitError}</p>
            )}
            <div className="flex gap-3">
              <button
                onClick={handleApprove}
                disabled={submitting}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-white text-sm font-semibold rounded-xl transition-opacity disabled:opacity-60 disabled:cursor-not-allowed shadow-sm"
                style={{ background: primaryColor }}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                {locale === "tr" ? "Onayla" : "Approve"}
              </button>
              <button
                onClick={() => { setShowRevision(true); setSubmitError(""); }}
                disabled={submitting}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-800 text-sm font-semibold rounded-xl transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                {locale === "tr" ? "Revizyon İste" : "Request revision"}
              </button>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-2xl shadow-sm border border-amber-200 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-zinc-800">{locale === "tr" ? "Revizyon Talebi" : "Revision request"}</h2>
              <button
                onClick={() => { setShowRevision(false); setSubmitError(""); }}
                className="text-xs text-zinc-400 hover:text-zinc-600 transition-colors"
              >
                {locale === "tr" ? "İptal" : "Cancel"}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder={locale === "tr" ? "Adınız (isteğe bağlı)" : "Your name (optional)"}
                value={revisionName}
                onChange={(e) => setRevisionName(e.target.value)}
                className="col-span-1 text-sm border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400"
              />
              <input
                type="email"
                placeholder={locale === "tr" ? "E-posta (isteğe bağlı)" : "Email (optional)"}
                value={revisionEmail}
                onChange={(e) => setRevisionEmail(e.target.value)}
                className="col-span-1 text-sm border border-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400"
              />
            </div>
            <textarea
              rows={4}
              placeholder={locale === "tr" ? "Revizyon notunuzu yazın... (zorunlu)" : "Describe the requested changes… (required)"}
              value={revisionComment}
              onChange={(e) => setRevisionComment(e.target.value)}
              className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400"
            />
            {submitError && (
              <p className="text-xs text-red-600">{submitError}</p>
            )}
            <button
              onClick={handleRevision}
              disabled={submitting || !revisionComment.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-60 disabled:cursor-not-allowed shadow-sm"
            >
              {submitting ? (locale === "tr" ? "Gönderiliyor..." : "Submitting…") : (locale === "tr" ? "Revizyon Talebini Gönder" : "Submit revision request")}
            </button>
          </div>
        )}

        {/* Expiry note */}
        <p className="text-center text-xs text-zinc-400 pb-8">
          {locale === "tr" ? `Bu link ${formatDate(approval.expires_at, locale)} tarihine kadar geçerlidir.` : `This link is valid until ${formatDate(approval.expires_at, locale)}.`}
        </p>
      </main>
    </div>
  );
}
