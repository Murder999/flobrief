"use client";

import {
  brandPortalApi,
  brandingApi,
  publicBrandingApi,
  type AgencyBrandingRead,
  type PlatformBrandingDefaults,
  type PublicBrandingView,
} from "@/lib/api-client";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuthContext } from "@/context/auth-context";
import { useWorkspace } from "@/context/workspace-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface EffectiveBranding {
  portalName: string;
  primaryColor: string;
  secondaryColor: string;
  accentColor: string;
  backgroundColor: string;
  surfaceColor: string;
  textColor: string;
  borderColor: string;
  logoUrl: string | null;
  darkLogoUrl: string | null;
  faviconUrl: string | null;
  ogImageUrl: string | null;
  supportEmail: string | null;
  supportPhone: string | null;
  websiteUrl: string;
  footerCompanyName: string;
  copyrightText: string;
  footerText: string | null;
  seoTitle: string;
  seoDescription: string;
  isWhiteLabel: boolean;
  source: "platform" | "agency" | "custom-domain";
}

const FALLBACK: EffectiveBranding = {
  portalName: "PostPiloter",
  primaryColor: "#4F46E5",
  secondaryColor: "#7C3AED",
  accentColor: "#6366F1",
  backgroundColor: "#FAF9F7",
  surfaceColor: "#FFFFFF",
  textColor: "#1A1917",
  borderColor: "#E5E2DC",
  logoUrl: null,
  darkLogoUrl: null,
  faviconUrl: null,
  ogImageUrl: null,
  supportEmail: "support@postpiloter.com",
  supportPhone: null,
  websiteUrl: "https://postpiloter.com",
  footerCompanyName: "PostPiloter",
  copyrightText: "PostPiloter. Tüm hakları saklıdır.",
  footerText: "PostPiloter ile güvenli brief ve onay yönetimi.",
  seoTitle: "PostPiloter — Ajans ve Marka Operasyon Platformu",
  seoDescription: "Ajanslar ve markalar için brief, onay, revizyon ve içerik takvimi platformu.",
  isWhiteLabel: false,
  source: "platform",
};

interface BrandingContextValue {
  branding: EffectiveBranding;
  isLoading: boolean;
  refreshBranding: () => Promise<void>;
  assetUrl: (value: string | null) => string | null;
}

const BrandingContext = createContext<BrandingContextValue | null>(null);

function platformEffective(value: PlatformBrandingDefaults): EffectiveBranding {
  return {
    ...FALLBACK,
    portalName: value.portal_name || FALLBACK.portalName,
    primaryColor: value.primary_color || FALLBACK.primaryColor,
    secondaryColor: value.secondary_color || FALLBACK.secondaryColor,
    accentColor: value.accent_color || FALLBACK.accentColor,
    backgroundColor: value.background_color || FALLBACK.backgroundColor,
    surfaceColor: value.surface_color || FALLBACK.surfaceColor,
    textColor: value.text_color || FALLBACK.textColor,
    borderColor: value.border_color || FALLBACK.borderColor,
    logoUrl: value.logo_url,
    darkLogoUrl: value.logo_dark_url,
    faviconUrl: value.favicon_url,
    ogImageUrl: value.og_image_url,
    supportEmail: value.support_email,
    supportPhone: value.support_phone,
    websiteUrl: value.website_url || FALLBACK.websiteUrl,
    footerCompanyName: value.footer_company_name || value.portal_name || FALLBACK.footerCompanyName,
    copyrightText: value.copyright_text || FALLBACK.copyrightText,
    footerText: value.footer_text,
    seoTitle: value.public_title || FALLBACK.seoTitle,
    seoDescription: value.public_description || FALLBACK.seoDescription,
  };
}

function publicEffective(value: PublicBrandingView, source: "agency" | "custom-domain"): EffectiveBranding {
  return {
    ...FALLBACK,
    portalName: value.brand_name || FALLBACK.portalName,
    primaryColor: value.primary_color || FALLBACK.primaryColor,
    secondaryColor: value.secondary_color || FALLBACK.secondaryColor,
    accentColor: value.accent_color || FALLBACK.accentColor,
    backgroundColor: value.background_color || FALLBACK.backgroundColor,
    surfaceColor: value.surface_color || FALLBACK.surfaceColor,
    textColor: value.text_color || FALLBACK.textColor,
    borderColor: value.border_color || FALLBACK.borderColor,
    logoUrl: value.logo_url,
    darkLogoUrl: value.dark_logo_url,
    faviconUrl: value.favicon_url,
    ogImageUrl: value.og_image_url,
    supportEmail: value.support_email,
    supportPhone: value.support_phone,
    websiteUrl: value.website_url || FALLBACK.websiteUrl,
    footerCompanyName: value.footer_company_name || value.brand_name || FALLBACK.footerCompanyName,
    copyrightText: value.copyright_text || FALLBACK.copyrightText,
    footerText: value.custom_footer_text,
    seoTitle: value.seo_title || value.brand_name || FALLBACK.seoTitle,
    seoDescription: value.seo_description || FALLBACK.seoDescription,
    isWhiteLabel: value.is_branded,
    source,
  };
}

function agencyEffective(value: AgencyBrandingRead, platform: EffectiveBranding): EffectiveBranding {
  if (!value.is_white_label_enabled || !value.white_label_entitlement) return platform;
  return {
    ...platform,
    portalName: value.brand_name_override || platform.portalName,
    primaryColor: value.primary_color || platform.primaryColor,
    secondaryColor: value.secondary_color || platform.secondaryColor,
    accentColor: value.accent_color || platform.accentColor,
    backgroundColor: value.background_color || platform.backgroundColor,
    surfaceColor: value.surface_color || platform.surfaceColor,
    textColor: value.text_color || platform.textColor,
    borderColor: value.border_color || platform.borderColor,
    logoUrl: value.logo_url || platform.logoUrl,
    darkLogoUrl: value.dark_logo_url || platform.darkLogoUrl,
    faviconUrl: value.favicon_url || platform.faviconUrl,
    ogImageUrl: value.og_image_url || platform.ogImageUrl,
    supportEmail: value.support_email || platform.supportEmail,
    supportPhone: value.support_phone || platform.supportPhone,
    websiteUrl: value.website_url || platform.websiteUrl,
    footerCompanyName: value.footer_company_name || value.brand_name_override || platform.footerCompanyName,
    copyrightText: value.copyright_text || platform.copyrightText,
    footerText: value.custom_footer_text || platform.footerText,
    seoTitle: value.seo_title || value.brand_name_override || platform.seoTitle,
    seoDescription: value.seo_description || platform.seoDescription,
    isWhiteLabel: true,
    source: "agency",
  };
}

function hexRgb(hex: string): [number, number, number] {
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
}

function darken(hex: string): string {
  const [r, g, b] = hexRgb(hex).map((channel) => Math.max(0, Math.round(channel * 0.82)));
  return `#${[r, g, b].map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function applyTokens(value: EffectiveBranding): void {
  const root = document.documentElement;
  const [r, g, b] = hexRgb(value.primaryColor);
  root.style.setProperty("--color-accent", value.primaryColor);
  root.style.setProperty("--color-accent-hover", darken(value.primaryColor));
  root.style.setProperty("--color-accent-subtle", `rgba(${r}, ${g}, ${b}, 0.10)`);
  root.style.setProperty("--color-accent-subtle-hover", `rgba(${r}, ${g}, ${b}, 0.16)`);
  root.style.setProperty("--gradient-accent", `linear-gradient(135deg, ${value.accentColor} 0%, ${value.primaryColor} 100%)`);
  root.style.setProperty("--gradient-sidebar", `linear-gradient(180deg, rgba(${r}, ${g}, ${b}, 0.06) 0%, transparent 35%)`);
  root.style.setProperty("--color-background", value.backgroundColor);
  root.style.setProperty("--color-surface", value.surfaceColor);
  root.style.setProperty("--color-text", value.textColor);
  root.style.setProperty("--color-border", value.borderColor);
  root.dataset.brandingReady = "true";
  root.style.visibility = "visible";
}

function setFavicon(url: string | null): void {
  const existing = document.querySelector<HTMLLinkElement>('link[data-tenant-favicon="true"]');
  if (!url) {
    existing?.remove();
    return;
  }
  const link = existing || document.createElement("link");
  link.rel = "icon";
  link.dataset.tenantFavicon = "true";
  link.href = url;
  if (!existing) document.head.appendChild(link);
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const { user, accessToken } = useAuthContext();
  const { activeAgency } = useWorkspace();
  const pathname = usePathname();
  const [branding, setBranding] = useState<EffectiveBranding>(FALLBACK);
  const [isLoading, setIsLoading] = useState(true);

  const assetUrl = useCallback((value: string | null): string | null => {
    if (!value) return null;
    return /^https?:\/\//.test(value) ? value : `${API_BASE}${value}`;
  }, []);

  const refreshBranding = useCallback(async () => {
    setIsLoading(true);
    try {
      const defaults = await publicBrandingApi.getPlatformDefaults();
      const base = platformEffective(defaults);

      if (user?.user_type === "agency_user" && accessToken && activeAgency) {
        const agency = await brandingApi.get(activeAgency.id, accessToken);
        setBranding(agencyEffective(agency, base));
        return;
      }
      if (user?.user_type === "brand_user" && accessToken) {
        const tenant = await brandPortalApi.branding(accessToken);
        setBranding(publicEffective(tenant, "agency"));
        return;
      }
      if (typeof window !== "undefined") {
        const host = window.location.hostname.toLowerCase();
        if (host !== "postpiloter.com" && host !== "www.postpiloter.com" && host !== "localhost") {
          try {
            const tenant = await publicBrandingApi.resolveHost(host);
            setBranding(publicEffective(tenant, "custom-domain"));
            return;
          } catch {
            // Unknown hosts fail closed to the platform identity.
          }
        }
      }
      setBranding(base);
    } catch {
      setBranding(FALLBACK);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, activeAgency, user?.user_type]);

  useEffect(() => {
    void refreshBranding();
  }, [refreshBranding]);

  useEffect(() => {
    const handler = () => void refreshBranding();
    window.addEventListener("postpiloter:branding-changed", handler);
    window.addEventListener("focus", handler);
    return () => {
      window.removeEventListener("postpiloter:branding-changed", handler);
      window.removeEventListener("focus", handler);
    };
  }, [refreshBranding]);

  useEffect(() => {
    applyTokens(branding);
    const favicon = assetUrl(branding.faviconUrl);
    setFavicon(favicon);
    if (pathname.startsWith("/platform")) {
      document.title = "Platform | PostPiloter";
    } else if (pathname.startsWith("/dashboard") || pathname.startsWith("/brand")) {
      document.title = `${branding.portalName} — ${branding.seoTitle}`;
    }
  }, [assetUrl, branding, pathname]);

  const value = useMemo(
    () => ({ branding, isLoading, refreshBranding, assetUrl }),
    [assetUrl, branding, isLoading, refreshBranding]
  );
  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>;
}

export function useBranding(): BrandingContextValue {
  const context = useContext(BrandingContext);
  if (!context) throw new Error("useBranding must be used inside BrandingProvider");
  return context;
}

export function notifyBrandingChanged(): void {
  window.dispatchEvent(new Event("postpiloter:branding-changed"));
}
