import type { Locale } from "./config";

interface NotificationInput {
  event_type: string;
  title: string;
  body: string;
  payload?: Record<string, unknown>;
}

const titles: Record<string, [string, string]> = {
  "brief.created": ["Brief created", "Brief oluşturuldu"],
  "brief.updated": ["Brief updated", "Brief güncellendi"],
  "brief.submitted_for_approval": ["Brief submitted for approval", "Brief onaya gönderildi"],
  "brief.requested": ["New brief requested", "Yeni brief istendi"],
  "brief.accepted": ["Brief accepted", "Brief kabul edildi"],
  "brief.production_started": ["Production started", "Üretim başladı"],
  "brief.ready_for_review": ["Ready for review", "İncelemeye hazır"],
  "brief.revision_requested": ["Revision requested", "Revizyon istendi"],
  "brief.approved": ["Brief approved", "Brief onaylandı"],
  "brief.rejected": ["Brief rejected", "Brief reddedildi"],
  "brief.completed": ["Brief completed", "Brief tamamlandı"],
  "brief.assigned": ["Brief assigned", "Brief atandı"],
  "brief.overdue": ["Brief overdue", "Brief gecikti"],
  "comment.added": ["New comment", "Yeni yorum"],
  "file.uploaded": ["New file", "Yeni dosya"],
  "calendar.item_created": ["Calendar item created", "Takvim öğesi oluşturuldu"],
  "calendar.item_due": ["Calendar item due", "Takvim öğesinin zamanı geldi"],
  "calendar.item_published": ["Content published", "İçerik yayınlandı"],
  "user.invited": ["Invitation sent", "Davet gönderildi"],
  "subscription.payment_failed": ["Payment failed", "Ödeme başarısız"],
  "subscription.changed": ["Subscription updated", "Abonelik güncellendi"],
  "deliverable.submitted": ["Deliverable submitted", "Teslimat gönderildi"],
  "deliverable.approved": ["Deliverable approved", "Teslimat onaylandı"],
  "deliverable.revision_requested": ["Deliverable revision requested", "Teslimat için revizyon istendi"],
  "public_approval.approved": ["Public approval completed", "Dış onay tamamlandı"],
  "public_approval.revision_requested": ["Public revision requested", "Dış onayda revizyon istendi"],
  "milestone.assigned": ["Task assigned", "Görev atandı"],
  "annotation.created": ["Annotation added", "İşaretleme eklendi"],
  "annotation.resolved": ["Annotation resolved", "İşaretleme çözüldü"],
  "annotation.replied": ["Annotation reply", "İşaretlemeye yanıt"],
  "annotation.reopened": ["Annotation reopened", "İşaretleme yeniden açıldı"],
  "mention.in_comment": ["You were mentioned in a comment", "Bir yorumda etiketlendiniz"],
  "mention.in_annotation": ["You were mentioned in an annotation", "Bir işaretlemede etiketlendiniz"],
  "invoice.sent": ["Invoice sent", "Fatura gönderildi"],
  "invoice.approval_pending": ["Invoice awaiting approval", "Fatura onay bekliyor"],
  "invoice.send_failed": ["Invoice could not be sent", "Fatura gönderilemedi"],
  "invoice.overdue": ["Invoice overdue", "Fatura gecikti"],
  "invoice.due_soon": ["Invoice due soon", "Faturanın vadesi yaklaşıyor"],
  "invoice.payment_received": ["Payment received", "Ödeme alındı"],
  "time_off.approved": ["Time off approved", "İzin onaylandı"],
  "time_off.rejected": ["Time off rejected", "İzin reddedildi"],
  "capacity.over_threshold": ["Capacity threshold exceeded", "Kapasite eşiği aşıldı"],
};

function value(payload: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const candidate = payload[key];
    if (typeof candidate === "string" && candidate.trim()) return candidate;
  }
  return "";
}

export function localizeNotification(input: NotificationInput, locale: Locale): { title: string; body: string } {
  const pair = titles[input.event_type];
  if (!pair) return { title: input.title, body: input.body };
  const payload = input.payload ?? {};
  const subject = value(payload, "brief_title", "deliverable_title", "task_title", "invoice_number", "brand_name");
  const actor = value(payload, "actor_name", "user_name", "inviter_name");
  const title = pair[locale === "tr" ? 1 : 0];
  if (locale === "tr") {
    const context = subject ? `“${subject}”` : "İlgili kayıt";
    return { title, body: actor ? `${actor}, ${context} kaydında bir güncelleme yaptı.` : `${context} için yeni bir güncelleme var.` };
  }
  const context = subject ? `“${subject}”` : "The related item";
  return { title, body: actor ? `${actor} updated ${context}.` : `${context} has a new update.` };
}
