"use client";

import { useRef, useState, useEffect } from "react";
import { agencyApi, type AgencyRead, ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import Link from "next/link";

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

const STATUS_LABELS: Record<string, string> = {
  trial: "Deneme",
  active: "Aktif",
  suspended: "Askıya Alındı",
  cancelled: "İptal Edildi",
};

const STATUS_COLORS: Record<string, string> = {
  trial: "text-warning bg-warning/10",
  active: "text-success bg-success/10",
  suspended: "text-danger bg-danger/10",
  cancelled: "text-text-muted bg-surface-2",
};

const SETTINGS_SECTIONS = [
  {
    href: "/dashboard/settings/branding",
    label: "White-label & Marka Ayarları",
    description: "Logo, renkler ve özel alan adı ayarları.",
    iconPath:
      "M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01",
    iconColor: "bg-purple-500/10 text-purple-500",
  },
  {
    href: "/dashboard/settings/notifications",
    label: "Bildirim Tercihleri",
    description: "E-posta ve uygulama içi bildirim ayarları.",
    iconPath:
      "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
    iconColor: "bg-amber-500/10 text-amber-500",
  },
  {
    href: "/dashboard/settings/members",
    label: "Ekip Üyeleri",
    description: "Üyeleri yönetin ve yeni davetler gönderin.",
    iconPath:
      "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
    iconColor: "bg-emerald-500/10 text-emerald-500",
  },
  {
    href: "/dashboard/settings/billing",
    label: "Abonelik & Faturalama",
    description: "Plan bilgileri, kullanım limitleri ve faturalar.",
    iconPath:
      "M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z",
    iconColor: "bg-indigo-500/10 text-indigo-500",
  },
];

function AgencyLogoCard({ agency, agencyId, accessToken, onUpdated }: {
  agency: AgencyRead; agencyId: string; accessToken: string; onUpdated: (a: AgencyRead) => void;
}) {
  const { toast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const logoSrc = agency.logo_url ? API_BASE + agency.logo_url : null;

  async function handleFile(file: File) {
    setUploading(true);
    try {
      const updated = await agencyApi.uploadAgencyLogo(agencyId, file, accessToken);
      onUpdated(updated);
      toast("Logo güncellendi.", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Logo yüklenemedi.", "error");
    } finally { setUploading(false); }
  }

  async function handleDelete() {
    setUploading(true);
    try {
      const updated = await agencyApi.deleteAgencyLogo(agencyId, accessToken);
      onUpdated(updated);
      toast("Logo silindi.", "success");
    } catch { toast("Logo silinemedi.", "error"); } finally { setUploading(false); }
  }

  return (
    <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-6">
      <div className="px-6 py-5 border-b border-border">
        <h2 className="text-sm font-semibold text-text">Ajans Logosu</h2>
        <p className="text-xs text-text-muted mt-0.5">PNG, JPEG, WebP veya SVG · Maks. 5 MB · Sidebar ve raporlarda görünür</p>
      </div>
      <div className="px-6 py-6 flex items-center gap-6">
        <div className="relative group/logo">
          <div className="w-20 h-20 rounded-2xl border-2 border-border bg-surface-2 flex items-center justify-center overflow-hidden">
            {logoSrc ? (
              <img src={logoSrc} alt={agency.name} className="w-full h-full object-contain p-2" />
            ) : (
              <span className="text-2xl font-bold text-accent">{agency.name.charAt(0).toUpperCase()}</span>
            )}
            {uploading && (
              <div className="absolute inset-0 bg-surface/70 rounded-2xl flex items-center justify-center">
                <svg className="w-5 h-5 text-accent animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
              </div>
            )}
          </div>
          {!uploading && (
            <div className="absolute inset-0 rounded-2xl bg-black/50 opacity-0 group-hover/logo:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1 cursor-pointer" onClick={() => inputRef.current?.click()}>
              <span className="text-white text-[10px] font-semibold">{logoSrc ? "Değiştir" : "Yükle"}</span>
            </div>
          )}
          <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
        </div>
        <div className="flex flex-col gap-2">
          <button onClick={() => inputRef.current?.click()} disabled={uploading}
            className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50">
            {logoSrc ? "Logoyu Değiştir" : "Logo Yükle"}
          </button>
          {logoSrc && (
            <button onClick={handleDelete} disabled={uploading}
              className="px-4 py-2 text-danger border border-danger/30 text-sm font-medium rounded-lg hover:bg-danger/5 transition-colors disabled:opacity-50">
              Logoyu Sil
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AgencySettingsPage() {
  const { accessToken } = useAuth();
  const { activeAgency, refreshWorkspaces } = useWorkspace();

  const [agency, setAgency] = useState<AgencyRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [name, setName] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (!activeAgency || !accessToken) return;

    setIsLoading(true);
    agencyApi
      .get(activeAgency.id, accessToken)
      .then((data) => {
        setAgency(data);
        setName(data.name);
      })
      .catch(() => {
        setErrorMsg("Ajans bilgileri yüklenemedi.");
      })
      .finally(() => setIsLoading(false));
  }, [activeAgency, accessToken]);

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
      setErrorMsg(err instanceof Error ? err.message : "Kaydedilemedi");
      setSaveState("error");
    }
  };

  const isDirty = agency && name !== agency.name;

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text">Ajans Ayarları</h1>
        <p className="mt-1 text-sm text-text-muted">
          Ajansınızın genel bilgilerini düzenleyin.
        </p>
      </div>

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
      <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-6">
        <div className="px-6 py-5 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Genel Bilgiler</h2>
        </div>

        <form onSubmit={handleSave} className="px-6 py-6 space-y-5">
          {isLoading ? (
            <>
              <SkeletonField />
              <SkeletonField />
            </>
          ) : (
            <>
              <Input
                label="Ajans Adı"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wide">
                  Slug
                </label>
                <div className="h-10 px-3 flex items-center bg-surface-2 border border-border rounded-lg">
                  <span className="text-sm text-text-muted">{agency?.slug}</span>
                </div>
                <p className="text-xs text-text-muted">Slug değiştirilemez.</p>
              </div>
            </>
          )}

          {errorMsg && (
            <div className="px-3 py-2 bg-danger/10 border border-danger/20 rounded-lg">
              <p className="text-sm text-danger">{errorMsg}</p>
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            {saveState === "saved" ? (
              <p className="text-sm text-success">Değişiklikler kaydedildi.</p>
            ) : (
              <div />
            )}
            <Button
              type="submit"
              disabled={isLoading || !isDirty || saveState === "saving"}
            >
              {saveState === "saving" ? "Kaydediliyor…" : "Değişiklikleri Kaydet"}
            </Button>
          </div>
        </form>
      </div>

      {/* Agency info card */}
      {agency && (
        <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-6">
          <div className="px-6 py-5 border-b border-border">
            <h2 className="text-sm font-semibold text-text">Ajans Bilgileri</h2>
          </div>
          <div className="px-6 py-5 grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-text-muted mb-0.5">Oluşturulma</p>
              <p className="text-sm text-text">
                {new Date(agency.created_at).toLocaleDateString("tr-TR")}
              </p>
            </div>
            <div>
              <p className="text-xs text-text-muted mb-0.5">Durum</p>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  STATUS_COLORS[agency.status] ?? "text-text-muted bg-surface-2"
                }`}
              >
                {STATUS_LABELS[agency.status] ?? agency.status}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Settings Sections hub */}
      <div>
        <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-3">Diğer Ayarlar</h2>
        <div className="grid grid-cols-1 gap-3">
          {SETTINGS_SECTIONS.map((section) => (
            <Link
              key={section.href}
              href={section.href}
              className="flex items-center gap-4 bg-surface border border-border rounded-xl p-4 hover:border-border-hover transition-colors group"
            >
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${section.iconColor}`}>
                <svg className="w-4.5 h-4.5 w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={section.iconPath} />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text">{section.label}</p>
                <p className="text-xs text-text-muted mt-0.5">{section.description}</p>
              </div>
              <svg className="w-4 h-4 text-text-muted group-hover:text-accent transition-colors flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
