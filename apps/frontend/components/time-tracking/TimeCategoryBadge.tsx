import type { TimeEntryCategory } from "@/lib/api-client";

export const TIME_CATEGORY_LABEL: Record<TimeEntryCategory, string> = {
  design: "Tasarım",
  copywriting: "Metin Yazarlığı",
  social_media: "Sosyal Medya",
  client_meeting: "Müşteri Toplantısı",
  internal_meeting: "İç Toplantı",
  revision: "Revizyon",
  research: "Araştırma",
  reporting: "Raporlama",
  project_management: "Proje Yönetimi",
  other: "Diğer",
};

export const TIME_CATEGORY_OPTIONS: { value: TimeEntryCategory; label: string }[] =
  (Object.keys(TIME_CATEGORY_LABEL) as TimeEntryCategory[]).map((value) => ({
    value,
    label: TIME_CATEGORY_LABEL[value],
  }));

const CATEGORY_DOT: Record<TimeEntryCategory, string> = {
  design: "bg-violet-400",
  copywriting: "bg-blue-400",
  social_media: "bg-pink-400",
  client_meeting: "bg-amber-400",
  internal_meeting: "bg-teal-400",
  revision: "bg-orange-400",
  research: "bg-cyan-400",
  reporting: "bg-indigo-400",
  project_management: "bg-emerald-400",
  other: "bg-text-muted/60",
};

interface TimeCategoryBadgeProps {
  category: TimeEntryCategory;
  className?: string;
}

export function TimeCategoryBadge({ category, className }: TimeCategoryBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium bg-surface-2 text-text-secondary border border-border ${className ?? ""}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${CATEGORY_DOT[category]}`} />
      {TIME_CATEGORY_LABEL[category] ?? category}
    </span>
  );
}
