"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  publicApprovalApi,
  type PublicApprovalView,
} from "@/lib/api-client";
import { CheckCircle2, RotateCcw, MessageSquare, Clock, XCircle, AlertCircle } from "lucide-react";
import { useLocale } from "@/context/locale-context";
import { LanguageSelector } from "@/components/i18n/language-selector";
import { formatLocalizedDate } from "@/lib/i18n/format";

function fmtDate(iso: string | null | undefined, locale: "en" | "tr"): string {
  if (!iso) return "—";
  return formatLocalizedDate(iso, locale, { day: "numeric", month: "long", year: "numeric" });
}

const PRIORITY_LABEL: Record<string, string> = {
  urgent: "Acil", high: "Yüksek", normal: "Normal", low: "Düşük",
};
const PRIORITY_LABEL_EN: Record<string, string> = {
  urgent: "Urgent", high: "High", normal: "Normal", low: "Low",
};

const PRIORITY_COLOR: Record<string, string> = {
  urgent: "text-red-500", high: "text-amber-500", normal: "text-blue-500", low: "text-gray-400",
};

function StatusBanner({ status, decidedAt, locale }: { status: PublicApprovalView["status"]; decidedAt: string | null; locale: "en" | "tr" }) {
  if (status === "approved") {
    return (
      <div className="flex items-center gap-3 px-5 py-4 rounded-xl bg-emerald-50 border border-emerald-200">
        <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-emerald-700">{locale === "tr" ? "Bu brief onaylandı" : "This brief was approved"}</p>
          {decidedAt && <p className="text-xs text-emerald-600">{locale === "tr" ? `${fmtDate(decidedAt, locale)} tarihinde` : `On ${fmtDate(decidedAt, locale)}`}</p>}
        </div>
      </div>
    );
  }
  if (status === "revision_requested") {
    return (
      <div className="flex items-center gap-3 px-5 py-4 rounded-xl bg-amber-50 border border-amber-200">
        <RotateCcw className="w-5 h-5 text-amber-500 flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold text-amber-700">{locale === "tr" ? "Revizyon talep edildi" : "A revision was requested"}</p>
          {decidedAt && <p className="text-xs text-amber-600">{locale === "tr" ? `${fmtDate(decidedAt, locale)} tarihinde` : `On ${fmtDate(decidedAt, locale)}`}</p>}
        </div>
      </div>
    );
  }
  if (status === "cancelled") {
    return (
      <div className="flex items-center gap-3 px-5 py-4 rounded-xl bg-gray-50 border border-gray-200">
        <XCircle className="w-5 h-5 text-gray-400 flex-shrink-0" />
        <p className="text-sm font-semibold text-gray-600">{locale === "tr" ? "Bu onay talebi iptal edildi" : "This approval request was cancelled"}</p>
      </div>
    );
  }
  if (status === "expired") {
    return (
      <div className="flex items-center gap-3 px-5 py-4 rounded-xl bg-red-50 border border-red-200">
        <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
        <p className="text-sm font-semibold text-red-700">{locale === "tr" ? "Bu onay talebinin süresi doldu" : "This approval request has expired"}</p>
      </div>
    );
  }
  return null;
}

export default function PublicApprovalPage() {
  const { locale } = useLocale();
  const { token } = useParams<{ token: string }>();
  const [approval, setApproval] = useState<PublicApprovalView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [approverName, setApproverName] = useState("");
  const [approverEmail, setApproverEmail] = useState("");
  const [revisionComment, setRevisionComment] = useState("");
  const [comment, setComment] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  const [showRevisionForm, setShowRevisionForm] = useState(false);
  const [showCommentForm, setShowCommentForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await publicApprovalApi.getByToken(token);
      setApproval(data);
    } catch {
      setError(locale === "tr" ? "Bu onay talebi bulunamadı veya süresi dolmuş." : "This approval request could not be found or has expired.");
    } finally {
      setLoading(false);
    }
  }, [locale, token]);

  useEffect(() => { load(); }, [load]);

  const handleApprove = async () => {
    if (!approval) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await publicApprovalApi.approve(token, {
        approver_name: approverName.trim() || undefined,
        approver_email: approverEmail.trim() || undefined,
      });
      setSubmitSuccess(locale === "tr" ? "Brief onaylandı! Ajans bildirim aldı." : "Brief approved. The agency has been notified.");
      await load();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSubmitError(e?.message ?? (locale === "tr" ? "Onay gönderilemedi." : "The approval could not be submitted."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevision = async () => {
    if (!revisionComment.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await publicApprovalApi.requestRevision(token, {
        comment: revisionComment.trim(),
        approver_name: approverName.trim() || undefined,
        approver_email: approverEmail.trim() || undefined,
      });
      setSubmitSuccess(locale === "tr" ? "Revizyon talebiniz iletildi." : "Your revision request was submitted.");
      setShowRevisionForm(false);
      setRevisionComment("");
      await load();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSubmitError(e?.message ?? (locale === "tr" ? "Revizyon gönderilemedi." : "The revision request could not be submitted."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleComment = async () => {
    if (!comment.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await publicApprovalApi.addComment(token, {
        comment: comment.trim(),
        author_name: approverName.trim() || undefined,
        author_email: approverEmail.trim() || undefined,
      });
      setComment("");
      setShowCommentForm(false);
      await load();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSubmitError(e?.message ?? (locale === "tr" ? "Yorum gönderilemedi." : "The comment could not be submitted."));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-gray-200" />
          <div className="h-4 w-40 bg-gray-200 rounded" />
        </div>
      </div>
    );
  }

  if (error || !approval) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-red-100 p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-lg font-bold text-gray-900 mb-2">{locale === "tr" ? "Onay Talebi Bulunamadı" : "Approval request not found"}</h1>
          <p className="text-sm text-gray-500">{error ?? (locale === "tr" ? "Bu link geçersiz ya da süresi dolmuş." : "This link is invalid or has expired.")}</p>
        </div>
      </div>
    );
  }

  const isPending = approval.status === "pending";
  const expiresAt = new Date(approval.expires_at);
  const timeLeft = expiresAt.getTime() - Date.now();
  const hoursLeft = Math.floor(timeLeft / 3600000);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold">F</span>
            </div>
            <span className="text-sm font-semibold text-gray-900">PostPiloter {locale === "tr" ? "Onay Portalı" : "Approval Portal"}</span>
          </div>
          <LanguageSelector compact />
          {isPending && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Clock className="w-3.5 h-3.5" />
              {hoursLeft > 0 ? (locale === "tr" ? `${hoursLeft} saat kaldı` : `${hoursLeft} hours left`) : (locale === "tr" ? "Süresi yakında dolacak" : "Expires soon")}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        {/* Status banner */}
        {!isPending && (
          <StatusBanner status={approval.status} decidedAt={approval.decided_at} locale={locale} />
        )}

        {/* Success message */}
        {submitSuccess && (
          <div className="flex items-center gap-3 px-5 py-4 rounded-xl bg-emerald-50 border border-emerald-200">
            <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
            <p className="text-sm font-medium text-emerald-700">{submitSuccess}</p>
          </div>
        )}

        {/* Brief card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-50">
            {approval.brand_name && (
              <p className="text-xs font-semibold text-indigo-600 mb-1 uppercase tracking-wide">{approval.brand_name}</p>
            )}
            <h1 className="text-xl font-bold text-gray-900 leading-snug">{approval.brief_title}</h1>
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <span className={`text-xs font-medium ${PRIORITY_COLOR[approval.brief_priority] ?? "text-gray-500"}`}>
                {(locale === "tr" ? PRIORITY_LABEL : PRIORITY_LABEL_EN)[approval.brief_priority] ?? approval.brief_priority}
              </span>
              {approval.brief_deadline && (
                <span className="text-xs text-gray-500">
                  {locale === "tr" ? "Termin" : "Due"}: {fmtDate(approval.brief_deadline, locale)}
                </span>
              )}
              {approval.template_name && (
                <span className="text-xs text-gray-500">{locale === "tr" ? "Şablon" : "Template"}: {approval.template_name}</span>
              )}
              <span className="text-xs text-gray-400">v{approval.version_number}</span>
            </div>
          </div>

          {approval.brief_description && (
            <div className="px-6 py-4 border-b border-gray-50">
              <p className="text-sm text-gray-600 leading-relaxed">{approval.brief_description}</p>
            </div>
          )}

          {/* Field sections */}
          {approval.sections.map((section, si) => (
            <div key={si} className="border-b border-gray-50 last:border-0">
              <div className="px-6 py-3 bg-gray-50/50">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{section.title}</p>
                {section.description && <p className="text-xs text-gray-400 mt-0.5">{section.description}</p>}
              </div>
              <div className="divide-y divide-gray-50">
                {section.fields.filter(f => f.value !== null && f.value !== undefined && f.value !== "").map((field, fi) => (
                  <div key={fi} className="px-6 py-3 grid grid-cols-3 gap-4">
                    <p className="text-xs font-medium text-gray-500 col-span-1 pt-0.5">{field.label}</p>
                    <div className="col-span-2">
                      {Array.isArray(field.value) ? (
                        <div className="flex flex-wrap gap-1.5">
                          {(field.value as string[]).map((v, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-700 capitalize">{v}</span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-gray-800 leading-relaxed">
                          {typeof field.value === "string" ? field.value : JSON.stringify(field.value)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Approver identity fields */}
        {isPending && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <p className="text-sm font-semibold text-gray-900 mb-4">Bilgileriniz (opsiyonel)</p>
            <div className="grid grid-cols-2 gap-3">
              <input
                value={approverName}
                onChange={(e) => setApproverName(e.target.value)}
                placeholder={locale === "tr" ? "Adınız" : "Your name"}
                className="px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-400"
              />
              <input
                value={approverEmail}
                onChange={(e) => setApproverEmail(e.target.value)}
                placeholder={locale === "tr" ? "E-posta adresiniz" : "Your email address"}
                type="email"
                className="px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-400"
              />
            </div>
          </div>
        )}

        {/* Action buttons */}
        {isPending && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={handleApprove}
                disabled={submitting}
                className="flex items-center justify-center gap-2 px-5 py-3.5 bg-emerald-500 hover:bg-emerald-600 text-white font-semibold rounded-xl shadow-sm disabled:opacity-60 transition-colors"
              >
                <CheckCircle2 className="w-4 h-4" />
                {submitting ? (locale === "tr" ? "Gönderiliyor…" : "Submitting…") : (locale === "tr" ? "Onayla" : "Approve")}
              </button>
              <button
                onClick={() => { setShowRevisionForm(!showRevisionForm); setShowCommentForm(false); }}
                className="flex items-center justify-center gap-2 px-5 py-3.5 bg-amber-50 hover:bg-amber-100 text-amber-700 font-semibold rounded-xl border border-amber-200 transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                {locale === "tr" ? "Revizyon İste" : "Request revision"}
              </button>
            </div>

            {showRevisionForm && (
              <div className="bg-white rounded-2xl border border-amber-200 p-5 space-y-3">
                <p className="text-sm font-semibold text-gray-800">{locale === "tr" ? "Revizyon nedeni" : "Revision reason"}</p>
                <textarea
                  value={revisionComment}
                  onChange={(e) => setRevisionComment(e.target.value)}
                  placeholder={locale === "tr" ? "Hangi konuların revize edilmesini istiyorsunuz?" : "What would you like to be revised?"}
                  rows={4}
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-amber-500/25 focus:border-amber-400"
                />
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setShowRevisionForm(false)} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors">{locale === "tr" ? "İptal" : "Cancel"}</button>
                  <button
                    onClick={handleRevision}
                    disabled={submitting || !revisionComment.trim()}
                    className="px-4 py-2 text-sm font-semibold text-white bg-amber-500 hover:bg-amber-600 rounded-xl disabled:opacity-50 transition-colors"
                  >
                    {submitting ? (locale === "tr" ? "Gönderiliyor…" : "Submitting…") : (locale === "tr" ? "Revizyon Talebini Gönder" : "Submit revision request")}
                  </button>
                </div>
              </div>
            )}

            {submitError && (
              <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-xl">
                <p className="text-sm text-red-600">{submitError}</p>
              </div>
            )}
          </div>
        )}

        {/* Comments */}
        {approval.comments.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-50">
              <p className="text-sm font-semibold text-gray-900">{locale === "tr" ? "Yorumlar" : "Comments"}</p>
            </div>
            <div className="divide-y divide-gray-50">
              {approval.comments.map((c) => (
                <div key={c.id} className="px-5 py-4">
                  <div className="flex items-center gap-2 mb-1.5">
                    <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center text-[10px] font-bold text-indigo-600">
                      {(c.author_name ?? c.author_email ?? "?")[0].toUpperCase()}
                    </div>
                    <span className="text-xs font-semibold text-gray-800">{c.author_name ?? c.author_email ?? "Anonim"}</span>
                    <span className="text-[11px] text-gray-400 ml-auto">{formatLocalizedDate(c.created_at, locale)}</span>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed pl-8">{c.comment}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Add comment */}
        {isPending && (
          <div>
            {!showCommentForm ? (
              <button
                onClick={() => setShowCommentForm(true)}
                className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                <MessageSquare className="w-4 h-4" />
                {locale === "tr" ? "Yorum ekle" : "Add comment"}
              </button>
            ) : (
              <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-3">
                <p className="text-sm font-semibold text-gray-800">{locale === "tr" ? "Yorum ekle" : "Add comment"}</p>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder={locale === "tr" ? "Yorumunuzu yazın…" : "Write your comment…"}
                  rows={3}
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/25 focus:border-indigo-400"
                />
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setShowCommentForm(false)} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors">{locale === "tr" ? "İptal" : "Cancel"}</button>
                  <button
                    onClick={handleComment}
                    disabled={submitting || !comment.trim()}
                    className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl disabled:opacity-50 transition-colors"
                  >
                    {submitting ? (locale === "tr" ? "Gönderiliyor…" : "Submitting…") : (locale === "tr" ? "Gönder" : "Send")}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="text-center py-4">
          <p className="text-xs text-gray-400">
            {locale === "tr" ? `Bu link ${fmtDate(approval.expires_at, locale)} tarihine kadar geçerlidir.` : `This link is valid until ${fmtDate(approval.expires_at, locale)}.`}
          </p>
        </div>
      </div>
    </div>
  );
}
