"use client";

import { useState, useEffect, useRef } from "react";
import {
  brandingApi,
  type AgencyBrandingRead,
  type BrandingSettingsUpdate,
  type BrandingAssetType,
  ApiError,
} from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useToast } from "@/components/ui/toast";
import { InfoTooltip } from "@/components/contextual-help/InfoTooltip";
import { useLocale } from "@/context/locale-context";
import type { TranslationKey } from "@/messages";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function publicAssetUrl(url: string | null): string | null {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${API_BASE}${url}`;
}

// ── Skeleton ───────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-2 ${className ?? ""}`} />;
}

function PageSkeleton() {
  return (
    <div className="space-y-8">
      <div className="flex justify-end">
        <Skeleton className="h-9 w-52" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Skeleton className="h-96" />
        <Skeleton className="h-96" />
      </div>
    </div>
  );
}

// ── Color picker row ──────────────────────────────────────────────────────────

function ColorField({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <label className="text-sm font-medium text-text w-32 shrink-0">{label}</label>
      <div className="flex items-center gap-2.5 flex-1">
        <div className="relative">
          <input
            type="color"
            value={value || "#6366F1"}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            disabled={disabled}
            className="w-10 h-10 rounded-lg border border-border cursor-pointer p-0.5 bg-surface disabled:opacity-40 disabled:cursor-not-allowed"
          />
        </div>
        <input
          type="text"
          value={value}
          onChange={(e) => {
            const v = e.target.value.toUpperCase();
            if (/^#[0-9A-F]{0,6}$/.test(v)) onChange(v);
          }}
          disabled={disabled}
          placeholder="#6366F1"
          className="flex-1 px-3 py-2 text-sm border border-border rounded-lg font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 disabled:opacity-40 disabled:cursor-not-allowed bg-surface text-text"
        />
      </div>
    </div>
  );
}

// ── Logo upload field ─────────────────────────────────────────────────────────

function LogoUploadField({
  label,
  hint,
  currentUrl,
  assetType,
  disabled,
  onUploaded,
}: {
  label: string;
  hint: string;
  currentUrl: string | null;
  assetType: BrandingAssetType;
  disabled: boolean;
  onUploaded: (settings: AgencyBrandingRead) => void;
}) {
  const { t } = useLocale();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    if (!accessToken || !activeAgency) return;
    setUploading(true);
    setError(null);
    try {
      const result = await brandingApi.uploadAsset(file, assetType, activeAgency.id, accessToken);
      onUploaded(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("settings.branding.uploadError"));
    } finally {
      setUploading(false);
    }
  }

  const resolvedUrl = publicAssetUrl(currentUrl);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-text">{label}</p>
          <p className="text-xs text-text-muted">{hint}</p>
        </div>
        {resolvedUrl && (
          <img
            src={resolvedUrl}
            alt={label}
            className="h-10 w-auto max-w-[120px] object-contain rounded border border-border"
          />
        )}
      </div>
      <button
        type="button"
        disabled={disabled || uploading}
        onClick={() => inputRef.current?.click()}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border-2 border-dashed border-border rounded-xl text-sm text-text-muted hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {uploading ? (
          <span className="flex items-center gap-2">
            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {t("settings.branding.uploading")}
          </span>
        ) : resolvedUrl ? (
          t("settings.branding.change")
        ) : (
          t("settings.branding.selectFile")
        )}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}

// ── Live preview panel ────────────────────────────────────────────────────────

function LivePreview({
  branding,
  form,
}: {
  branding: AgencyBrandingRead;
  form: BrandingSettingsUpdate;
}) {
  const { t } = useLocale();
  const primary = form.primary_color || branding.primary_color || "#6366F1";
  const secondary = form.secondary_color || branding.secondary_color || "#818CF8";
  const accent = form.accent_color || branding.accent_color || "#4F46E5";
  const brandName = form.brand_name_override ?? branding.brand_name_override ?? t("settings.branding.preview.fallbackName");
  const logoUrl = publicAssetUrl(branding.logo_url);

  return (
    <div className="bg-surface-2 border border-border rounded-2xl p-5 space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-2 h-2 rounded-full bg-border" />
        <span className="text-xs font-medium text-text-muted uppercase tracking-wider">
          {t("settings.branding.preview.title")}
        </span>
      </div>

      {/* Simulated approval portal card */}
      <div className="bg-surface rounded-xl border border-border overflow-hidden shadow-sm">
        {/* Branded header */}
        <div
          className="px-5 py-3 flex items-center gap-2.5"
          style={{ background: `linear-gradient(135deg, ${primary}15, ${secondary}10)`, borderBottom: `2px solid ${primary}30` }}
        >
          {logoUrl ? (
            <img src={logoUrl} alt={t("settings.branding.preview.logoAlt")} className="h-6 w-auto max-w-[80px] object-contain" />
          ) : (
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center text-white font-bold text-xs"
              style={{ background: primary }}
            >
              {(brandName[0] || "A").toUpperCase()}
            </div>
          )}
          <span className="text-sm font-semibold" style={{ color: primary }}>
            {brandName}
          </span>
        </div>

        <div className="p-5 space-y-3">
          <div className="h-4 bg-surface-2 rounded w-3/4" />
          <div className="h-3 bg-surface-2 rounded w-1/2" />
          <div className="pt-2 flex gap-2">
            <button
              className="flex-1 py-2 rounded-lg text-white text-xs font-medium"
              style={{ background: primary }}
            >
              {t("settings.branding.preview.approve")}
            </button>
            <button
              className="flex-1 py-2 rounded-lg text-xs font-medium border"
              style={{ borderColor: accent, color: accent }}
            >
              {t("settings.branding.preview.requestRevision")}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        {[
          { label: t("settings.branding.color.primary"), color: primary },
          { label: t("settings.branding.color.secondary"), color: secondary },
          { label: t("settings.branding.color.accent"), color: accent },
        ].map(({ label, color }) => (
          <div key={label} className="text-center space-y-1">
            <div className="w-full h-6 rounded-md border border-border" style={{ background: color }} />
            <span className="text-text-muted font-mono">{color}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Entitlement locked state ──────────────────────────────────────────────────

function EntitlementLockedBanner() {
  const { t } = useLocale();

  return (
    <div className="relative overflow-hidden bg-gradient-to-r from-indigo-50 to-violet-50 border border-indigo-200 rounded-2xl p-6">
      <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-100 rounded-full -translate-y-1/2 translate-x-1/4 opacity-40" />
      <div className="relative">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-indigo-900 text-sm mb-1">
              {t("settings.branding.locked.title")}
            </h3>
            <p className="text-xs text-indigo-700 leading-relaxed">
              {t("settings.branding.locked.description")}
            </p>
            <button className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-xs font-semibold rounded-lg hover:bg-indigo-700 transition-colors">
              {t("settings.branding.locked.upgrade")}
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Domain status badge ───────────────────────────────────────────────────────

function DomainStatusBadge({ status }: { status: string }) {
  const { t } = useLocale();
  const map: Record<string, { labelKey: TranslationKey; cls: string }> = {
    pending: { labelKey: "settings.branding.domainStatus.pending", cls: "text-amber-700 bg-amber-50 border-amber-200" },
    verified: { labelKey: "settings.branding.domainStatus.verified", cls: "text-emerald-700 bg-emerald-50 border-emerald-200" },
    failed: { labelKey: "settings.branding.domainStatus.failed", cls: "text-red-700 bg-red-50 border-red-200" },
    disabled: { labelKey: "settings.branding.domainStatus.disabled", cls: "text-text-muted bg-surface-2 border-border" },
  };
  const config = map[status];
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${config?.cls ?? "text-text-muted bg-surface-2 border-border"}`}>
      {config ? t(config.labelKey) : status}
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function BrandingSettingsPage() {
  const { t } = useLocale();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const { confirm, toast } = useToast();
  const brandingRef = useRef<HTMLDivElement>(null);

  const [branding, setBranding] = useState<AgencyBrandingRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  const [form, setForm] = useState<BrandingSettingsUpdate>({});

  const [domainInput, setDomainInput] = useState("");
  const [domainSaving, setDomainSaving] = useState(false);
  const [domainToken, setDomainToken] = useState<string | null>(null);
  const [domainError, setDomainError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !activeAgency) return;
    setIsLoading(true);
    brandingApi
      .get(activeAgency.id, accessToken)
      .then((data) => {
        setBranding(data);
        setForm({
          brand_name_override: data.brand_name_override,
          primary_color: data.primary_color ?? "",
          secondary_color: data.secondary_color ?? "",
          accent_color: data.accent_color ?? "",
          custom_footer_text: data.custom_footer_text,
          is_white_label_enabled: data.is_white_label_enabled,
        });
        // load domain
        brandingApi.getDomain(activeAgency.id, accessToken).catch(() => null);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [accessToken, activeAgency]);

  async function handleSave() {
    if (!accessToken || !activeAgency || !branding) return;
    setSaveState("saving");
    setSaveError(null);
    try {
      const payload: BrandingSettingsUpdate = {};
      if (form.brand_name_override !== undefined) payload.brand_name_override = form.brand_name_override;
      if (form.primary_color) payload.primary_color = form.primary_color;
      if (form.secondary_color) payload.secondary_color = form.secondary_color;
      if (form.accent_color) payload.accent_color = form.accent_color;
      if (form.custom_footer_text !== undefined) payload.custom_footer_text = form.custom_footer_text;
      if (form.is_white_label_enabled !== undefined) payload.is_white_label_enabled = form.is_white_label_enabled;

      const updated = await brandingApi.update(payload, activeAgency.id, accessToken);
      setBranding(updated);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2500);
    } catch (e) {
      setSaveState("error");
      setSaveError(e instanceof ApiError ? e.message : t("settings.branding.saveError"));
    }
  }

  async function handleReset() {
    if (!accessToken || !activeAgency) return;
    const ok = await confirm({
      title: t("settings.branding.resetTitle"),
      message: t("settings.branding.resetMessage"),
      confirmLabel: t("settings.branding.resetAction"),
      destructive: true,
    });
    if (!ok) return;
    try {
      const updated = await brandingApi.reset(activeAgency.id, accessToken);
      toast(t("settings.branding.resetSuccess"), "success");
      setBranding(updated);
      setForm({
        brand_name_override: null,
        primary_color: "",
        secondary_color: "",
        accent_color: "",
        custom_footer_text: null,
        is_white_label_enabled: false,
      });
    } catch {}
  }

  async function handleCreateDomain() {
    if (!accessToken || !activeAgency || !domainInput.trim()) return;
    setDomainSaving(true);
    setDomainError(null);
    setDomainToken(null);
    try {
      const result = await brandingApi.createDomain(domainInput.trim(), activeAgency.id, accessToken);
      setDomainToken(result.verification_token);
      setDomainInput("");
    } catch (e) {
      setDomainError(e instanceof ApiError ? e.message : t("settings.branding.genericError"));
    } finally {
      setDomainSaving(false);
    }
  }

  if (isLoading || !branding) return <PageSkeleton />;

  const locked = !branding.white_label_entitlement;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            onClick={handleReset}
            className="px-4 py-2 text-sm text-zinc-600 hover:text-red-600 transition-colors"
          >
            {t("settings.branding.resetAction")}
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saveState === "saving" || locked}
            className="px-5 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saveState === "saving" && (
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {saveState === "saved"
              ? t("settings.branding.saved")
              : saveState === "saving"
                ? t("settings.branding.saving")
                : t("settings.branding.saveAction")}
          </button>
      </div>

      {saveState === "error" && saveError && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {saveError}
        </div>
      )}

      {/* Entitlement lock banner */}
      {locked && <EntitlementLockedBanner />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left column: settings */}
        <div className="space-y-6">
          {/* White-label toggle */}
          <div className="bg-surface border border-border rounded-2xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div ref={brandingRef}>
                <h2 className="text-sm font-semibold text-text">{t("settings.branding.whiteLabel.title")}</h2>
                <InfoTooltip
                  targetRef={brandingRef}
                  text={t("settings.branding.whiteLabel.help")}
                  title={t("settings.branding.whiteLabel.title")}
                />
              </div>
              <button
                type="button"
                disabled={locked}
                onClick={() =>
                  setForm((f) => ({ ...f, is_white_label_enabled: !f.is_white_label_enabled }))
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 disabled:opacity-40 disabled:cursor-not-allowed
                  ${form.is_white_label_enabled ? "bg-indigo-600" : "bg-surface-2"}`}
              >
                <span
                  className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform duration-200
                    ${form.is_white_label_enabled ? "translate-x-6" : "translate-x-1"}`}
                />
              </button>
            </div>
          </div>

          {/* Brand identity */}
          <div className="bg-surface border border-border rounded-2xl p-6 space-y-5">
            <h2 className="text-sm font-semibold text-text">{t("settings.branding.identity.title")}</h2>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                {t("settings.branding.identity.nameOptional")}
              </label>
              <InfoTooltip
                text={t("settings.branding.identity.nameTooltip")}
                title={t("settings.branding.identity.nameTooltipTitle")}
              >
                <input
                  type="text"
                  value={form.brand_name_override ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, brand_name_override: e.target.value || null }))}
                  disabled={locked}
                  placeholder={t("settings.branding.identity.namePlaceholder")}
                  className="w-full px-3 py-2.5 text-sm border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 disabled:opacity-40 disabled:cursor-not-allowed bg-surface text-text"
                />
              </InfoTooltip>
            </div>

            <div className="space-y-3">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                {t("settings.branding.identity.colors")}
              </label>
              <ColorField
                label={t("settings.branding.color.primary")}
                value={form.primary_color ?? ""}
                onChange={(v) => setForm((f) => ({ ...f, primary_color: v }))}
                disabled={locked}
              />
              <ColorField
                label={t("settings.branding.color.secondary")}
                value={form.secondary_color ?? ""}
                onChange={(v) => setForm((f) => ({ ...f, secondary_color: v }))}
                disabled={locked}
              />
              <ColorField
                label={t("settings.branding.color.accent")}
                value={form.accent_color ?? ""}
                onChange={(v) => setForm((f) => ({ ...f, accent_color: v }))}
                disabled={locked}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                {t("settings.branding.identity.footer")}
              </label>
              <input
                type="text"
                value={form.custom_footer_text ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, custom_footer_text: e.target.value || null }))}
                disabled={locked}
                placeholder={t("settings.branding.identity.footerPlaceholder")}
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 disabled:opacity-40 disabled:cursor-not-allowed bg-surface text-text"
              />
            </div>
          </div>

          {/* Logo uploads */}
          <div className="bg-surface border border-border rounded-2xl p-6 space-y-5">
            <h2 className="text-sm font-semibold text-text">{t("settings.branding.assets.title")}</h2>
            <p className="text-xs text-text-muted">{t("settings.branding.assets.help")}</p>

            <LogoUploadField
              label={t("settings.branding.assets.mainLogo")}
              hint={t("settings.branding.assets.mainLogoHint")}
              currentUrl={branding.logo_url}
              assetType="logo"
              disabled={locked}
              onUploaded={setBranding}
            />

            <div className="border-t border-border" />

            <LogoUploadField
              label={t("settings.branding.assets.emailLogo")}
              hint={t("settings.branding.assets.emailLogoHint")}
              currentUrl={branding.email_logo_url}
              assetType="email_logo"
              disabled={locked}
              onUploaded={setBranding}
            />

            <div className="border-t border-border" />

            <LogoUploadField
              label={t("settings.branding.assets.favicon")}
              hint={t("settings.branding.assets.faviconHint")}
              currentUrl={branding.favicon_url}
              assetType="favicon"
              disabled={locked}
              onUploaded={setBranding}
            />
          </div>

          {/* Custom domain */}
          <div className="bg-surface border border-border rounded-2xl p-6 space-y-4">
            <h2 className="text-sm font-semibold text-text">{t("settings.branding.domain.title")}</h2>
            <p className="text-xs text-text-muted leading-relaxed">
              {t("settings.branding.domain.description")}
            </p>

            <div className="flex gap-2">
              <input
                type="text"
                value={domainInput}
                onChange={(e) => setDomainInput(e.target.value)}
                disabled={locked || domainSaving}
                placeholder={t("settings.branding.domain.placeholder")}
                className="flex-1 px-3 py-2.5 text-sm border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 disabled:opacity-40 disabled:cursor-not-allowed font-mono bg-surface text-text"
              />
              <button
                type="button"
                disabled={locked || domainSaving || !domainInput.trim()}
                onClick={handleCreateDomain}
                className="px-4 py-2 bg-text text-surface text-sm font-medium rounded-xl hover:opacity-80 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {domainSaving ? "…" : t("settings.branding.domain.save")}
              </button>
            </div>

            {domainError && <p className="text-xs text-red-500">{domainError}</p>}

            {domainToken && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-2">
                <p className="text-xs font-semibold text-amber-800">{t("settings.branding.domain.dnsTitle")}</p>
                <p className="text-xs text-amber-700 leading-relaxed">
                  {t("settings.branding.domain.dnsHelp")}
                </p>
                <code className="block text-xs font-mono bg-amber-100 rounded-lg px-3 py-2 text-amber-900 break-all">
                  {domainToken}
                </code>
                <DomainStatusBadge status="pending" />
              </div>
            )}
          </div>
        </div>

        {/* Right column: live preview */}
        <div className="space-y-6">
          <LivePreview branding={branding} form={form} />

          {/* Info card */}
          <div className="bg-surface border border-border rounded-2xl p-5 space-y-3">
            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              {t("settings.branding.applies.title")}
            </h3>
            <ul className="space-y-2">
              {[
                t("settings.branding.applies.approvalPortal"),
                t("settings.branding.applies.sharedReport"),
                t("settings.branding.applies.emailNotifications"),
              ].map((label) => (
                <li key={label} className="flex items-center gap-2.5 text-xs text-text-muted">
                  <svg className="w-3.5 h-3.5 text-accent flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  {label}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
