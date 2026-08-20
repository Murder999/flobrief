import type { TranslationKey } from "@/messages";

const navigationKeys: Record<string, TranslationKey> = {
  "Genel Bakış": "dashboard.navigation.overview",
  "İş Akışı": "dashboard.navigation.workflow",
  "Brief'ler": "dashboard.navigation.briefs",
  Briefler: "dashboard.navigation.briefs",
  Takvim: "dashboard.navigation.calendar",
  Şablonlar: "dashboard.navigation.templates",
  "Zaman Takibi": "dashboard.navigation.timeTracking",
  "Markalar & Raporlar": "dashboard.navigation.brandsReports",
  Markalar: "dashboard.navigation.brands",
  Raporlar: "dashboard.navigation.reports",
  Aktivite: "dashboard.navigation.activity",
  Ekip: "dashboard.navigation.team",
  "Ekip Üyeleri": "dashboard.navigation.members",
  Kapasite: "dashboard.navigation.capacity",
  Davetlerim: "dashboard.navigation.invitations",
  Finans: "dashboard.navigation.finance",
  "Faturalandırılabilir Zaman": "dashboard.navigation.billableTime",
  Faturalar: "dashboard.navigation.invoices",
  "Retainer'lar": "dashboard.navigation.retainers",
  "Finans Ayarları": "dashboard.navigation.financeSettings",
  "Muhasebe Entegrasyonu": "dashboard.navigation.accounting",
  Kârlılık: "dashboard.navigation.profitability",
  Hesap: "dashboard.navigation.account",
  Faturalama: "dashboard.navigation.billing",
  Profilim: "dashboard.navigation.profile",
  Bildirimler: "dashboard.navigation.notifications",
  "Ajans Ayarları": "dashboard.navigation.agencySettings",
  "Ana Sayfa": "dashboard.navigation.home",
  Genel: "dashboard.navigation.general",
  "Brief Ver": "dashboard.navigation.createBrief",
  Brieflerim: "dashboard.navigation.myBriefs",
  Onaylar: "dashboard.navigation.approvals",
  Dosyalar: "dashboard.navigation.files",
  Marka: "dashboard.navigation.brand",
  "Marka DNA": "dashboard.navigation.brandIdentity",
  Diğer: "dashboard.navigation.other",
  "Marka Portalı": "dashboard.navigation.portal",
  Ayarlar: "dashboard.navigation.settings",
};

export function translateAppNavigationLabel(
  t: (key: TranslationKey) => string,
  label: string | null
): string | null {
  if (!label) return null;
  const key = navigationKeys[label];
  return key ? t(key) : label;
}
