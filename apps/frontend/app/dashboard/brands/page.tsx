"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { agencyApi, brandIdentityApi, invitationApi, type BrandRead, type BrandIdentityOverview, ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function BrandCardSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-2xl overflow-hidden animate-pulse">
      <div className="h-28 bg-surface-2" />
      <div className="p-4 space-y-2">
        <div className="h-4 bg-surface-2 rounded w-2/3" />
        <div className="h-3 bg-surface-2 rounded w-1/3" />
        <div className="flex gap-1.5 mt-3">
          {[1,2,3].map(i => <div key={i} className="w-5 h-5 rounded-full bg-surface-2" />)}
        </div>
      </div>
    </div>
  );
}

function EmptyBrands({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="col-span-full flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 bg-gradient-to-br from-accent/20 to-accent/5 rounded-2xl flex items-center justify-center mb-4 ring-1 ring-accent/20">
        <svg className="w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-text mb-1">Henüz marka yok</h3>
      <p className="text-sm text-text-muted mb-5 max-w-xs">
        İlk markanızı ekleyin ve brief, takvim ve raporları marka bazlı yönetin.
      </p>
      <button onClick={onAdd} className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors shadow-sm">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Marka Ekle
      </button>
    </div>
  );
}

const STATUS_MAP: Record<string, { label: string; cls: string; dot: string }> = {
  active:   { label: "Aktif",   cls: "text-success",     dot: "bg-success" },
  inactive: { label: "Pasif",   cls: "text-text-muted",  dot: "bg-text-muted/40" },
  archived: { label: "Arşiv",   cls: "text-text-muted",  dot: "bg-text-muted/40" },
};

const DNA_STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  approved:     { label: "DNA Onaylı",  cls: "text-success bg-success/10" },
  reviewed:     { label: "İncelendi",   cls: "text-info bg-info/10" },
  ai_generated: { label: "Analiz OK",   cls: "text-accent bg-accent/10" },
  needs_review: { label: "İnceleme",    cls: "text-warning bg-warning/10" },
  draft:        { label: "Taslak",      cls: "text-text-muted bg-surface-2" },
};

function BrandCard({
  brand,
  dnaOverview,
  onInvite,
}: {
  brand: BrandRead;
  dnaOverview: BrandIdentityOverview | null;
  onInvite: (brand: BrandRead) => void;
}) {
  const st = STATUS_MAP[brand.status] ?? { label: brand.status, cls: "text-text-muted", dot: "bg-text-muted/40" };
  const initials = brand.name.slice(0, 2).toUpperCase();
  const profile = dnaOverview?.profile;
  const dnaStatus = profile ? (DNA_STATUS_LABEL[profile.status] ?? { label: profile.status, cls: "text-text-muted bg-surface-2" }) : null;
  const primaryColors = (profile?.primary_colors ?? []).slice(0, 4) as { hex: string }[];
  const logoSrc = brand.logo_url ? API_BASE + brand.logo_url : null;

  return (
    <div className="group bg-surface border border-border rounded-2xl overflow-hidden hover:border-accent/40 hover:shadow-lg transition-all duration-200 flex flex-col">
      {/* Cover / Logo area */}
      <div className="relative h-28 bg-gradient-to-br from-surface-2 to-surface flex items-center justify-center overflow-hidden">
        {/* Color stripe at top if DNA available */}
        {primaryColors.length > 0 && (
          <div className="absolute top-0 left-0 right-0 h-1 flex">
            {primaryColors.map((c, i) => (
              <div key={i} className="flex-1" style={{ backgroundColor: c.hex }} />
            ))}
          </div>
        )}
        {logoSrc ? (
          <img
            src={logoSrc}
            alt={`${brand.name} logo`}
            className="max-h-16 max-w-[120px] object-contain drop-shadow-sm"
          />
        ) : (
          <div className="w-16 h-16 bg-accent/10 rounded-2xl flex items-center justify-center ring-1 ring-accent/20">
            <span className="text-xl font-bold text-accent tracking-tight">{initials}</span>
          </div>
        )}
        {/* Status dot */}
        <div className="absolute top-3 right-3 flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
          <span className={`text-[10px] font-medium ${st.cls}`}>{st.label}</span>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col">
        <a href={`/dashboard/brands/${brand.id}`} className="block mb-1">
          <h3 className="font-semibold text-sm text-text group-hover:text-accent transition-colors leading-tight">{brand.name}</h3>
        </a>
        <p className="text-xs text-text-muted/60 font-mono mb-3">{brand.slug}</p>

        {/* DNA Status + color swatches */}
        <div className="flex items-center justify-between mb-4">
          {dnaStatus ? (
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${dnaStatus.cls}`}>
              {dnaStatus.label}
            </span>
          ) : (
            <span className="text-[10px] text-text-muted/50 italic">DNA yok</span>
          )}
          {primaryColors.length > 0 && (
            <div className="flex gap-1">
              {primaryColors.map((c, i) => (
                <div
                  key={i}
                  className="w-4 h-4 rounded-full border border-white/20 shadow-sm ring-1 ring-black/5"
                  style={{ backgroundColor: c.hex }}
                  title={c.hex}
                />
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-auto flex gap-2">
          <a
            href={`/dashboard/brands/${brand.id}`}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-surface-2 text-text hover:bg-accent/10 hover:text-accent border border-border hover:border-accent/30 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Marka DNA
          </a>
          <button
            onClick={() => onInvite(brand)}
            className="flex items-center justify-center px-3 py-2 rounded-lg text-xs font-medium text-accent border border-accent/30 hover:bg-accent/10 transition-colors"
            title="Kullanıcı davet et"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

interface InviteBrandMemberModalProps {
  brand: BrandRead | null;
  agencyId: string;
  accessToken: string;
  onClose: () => void;
}

function InviteBrandMemberModal({ brand, agencyId, accessToken, onClose }: InviteBrandMemberModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("brand_manager");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (!brand) { setEmail(""); setRole("brand_manager"); setError(null); setSaving(false); }
  }, [brand]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!brand || !email.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await invitationApi.inviteBrandMember(brand.id, agencyId, { email: email.trim(), role }, accessToken);
      toast(`${email} adresine davet gönderildi.`, "success");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Davet gönderilemedi.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen={!!brand} onClose={onClose} title={`${brand?.name ?? ""} — Marka Yetkilisi Davet Et`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">E-posta Adresi <span className="text-danger">*</span></label>
          <input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="marka@sirket.com"
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors" />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Rol</label>
          <select value={role} onChange={(e) => setRole(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors">
            <option value="brand_manager">Marka Yöneticisi</option>
            <option value="brand_viewer">Marka İzleyici</option>
            <option value="external_approver">Harici Onaylayıcı</option>
          </select>
        </div>
        {error && <p className="text-sm text-danger bg-danger/10 rounded-lg px-3 py-2">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1 border-t border-border">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-surface-2 transition-colors">İptal</button>
          <button type="submit" disabled={saving || !email.trim()} className="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm">
            {saving ? "Gönderiliyor…" : "Davet Gönder"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

interface CreateBrandModalProps {
  isOpen: boolean;
  onClose: () => void;
  agencyId: string;
  accessToken: string;
  onCreated: () => void;
}

function CreateBrandModal({ isOpen, onClose, agencyId, accessToken, onCreated }: CreateBrandModalProps) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (!isOpen) { setName(""); setError(null); setSaving(false); }
  }, [isOpen]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await agencyApi.createBrand(agencyId, { name: name.trim() }, accessToken);
      toast("Marka oluşturuldu.", "success");
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bir hata oluştu.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Yeni Marka">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1">Marka Adı <span className="text-danger">*</span></label>
          <input type="text" required autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Örn: Nike TR, Zara Home..."
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors" />
        </div>
        {error && <p className="text-sm text-danger bg-danger/10 rounded-lg px-3 py-2">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1 border-t border-border">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-surface-2 transition-colors">İptal</button>
          <button type="submit" disabled={saving || !name.trim()} className="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm">
            {saving ? "Oluşturuluyor…" : "Oluştur"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default function BrandsPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;

  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [dnaMap, setDnaMap] = useState<Record<string, BrandIdentityOverview | null>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [inviteBrand, setInviteBrand] = useState<BrandRead | null>(null);

  const fetchBrands = useCallback(async () => {
    if (!accessToken || !agencyId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await agencyApi.listBrands(agencyId, accessToken);
      const list = Array.isArray(data) ? data : [];
      setBrands(list);
      // Fetch DNA overview for each brand in parallel
      const dnaResults = await Promise.allSettled(
        list.map(b => brandIdentityApi.getOverview(b.id, agencyId, accessToken))
      );
      const map: Record<string, BrandIdentityOverview | null> = {};
      list.forEach((b, i) => {
        const r = dnaResults[i];
        map[b.id] = r.status === "fulfilled" ? r.value : null;
      });
      setDnaMap(map);
    } catch {
      setError("Markalar yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !agencyId) setLoading(false);
  }, [workspaceReady, workspaceLoading, agencyId]);

  useEffect(() => { fetchBrands(); }, [fetchBrands]);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-text">Markalar</h1>
          {!loading && <p className="text-sm text-text-muted mt-0.5">{brands.length} marka</p>}
        </div>
        <button onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors shadow-sm">
          <span className="text-base leading-none">+</span>
          Yeni Marka
        </button>
      </div>

      {error ? (
        <div className="rounded-xl border border-danger/20 bg-danger/10 px-5 py-4 text-sm text-danger flex items-center gap-3">
          <span>{error}</span>
          <button onClick={fetchBrands} className="underline hover:no-underline text-danger/80">Tekrar dene</button>
        </div>
      ) : loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <BrandCardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {brands.length === 0 ? (
            <EmptyBrands onAdd={() => setModalOpen(true)} />
          ) : (
            brands.map((b) => (
              <BrandCard key={b.id} brand={b} dnaOverview={dnaMap[b.id] ?? null} onInvite={setInviteBrand} />
            ))
          )}
        </div>
      )}

      {!loading && !agencyId && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 bg-surface-2 rounded-2xl flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-text-muted/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-text mb-1">Ajans seçilmedi</h3>
          <p className="text-sm text-text-muted mb-5 max-w-xs">Devam etmek için bir ajans seçin veya yeni ajans oluşturun.</p>
          <a href="/onboarding/create-agency" className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors shadow-sm">
            Ajans Oluştur
          </a>
        </div>
      )}

      {agencyId && accessToken && (
        <>
          <CreateBrandModal isOpen={modalOpen} onClose={() => setModalOpen(false)} agencyId={agencyId} accessToken={accessToken} onCreated={fetchBrands} />
          <InviteBrandMemberModal brand={inviteBrand} agencyId={agencyId} accessToken={accessToken} onClose={() => setInviteBrand(null)} />
        </>
      )}
    </div>
  );
}
