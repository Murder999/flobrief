"use client";

import { useRef, useState, useEffect } from "react";
import { agencyApi, type AgencyRead, ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useLocale } from "@/context/locale-context";
import type { TranslationKey } from "@/messages";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

type SaveState = "idle" | "saving" | "saved" | "error";

function SkeletonField() {
  return (
    <div className="space-y-1.5">
      <div className="h-3 bg-surface-2 rounded w-20 animate-pulse" />
      <div className="h-10 bg-surface-2 rounded-lg animate-pulse" />
    </div>
  );
}

const STATUS_LABEL_KEYS: Record<string, TranslationKey> = {
  trial: "settings.agency.status.trial",
  active: "settings.agency.status.active",
  suspended: "settings.agency.status.suspended",
  cancelled: "settings.agency.status.cancelled",
};

const STATUS_COLORS: Record<string, string> = {
  trial: "text-warning bg-warning/10",
  active: "text-success bg-success/10",
  suspended: "text-danger bg-danger/10",
  cancelled: "text-text-muted bg-surface-2",
};

function AgencyLogoCard({ agency, agencyId, accessToken, onUpdated }: {
  agency: AgencyRead; agencyId: string; accessToken: string; onUpdated: (a: AgencyRead) => void;
}) {
  const { t } = useLocale();
  const { toast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const logoSrc = agency.logo_url ? API_BASE + agency.logo_url : null;

  async function handleFile(file: File) {
    setUploading(true);
    try {
      const updated = await agencyApi.uploadAgencyLogo(agencyId, file, accessToken);
      onUpdated(updated);
      toast(t("settings.agency.logo.updated"), "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : t("settings.agency.logo.uploadError"), "error");
    } finally { setUploading(false); }
  }

  async function handleDelete() {
    setUploading(true);
    try {
      const updated = await agencyApi.deleteAgencyLogo(agencyId, accessToken);
      onUpdated(updated);
      toast(t("settings.agency.logo.deleted"), "success");
    } catch { toast(t("settings.agency.logo.deleteError"), "error"); } finally { setUploading(false); }
  }

  return (
    <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-5">
      <div className="px-5 py-4 border-b border-border">
        <h2 className="text-sm font-semibold text-text">{t("settings.agency.logo.title")}</h2>
        <p className="text-xs text-text-muted mt-0.5">{t("settings.agency.logo.help")}</p>
      </div>
      <div className="px-5 py-6 flex items-center gap-5">
        <div className="relative group/logo">
          <div className="w-16 h-16 rounded-2xl border-2 border-border bg-surface-2 flex items-center justify-center overflow-hidden">
            {logoSrc ? (
              <img src={logoSrc} alt={agency.name} className="w-full h-full object-contain p-2" />
            ) : (
              <span className="text-2xl font-bold text-accent">{agency.name.charAt(0).toUpperCase()}</span>
            )}
            {uploading && (
              <div className="absolute inset-0 bg-surface/70 rounded-2xl flex items-center justify-center">
                <svg className="w-4 h-4 text-accent animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="3"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4"/>
                </svg>
              </div>
            )}
          </div>
          {!uploading && (
            <div className="absolute inset-0 rounded-2xl bg-black/50 opacity-0 group-hover/logo:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1 cursor-pointer" onClick={() => inputRef.current?.click()}>
              <span className="text-white text-[10px] font-semibold">
                {t(logoSrc ? "settings.agency.logo.change" : "settings.agency.logo.upload")}
              </span>
            </div>
          )}
          <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
        </div>
        <div className="flex flex-col gap-2">
          <button onClick={() => inputRef.current?.click()} disabled={uploading}
            className="px-3 py-1.5 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50">
            {t(logoSrc ? "settings.agency.logo.changeAction" : "settings.agency.logo.uploadAction")}
          </button>
          {logoSrc && (
            <button onClick={handleDelete} disabled={uploading}
              className="px-3 py-1.5 text-danger border border-danger/30 text-sm font-medium rounded-lg hover:bg-danger/5 transition-colors disabled:opacity-50">
              {t("settings.agency.logo.deleteAction")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AgencySettingsPage() {
  const { intlLocale, t } = useLocale();
  const { accessToken } = useAuth();
  const { activeAgency, refreshWorkspaces } = useWorkspace();
  const [agency, setAgency] = useState<AgencyRead | null>(null);
  const [name, setName] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (!activeAgency || !accessToken) return;
    agencyApi
      .get(activeAgency.id, accessToken)
      .then((data) => {
        setAgency(data);
        setName(data.name);
      })
      .catch(() => {
        setErrorMsg(t("settings.agency.loadError"));
      })
      .finally(() => {});
  }, [activeAgency, accessToken, t]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeAgency || !accessToken) return;

    setSaveState("saving");
    setErrorMsg("");

    try {
      const updated = await agencyApi.update(
        activeAgency.id,
        { name: name.trim() },
        accessToken
      );
      setAgency(updated);
      await refreshWorkspaces();
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2500);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : t("settings.agency.saveError"));
      setSaveState("error");
    }
  };

  const isDirty = agency && name !== agency.name;

  return (
    <div>
      {/* Logo upload */}
      {agency && activeAgency && accessToken && (
        <AgencyLogoCard
          agency={agency}
          agencyId={activeAgency.id}
          accessToken={accessToken}
          onUpdated={(updated) => { setAgency(updated); refreshWorkspaces(); }}
        />
      )}

      {/* Agency name form */}
      <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-4">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">{t("settings.agency.generalTitle")}</h2>
        </div>

        <form onSubmit={handleSave} className="space-y-3 px-5 py-4">
          <Input
            label={t("settings.agency.name")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wide text-text-muted">
              {t("settings.agency.slug")}
            </label>
            <div className="flex h-9 items-center rounded-lg border border-border bg-surface-2 px-3">
              <span className="text-sm text-text-muted">{agency?.slug}</span>
            </div>
            <p className="text-xs text-text-muted">{t("settings.agency.slugImmutable")}</p>
          </div>

          {errorMsg ? (
            <div className="rounded-lg border border-danger/20 bg-danger/10 px-2 py-1.5">
              <p className="text-sm text-danger">{errorMsg}</p>
            </div>
          ) : null}

          <div className="flex items-center justify-between">
            {saveState === "saved" ? (
              <p className="text-sm text-success">{t("settings.agency.saved")}</p>
            ) : (
              <div />
            )}
            <Button type="submit" disabled={!isDirty || saveState === "saving"}>
              {t(saveState === "saving" ? "settings.agency.saving" : "settings.agency.saveAction")}
            </Button>
          </div>
        </form>
        </div>

      {/* Agency info card */}
      {agency && (
        <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-4">
          <div className="px-5 py-4 border-b border-border">
            <h2 className="text-sm font-semibold text-text">{t("settings.agency.infoTitle")}</h2>
          </div>
          <div className="px-5 py-4 grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-text-muted mb-0.5">{t("settings.agency.created")}</p>
              <p className="text-sm text-text">
                {new Date(agency.created_at).toLocaleDateString(intlLocale)}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted mb-0.5">{t("settings.agency.status")}</p>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  STATUS_COLORS[agency.status] ?? "text-text-muted bg-surface-2"
                }`}
              >
                {STATUS_LABEL_KEYS[agency.status] ? t(STATUS_LABEL_KEYS[agency.status]) : agency.status}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
