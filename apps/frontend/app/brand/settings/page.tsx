"use client";

import { useAuth } from "@/hooks/useAuth";
import { brandPortalApi, type UserProfileRead, type BrandProfileRead } from "@/lib/api-client";
import { getInitials } from "@/lib/auth";
import { PhoneNumberInput } from "@/components/forms/PhoneNumberInput";
import { PasswordChangeForm } from "@/components/settings/password-change-form";
import { useEffect, useState, useCallback, type FormEvent } from "react";

type Tab = "profile" | "brand";

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">{label}</p>
      {children}
    </div>
  );
}

function SaveButton({ isLoading, disabled }: { isLoading: boolean; disabled?: boolean }) {
  return (
    <button
      type="submit"
      disabled={isLoading || disabled}
      className="px-4 py-2 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {isLoading ? "Kaydediliyor…" : "Kaydet"}
    </button>
  );
}

export default function BrandSettingsPage() {
  const { user, accessToken, refreshUser, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("profile");

  // Profile state
  const [profile, setProfile] = useState<UserProfileRead | null>(null);
  const [fullName, setFullName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Phone number (WhatsApp consent itself is granted from the Notifications
  // settings panel — /brand/notifications — never implied by phone presence).
  const [phoneNumber, setPhoneNumber] = useState("");
  const [whatsappSaving, setWhatsappSaving] = useState(false);
  const [whatsappSuccess, setWhatsappSuccess] = useState(false);
  const [whatsappError, setWhatsappError] = useState<string | null>(null);

  // Brand state
  const [brand, setBrand] = useState<BrandProfileRead | null>(null);
  const [brandName, setBrandName] = useState("");
  const [brandSaving, setBrandSaving] = useState(false);
  const [brandSuccess, setBrandSuccess] = useState(false);
  const [brandError, setBrandError] = useState<string | null>(null);
  const [isManager, setIsManager] = useState(false);

  const loadData = useCallback(async () => {
    if (!accessToken) return;
    const [prof, br, me] = await Promise.allSettled([
      brandPortalApi.getProfile(accessToken),
      brandPortalApi.getBrand(accessToken),
      brandPortalApi.me(accessToken),
    ]);
    if (prof.status === "fulfilled") {
      setProfile(prof.value);
      setFullName(prof.value.full_name);
      setJobTitle(prof.value.job_title ?? user?.job_title ?? "");
      setPhoneNumber(prof.value.phone_number ?? "");
    }
    if (br.status === "fulfilled") {
      setBrand(br.value);
      setBrandName(br.value.name);
    }
    if (me.status === "fulfilled") {
      setIsManager(["brand_owner", "brand_manager"].includes(me.value.membership_role));
    }
  }, [accessToken, user?.job_title]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleProfileSave(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setProfileSaving(true);
    setProfileError(null);
    setProfileSuccess(false);
    try {
      const updated = await brandPortalApi.updateProfile({ full_name: fullName, job_title: jobTitle || null }, accessToken);
      setProfile(updated);
      setFullName(updated.full_name);
      if (refreshUser) await refreshUser();
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err: unknown) {
      setProfileError(err instanceof Error ? err.message : "Güncelleme başarısız");
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleSaveWhatsApp(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setWhatsappSaving(true);
    setWhatsappError(null);
    setWhatsappSuccess(false);
    try {
      const updated = await brandPortalApi.updateProfile(
        { phone_number: phoneNumber.trim() || null },
        accessToken,
      );
      setPhoneNumber(updated.phone_number ?? "");
      setWhatsappSuccess(true);
      setTimeout(() => setWhatsappSuccess(false), 3000);
    } catch (err: unknown) {
      setWhatsappError(err instanceof Error ? err.message : "Kaydedilemedi.");
    } finally {
      setWhatsappSaving(false);
    }
  }

  async function handleBrandSave(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setBrandSaving(true);
    setBrandError(null);
    setBrandSuccess(false);
    try {
      const updated = await brandPortalApi.updateBrand({ name: brandName }, accessToken);
      setBrand(updated);
      setBrandName(updated.name);
      setBrandSuccess(true);
      setTimeout(() => setBrandSuccess(false), 3000);
    } catch (err: unknown) {
      setBrandError(err instanceof Error ? err.message : "Güncelleme başarısız");
    } finally {
      setBrandSaving(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text">Ayarlar</h1>
        <p className="mt-1 text-text-muted">Profil ve marka bilgilerinizi yönetin.</p>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 bg-surface-2 p-1 rounded-xl w-fit mb-6">
        {(["profile", "brand"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === t ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"
            }`}
          >
            {t === "profile" ? "Profilim" : "Marka Profili"}
          </button>
        ))}
      </div>

      {/* Profile tab */}
      {activeTab === "profile" && (
        <>
        <div className="bg-surface border border-border rounded-xl p-6">
          {/* Avatar */}
          <div className="flex items-center gap-4 mb-6 pb-6 border-b border-border">
            <div className="w-14 h-14 bg-accent/20 rounded-full flex items-center justify-center flex-shrink-0">
              <span className="text-lg font-semibold text-accent">
                {user ? getInitials(user.full_name) : "?"}
              </span>
            </div>
            <div>
              <p className="text-base font-semibold text-text">{profile?.full_name ?? user?.full_name}</p>
              <p className="text-sm text-text-muted">{profile?.email ?? user?.email}</p>
            </div>
          </div>

          <form onSubmit={handleProfileSave} className="space-y-5">
            <FieldRow label="Ad Soyad">
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="w-full h-9 px-3 bg-surface-2 border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              />
            </FieldRow>

            <FieldRow label="Meslek / Unvan">
              <input
                type="text"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                placeholder="örn. Marka Müdürü, Pazarlama Uzmanı"
                className="w-full h-9 px-3 bg-surface-2 border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
              />
              <p className="text-xs text-text-muted mt-1">Yorumlarda isminizin altında görünür.</p>
            </FieldRow>

            <FieldRow label="E-posta">
              <p className="text-sm text-text">{profile?.email ?? user?.email ?? "—"}</p>
              <p className="text-xs text-text-muted mt-0.5">E-posta değişikliği için ajansınızla iletişime geçin.</p>
            </FieldRow>

            <FieldRow label="Hesap Türü">
              <p className="text-sm text-text">Marka Kullanıcısı</p>
            </FieldRow>

            <FieldRow label="Son Giriş">
              <p className="text-sm text-text">
                {user?.last_login_at
                  ? new Date(user.last_login_at).toLocaleDateString("tr-TR", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "—"}
              </p>
            </FieldRow>

            {profileError && (
              <div className="rounded-lg bg-danger/10 border border-danger/20 px-4 py-3">
                <p className="text-sm text-danger">{profileError}</p>
              </div>
            )}
            {profileSuccess && (
              <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-4 py-3">
                <p className="text-sm text-emerald-400">Profil güncellendi.</p>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <SaveButton isLoading={profileSaving} />
            </div>
          </form>
        </div>

        <div className="mt-4">
          <PasswordChangeForm accessToken={accessToken} onCompleted={() => void logout()} />
        </div>

        {/* WhatsApp Opt-In */}
        <div className="mt-4 bg-surface border border-border rounded-xl p-6">
          <div className="flex items-center gap-3 mb-4 pb-4 border-b border-border">
            <div className="w-8 h-8 bg-emerald-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-text">WhatsApp Bildirimleri</h3>
              <p className="text-xs text-text-muted">Brief güncellemeleri ve onay talepleri için bildirim alın.</p>
            </div>
          </div>
          <form onSubmit={handleSaveWhatsApp} className="space-y-4">
            <PhoneNumberInput
              id="brand-phone"
              label="Telefon Numarası"
              value={phoneNumber}
              onChange={setPhoneNumber}
              helperText="WhatsApp bildirimleri bu numaraya gönderilir."
            />

            <div className="flex items-center justify-between py-3 px-4 bg-surface-2 rounded-lg gap-3">
              <p className="text-xs text-text-muted leading-relaxed">
                WhatsApp bildirimlerini açmak, kapatmak ve bildirim türlerini seçmek için
                Bildirimler sayfasındaki WhatsApp bölümünü kullanın.
              </p>
              <a
                href="/brand/notifications?tab=settings"
                className="text-xs font-medium text-accent hover:underline whitespace-nowrap flex-shrink-0"
              >
                Bildirim ayarlarına git →
              </a>
            </div>

            {whatsappError && (
              <div className="rounded-lg bg-danger/10 border border-danger/20 px-4 py-3">
                <p className="text-sm text-danger">{whatsappError}</p>
              </div>
            )}
            {whatsappSuccess && (
              <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-4 py-3">
                <p className="text-sm text-emerald-400">WhatsApp ayarları güncellendi.</p>
              </div>
            )}

            <div className="flex justify-end pt-1">
              <SaveButton isLoading={whatsappSaving} />
            </div>
          </form>
        </div>
        </>
      )}

      {/* Brand tab */}
      {activeTab === "brand" && (
        <div className="bg-surface border border-border rounded-xl p-6">
          {brand ? (
            <>
              <div className="flex items-center gap-4 mb-6 pb-6 border-b border-border">
                <div className="w-14 h-14 bg-accent/10 rounded-xl flex items-center justify-center flex-shrink-0">
                  <span className="text-xl font-bold text-accent">
                    {getInitials(brand.name)}
                  </span>
                </div>
                <div>
                  <p className="text-base font-semibold text-text">{brand.name}</p>
                  <p className="text-sm text-text-muted">/{brand.slug}</p>
                </div>
              </div>

              {isManager ? (
                <form onSubmit={handleBrandSave} className="space-y-5">
                  <FieldRow label="Marka Adı">
                    <input
                      type="text"
                      value={brandName}
                      onChange={(e) => setBrandName(e.target.value)}
                      required
                      className="w-full h-9 px-3 bg-surface-2 border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                    />
                  </FieldRow>

                  <FieldRow label="Marka URL Slug">
                    <p className="text-sm text-text">/{brand.slug}</p>
                    <p className="text-xs text-text-muted mt-0.5">Slug değişikliği için ajansınızla iletişime geçin.</p>
                  </FieldRow>

                  <FieldRow label="Durum">
                    <p className="text-sm text-text">
                      {brand.status === "active" ? "Aktif" : brand.status === "inactive" ? "Pasif" : brand.status === "suspended" ? "Askıya Alındı" : brand.status}
                    </p>
                  </FieldRow>

                  {brandError && (
                    <div className="rounded-lg bg-danger/10 border border-danger/20 px-4 py-3">
                      <p className="text-sm text-danger">{brandError}</p>
                    </div>
                  )}
                  {brandSuccess && (
                    <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-4 py-3">
                      <p className="text-sm text-emerald-400">Marka güncellendi.</p>
                    </div>
                  )}

                  <div className="flex justify-end pt-2">
                    <SaveButton isLoading={brandSaving} />
                  </div>
                </form>
              ) : (
                <div className="space-y-5">
                  <FieldRow label="Marka Adı">
                    <p className="text-sm text-text">{brand.name}</p>
                  </FieldRow>
                  <FieldRow label="Marka URL Slug">
                    <p className="text-sm text-text">/{brand.slug}</p>
                  </FieldRow>
                  <FieldRow label="Durum">
                    <p className="text-sm text-text">
                      {brand.status === "active" ? "Aktif" : brand.status === "inactive" ? "Pasif" : brand.status === "suspended" ? "Askıya Alındı" : brand.status}
                    </p>
                  </FieldRow>
                  <div className="pt-4 border-t border-border">
                    <p className="text-xs text-text-muted">
                      Marka bilgilerini düzenlemek için yönetici yetkisi gereklidir.
                    </p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="animate-pulse space-y-4">
              <div className="flex items-center gap-4 pb-6 border-b border-border">
                <div className="w-14 h-14 bg-surface-2 rounded-xl" />
                <div className="space-y-2">
                  <div className="h-4 bg-surface-2 rounded w-32" />
                  <div className="h-3 bg-surface-2 rounded w-20" />
                </div>
              </div>
              <div className="h-9 bg-surface-2 rounded-lg" />
              <div className="h-9 bg-surface-2 rounded-lg" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
