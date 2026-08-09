export const EVENT_TYPE_CFG: Record<string, { label: string; chip: string; dot: string }> = {
  // Real content calendar item types
  post: { label: "Gönderi", chip: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20", dot: "bg-indigo-400" },
  story: { label: "Hikaye", chip: "bg-purple-500/10 text-purple-400 border-purple-500/20", dot: "bg-purple-400" },
  reels: { label: "Reels", chip: "bg-pink-500/10 text-pink-400 border-pink-500/20", dot: "bg-pink-400" },
  video: { label: "Video", chip: "bg-rose-500/10 text-rose-400 border-rose-500/20", dot: "bg-rose-400" },
  campaign: { label: "Kampanya", chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  blog: { label: "Blog", chip: "bg-teal-500/10 text-teal-400 border-teal-500/20", dot: "bg-teal-400" },
  email: { label: "E-posta", chip: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20", dot: "bg-cyan-400" },
  ad_creative: { label: "Reklam Kreatifi", chip: "bg-orange-500/10 text-orange-400 border-orange-500/20", dot: "bg-orange-400" },
  meeting: { label: "Toplantı", chip: "bg-blue-500/10 text-blue-400 border-blue-500/20", dot: "bg-blue-400" },
  custom: { label: "Özel Etkinlik", chip: "bg-slate-500/10 text-slate-400 border-slate-500/20", dot: "bg-slate-400" },
  // Brief-lifecycle milestones
  brief_start: { label: "Brief Başlangıcı", chip: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", dot: "bg-emerald-400" },
  first_draft: { label: "İlk Taslak", chip: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20", dot: "bg-indigo-400" },
  brand_feedback: { label: "Marka Geri Bildirimi", chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  approval_deadline: { label: "Onay Son Tarihi", chip: "bg-red-500/10 text-red-400 border-red-500/20", dot: "bg-red-400" },
  final_delivery: { label: "Nihai Teslim", chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
  publish_date: { label: "Yayın Tarihi", chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
};

export const STATUS_CFG: Record<string, { label: string; chip: string; dot: string }> = {
  planned: { label: "Planlandı", chip: "bg-surface-2 text-text-muted border-border", dot: "bg-text-muted/40" },
  in_design: { label: "Tasarımda", chip: "bg-blue-500/10 text-blue-400 border-blue-500/20", dot: "bg-blue-400" },
  waiting_approval: { label: "Onay Bekliyor", chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  approved: { label: "Onaylandı", chip: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", dot: "bg-emerald-400" },
  scheduled: { label: "Zamanlandı", chip: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20", dot: "bg-indigo-400" },
  published: { label: "Yayınlandı", chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
  cancelled: { label: "İptal", chip: "bg-danger/10 text-danger border-danger/20", dot: "bg-danger" },
  draft: { label: "Taslak", chip: "bg-surface-2 text-text-muted border-border", dot: "bg-text-muted/40" },
  submitted: { label: "Gönderildi", chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  accepted: { label: "Kabul Edildi", chip: "bg-teal-500/10 text-teal-400 border-teal-500/20", dot: "bg-teal-400" },
  in_production: { label: "Üretimde", chip: "bg-blue-500/10 text-blue-400 border-blue-500/20", dot: "bg-blue-400" },
  ready_for_review: { label: "İncelemeye Hazır", chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
  revision_requested: { label: "Revize İstendi", chip: "bg-orange-500/10 text-orange-400 border-orange-500/20", dot: "bg-orange-400" },
  rejected: { label: "Reddedildi", chip: "bg-danger/10 text-danger border-danger/20", dot: "bg-danger" },
  completed: { label: "Tamamlandı", chip: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20", dot: "bg-emerald-500" },
  archived: { label: "Arşiv", chip: "bg-surface-2 text-text-muted/50 border-border", dot: "bg-text-muted/20" },
  in_review: { label: "İncelemede", chip: "bg-amber-500/10 text-amber-400 border-amber-500/20", dot: "bg-amber-400" },
};

export const PRIORITY_CFG: Record<string, { label: string; className: string }> = {
  urgent: { label: "Acil", className: "text-red-400 bg-red-400/10" },
  high: { label: "Yüksek", className: "text-amber-400 bg-amber-400/10" },
  normal: { label: "Normal", className: "text-blue-400 bg-blue-400/10" },
  low: { label: "Düşük", className: "text-slate-400 bg-slate-400/10" },
};
