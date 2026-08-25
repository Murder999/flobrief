import type { TranslationKey } from "@/messages";

export type HelpPortal = "agency" | "brand";

export interface HelpArticleMeta {
  id: string;
  href?: string;
}

export interface HelpCategoryMeta {
  id: string;
  articles: HelpArticleMeta[];
}

export interface HelpQuickActionMeta {
  id: string;
  href: string;
  icon: "brief" | "approval" | "revision" | "notifications" | "brand" | "template" | "report";
}

export interface HelpPortalConfig {
  basePath: string;
  defaultTopic: string;
  quickActions: HelpQuickActionMeta[];
  categories: HelpCategoryMeta[];
}

export const HELP_CONFIG: Record<HelpPortal, HelpPortalConfig> = {
  brand: {
    basePath: "/brand/help",
    defaultTopic: "portal-overview",
    quickActions: [
      { id: "brief", href: "/brand/briefs/new", icon: "brief" },
      { id: "approvals", href: "/brand/approvals", icon: "approval" },
      { id: "revision", href: "/brand/approvals", icon: "revision" },
      { id: "notifications", href: "/brand/notifications", icon: "notifications" },
    ],
    categories: [
      {
        id: "getting-started",
        articles: [
          { id: "portal-overview", href: "/brand/dashboard" },
          { id: "first-brief", href: "/brand/briefs/new" },
          { id: "agency-workflow", href: "/brand/dashboard" },
        ],
      },
      {
        id: "briefs",
        articles: [
          { id: "brief-create", href: "/brand/briefs/new" },
          { id: "brief-status", href: "/brand/briefs" },
          { id: "brief-update", href: "/brand/briefs" },
          { id: "brief-files", href: "/brand/files" },
        ],
      },
      {
        id: "revision-approval",
        articles: [
          { id: "revision", href: "/brand/approvals" },
          { id: "comments", href: "/brand/briefs" },
          { id: "approval", href: "/brand/approvals" },
          { id: "rejection", href: "/brand/approvals" },
          { id: "versions", href: "/brand/briefs" },
        ],
      },
      {
        id: "content-files",
        articles: [
          { id: "calendar", href: "/brand/calendar" },
          { id: "files", href: "/brand/files" },
          { id: "deliveries", href: "/brand/approvals" },
        ],
      },
      {
        id: "brand",
        articles: [
          { id: "brand-dna", href: "/brand/identity" },
          { id: "brand-settings", href: "/brand/settings" },
          { id: "team", href: "/brand/team" },
        ],
      },
      {
        id: "notifications",
        articles: [
          { id: "notifications-inapp", href: "/brand/notifications" },
          { id: "notifications-email", href: "/brand/notifications" },
          { id: "notifications-whatsapp", href: "/brand/notifications" },
        ],
      },
      {
        id: "reporting",
        articles: [
          { id: "report-view", href: "/brand/reports" },
          { id: "report-metrics", href: "/brand/reports" },
        ],
      },
      {
        id: "account",
        articles: [
          { id: "profile", href: "/brand/settings?tab=profile" },
          { id: "language", href: "/brand/settings" },
          { id: "security", href: "/brand/settings" },
        ],
      },
    ],
  },
  agency: {
    basePath: "/dashboard/help",
    defaultTopic: "portal-overview",
    quickActions: [
      { id: "brief", href: "/dashboard/briefs/new", icon: "brief" },
      { id: "brand", href: "/dashboard/brands", icon: "brand" },
      { id: "template", href: "/dashboard/templates/new", icon: "template" },
      { id: "report", href: "/dashboard/reports/new", icon: "report" },
    ],
    categories: [
      {
        id: "getting-started",
        articles: [
          { id: "portal-overview", href: "/dashboard" },
          { id: "first-brand", href: "/dashboard/brands" },
          { id: "agency-workflow", href: "/dashboard" },
        ],
      },
      {
        id: "brands",
        articles: [
          { id: "brand-add", href: "/dashboard/brands" },
          { id: "brand-team", href: "/dashboard/brands" },
          { id: "brand-settings", href: "/dashboard/brands" },
        ],
      },
      {
        id: "briefs",
        articles: [
          { id: "brief-create", href: "/dashboard/briefs/new" },
          { id: "five-dates", href: "/dashboard/briefs/new" },
          { id: "platform-content", href: "/dashboard/briefs/new" },
          { id: "brief-assignment", href: "/dashboard/briefs/new" },
          { id: "brief-status", href: "/dashboard/briefs" },
        ],
      },
      {
        id: "templates",
        articles: [
          { id: "template-create", href: "/dashboard/templates/new" },
          { id: "template-use", href: "/dashboard/templates" },
          { id: "template-edit", href: "/dashboard/templates" },
        ],
      },
      {
        id: "revision-approval",
        articles: [
          { id: "file-send", href: "/dashboard/briefs" },
          { id: "revision", href: "/dashboard/briefs" },
          { id: "comments", href: "/dashboard/briefs" },
          { id: "approval", href: "/dashboard/briefs" },
        ],
      },
      {
        id: "reporting",
        articles: [
          { id: "report-create", href: "/dashboard/reports/new" },
          { id: "report-kpis", href: "/dashboard/reports" },
          { id: "brand-reporting", href: "/dashboard/reports" },
        ],
      },
      {
        id: "team-capacity",
        articles: [
          { id: "members", href: "/dashboard/settings/members" },
          { id: "capacity", href: "/dashboard/capacity" },
          { id: "assignments", href: "/dashboard/capacity/unassigned" },
        ],
      },
      {
        id: "settings",
        articles: [
          { id: "profile", href: "/dashboard/settings/profile" },
          { id: "agency-info", href: "/dashboard/settings/agency" },
          { id: "notifications", href: "/dashboard/settings/notifications" },
          { id: "white-label", href: "/dashboard/settings/branding" },
          { id: "billing", href: "/dashboard/settings/billing" },
        ],
      },
    ],
  },
};

export function helpCommonKey(id: string): TranslationKey {
  return `help.common.${id}` as TranslationKey;
}

export function helpCategoryKey(portal: HelpPortal, id: string): TranslationKey {
  return `help.${portal}.category.${id}` as TranslationKey;
}

export function helpQuickActionKey(portal: HelpPortal, id: string, field: "title" | "description"): TranslationKey {
  return `help.${portal}.quick.${id}.${field}` as TranslationKey;
}

export function helpArticleKey(
  portal: HelpPortal,
  id: string,
  field: "title" | "summary" | "purpose" | "steps" | "notes" | "keywords"
): TranslationKey {
  return `help.${portal}.article.${id}.${field}` as TranslationKey;
}

export function helpFaqKey(portal: HelpPortal, categoryId: string, field: "question" | "answer"): TranslationKey {
  return `help.${portal}.faq.${categoryId}.${field}` as TranslationKey;
}
