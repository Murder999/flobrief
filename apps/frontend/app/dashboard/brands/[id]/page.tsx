"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { useToast } from "@/components/ui/toast";
import {
  agencyApi,
  brandIdentityApi,
  type BrandRead,
  type BrandIdentityOverview,
  type BrandIdentityProfileRead,
  type BrandIdentityDocumentRead,
  type BrandIdentityProfileUpdate,
  type ColorEntry,
  type FontEntry,
  ApiError,
} from "@/lib/api-client";

// ── Status helpers ─────────────────────────────────────────────────────────────

const PROFILE_STATUS_CONFIG: Record<string, { label: string; cls: string; dot: string }> = {
  draft:        { label: "Taslak",              cls: "text-text-muted bg-surface-2",      dot: "bg-text-muted" },
  ai_generated: { label: "Analiz Edildi",       cls: "text-info bg-info/10",              dot: "bg-info" },
  reviewed:     { label: "İncelendi",           cls: "text-warning bg-warning/10",        dot: "bg-warning" },
  approved:     { label: "Onaylandı",           cls: "text-success bg-success/10",        dot: "bg-success" },
};

const DOC_STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  uploaded:     { label: "Yüklendi",            cls: "text-text-muted bg-surface-2" },
  processing:   { label: "İşleniyor",           cls: "text-info bg-info/10" },
  analyzed:     { label: "Analiz Tamamlandı",   cls: "text-success bg-success/10" },
  needs_review: { label: "İnceleme Gerekli",    cls: "text-warning bg-warning/10" },
  approved:     { label: "Onaylandı",           cls: "text-success bg-success/10" },
  failed:       { label: "Hata",                cls: "text-danger bg-danger/10" },
};

const PROFILE_STATUS_DESC: Record<string, string> = {
  draft:        "Manuel oluşturuldu, analiz yapılmadı.",
  ai_generated: "Otomatik analiz tamamlandı. İncelemeniz önerilir.",
  needs_review: "PDF görüntü tabanlı, metin çıkarılamadı. Manuel inceleme gerekli.",
  reviewed:     "İncelendi, onay bekliyor.",
  approved:     "Marka DNA onaylandı ve aktif.",
};

type TabKey = "genel" | "dna" | "dosyalar";

// ── DNA Card wrapper ───────────────────────────────────────────────────────────

function DNACard({
  title,
  children,
  colSpan,
  accent,
  onEdit,
}: {
  title: string;
  children: React.ReactNode;
  colSpan?: boolean;
  accent?: "success" | "danger" | "accent";
  onEdit?: () => void;
}) {
  const headerCls = accent === "success" ? "text-success" : accent === "danger" ? "text-danger" : accent === "accent" ? "text-accent" : "text-text-muted";
  const borderCls = accent === "success" ? "border-success/20" : accent === "danger" ? "border-danger/20" : accent === "accent" ? "border-accent/20 bg-gradient-to-r from-accent/5 to-transparent" : "border-border";
  return (
    <div className={`bg-surface rounded-xl p-5 border ${borderCls}${colSpan ? " lg:col-span-2" : ""}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className={`text-xs font-semibold uppercase tracking-wider ${headerCls}`}>{title}</h3>
        {onEdit && (
          <button onClick={onEdit} className="text-[11px] text-text-muted hover:text-accent transition-colors">Düzenle</button>
        )}
      </div>
      {children}
    </div>
  );
}

// ── DNA Empty state ────────────────────────────────────────────────────────────

function DNAEmpty({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2.5 py-2">
      <div className="w-1.5 h-1.5 rounded-full bg-text-muted/30 flex-shrink-0" />
      <p className="text-xs text-text-muted/60 italic">
        {label} PDF&apos;te tespit edilemedi — Düzenle butonu ile manuel ekleyebilirsiniz.
      </p>
    </div>
  );
}

// ── Color Swatch ──────────────────────────────────────────────────────────────

function ColorSwatch({ color }: { color: ColorEntry }) {
  const [copied, setCopied] = useState(false);
  const isEstimated = color.source === "visual_extraction";
  const copy = () => {
    if (!color.hex) return;
    navigator.clipboard.writeText(color.hex);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex flex-col gap-2 group">
      <div
        className="w-full h-20 rounded-xl border border-border cursor-pointer relative overflow-hidden"
        style={{ backgroundColor: color.hex ?? "#e5e7eb" }}
        onClick={copy}
        title="HEX kodunu kopyala"
      >
        {isEstimated && (
          <span className="absolute top-1 left-1 text-[9px] font-semibold bg-amber-500/90 text-white px-1.5 py-0.5 rounded-full leading-none">
            Tahmini
          </span>
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
          {copied ? (
            <span className="text-white text-xs font-medium bg-black/40 px-2 py-0.5 rounded">Kopyalandı!</span>
          ) : (
            <span className="text-white text-xs font-medium bg-black/0 group-hover:bg-black/30 px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-all">Kopyala</span>
          )}
        </div>
      </div>
      <div className="space-y-0.5">
        {color.name && <p className="text-xs font-medium text-text">{color.name}</p>}
        {color.hex && <p className="text-xs font-mono text-text-muted">{color.hex}</p>}
        {color.rgb && <p className="text-xs text-text-muted/70">RGB: {color.rgb}</p>}
        {color.usage && <p className="text-xs text-text-muted/60 leading-tight">{color.usage}</p>}
      </div>
    </div>
  );
}

// ── Font Card ────────────────────────────────────────────────────────────────

function FontCard({ font }: { font: FontEntry }) {
  return (
    <div className="bg-surface-2/50 rounded-xl p-4 border border-border/50">
      <div className="flex items-start justify-between mb-2">
        {font.role && (
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted px-2 py-0.5 bg-surface-2 rounded-full">
            {font.role}
          </span>
        )}
        {font.weight && (
          <span className="text-xs text-text-muted">
            {font.weight}
          </span>
        )}
      </div>
      {font.family && (
        <p className="text-lg font-semibold text-text mt-2" style={{ fontFamily: `'${font.family}', sans-serif` }}>
          {font.family}
        </p>
      )}
      <p className="text-sm text-text-muted/70 mt-0.5" style={{ fontFamily: font.family ? `'${font.family}', sans-serif` : undefined }}>
        Aa Bb Cc 0123 — Örnek metin
      </p>
      {font.usage && <p className="text-xs text-text-muted mt-2 leading-tight">{font.usage}</p>}
    </div>
  );
}

// ── Rule List ────────────────────────────────────────────────────────────────

function RuleList({ rules, variant = "do" }: { rules: string[]; variant?: "do" | "dont" }) {
  const dot = variant === "do"
    ? "bg-success"
    : "bg-danger";
  return (
    <ul className="space-y-2">
      {rules.map((rule, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-text">
          <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
          {rule}
        </li>
      ))}
    </ul>
  );
}

// ── Edit Drawer ───────────────────────────────────────────────────────────────

function EditDrawer({
  profile,
  onClose,
  onSave,
}: {
  profile: BrandIdentityProfileRead;
  onClose: () => void;
  onSave: (data: BrandIdentityProfileUpdate) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const [summary, setSummary] = useState(profile.summary ?? "");
  const [doRules, setDoRules] = useState((profile.do_rules ?? []).join("\n"));
  const [dontRules, setDontRules] = useState((profile.dont_rules ?? []).join("\n"));
  const [keyTakeaways, setKeyTakeaways] = useState((profile.key_takeaways ?? []).join("\n"));
  const [socialNotes, setSocialNotes] = useState((profile.social_media_notes ?? []).join("\n"));
  const [logoRules, setLogoRules] = useState((profile.logo_rules ?? []).join("\n"));
  const [changeNote, setChangeNote] = useState("");

  async function handleSave() {
    setSaving(true);
    const parseLines = (s: string) => s.split("\n").map(l => l.trim()).filter(Boolean);
    await onSave({
      summary: summary || null,
      do_rules: parseLines(doRules).length > 0 ? parseLines(doRules) : null,
      dont_rules: parseLines(dontRules).length > 0 ? parseLines(dontRules) : null,
      key_takeaways: parseLines(keyTakeaways).length > 0 ? parseLines(keyTakeaways) : null,
      social_media_notes: parseLines(socialNotes).length > 0 ? parseLines(socialNotes) : null,
      logo_rules: parseLines(logoRules).length > 0 ? parseLines(logoRules) : null,
      change_note: changeNote || null,
    });
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-xl bg-surface shadow-2xl flex flex-col h-full overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-base font-semibold text-text">Marka DNA Düzenle</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-2 text-text-muted hover:text-text transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Marka Özeti</label>
            <textarea
              value={summary}
              onChange={e => setSummary(e.target.value)}
              rows={4}
              placeholder="Markanın kurumsal kimliğini kısaca özetleyin…"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Logo Kuralları <span className="text-text-muted/60">(her satır bir kural)</span></label>
            <textarea
              value={logoRules}
              onChange={e => setLogoRules(e.target.value)}
              rows={3}
              placeholder="Logonun etrafında güvenli alan bırakılmalıdır&#10;Logo renkli arka planlarda beyaz kullanılır"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Yapılacaklar <span className="text-text-muted/60">(her satır bir madde)</span></label>
            <textarea
              value={doRules}
              onChange={e => setDoRules(e.target.value)}
              rows={4}
              placeholder="Lacivert arka plan kullanın&#10;Montserrat fontunu tercih edin"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Yapılmayacaklar <span className="text-text-muted/60">(her satır bir madde)</span></label>
            <textarea
              value={dontRules}
              onChange={e => setDontRules(e.target.value)}
              rows={4}
              placeholder="Logo üzerine metin yazılmaz&#10;Mor ve sarı renkler kullanılmaz"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">5 Kritik Kural <span className="text-text-muted/60">(her satır bir kural)</span></label>
            <textarea
              value={keyTakeaways}
              onChange={e => setKeyTakeaways(e.target.value)}
              rows={5}
              placeholder="Asla sarı renk kullanma&#10;Font her zaman Montserrat olmalı"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Sosyal Medya Notları <span className="text-text-muted/60">(her satır bir not)</span></label>
            <textarea
              value={socialNotes}
              onChange={e => setSocialNotes(e.target.value)}
              rows={3}
              placeholder="Instagram'da reels formatı tercih edilir&#10;Story'lerde beyaz metin kullanılır"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Değişiklik Notu <span className="text-text-muted/60">(isteğe bağlı)</span></label>
            <input
              type="text"
              value={changeNote}
              onChange={e => setChangeNote(e.target.value)}
              placeholder="Renk paleti güncellendi…"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            />
          </div>
        </div>
        <div className="px-6 py-4 border-t border-border flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
          >
            Vazgeç
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50 shadow-sm"
          >
            {saving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Upload Area ───────────────────────────────────────────────────────────────

function UploadArea({ onFile }: { onFile: (f: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
        dragging ? "border-accent bg-accent/5" : "border-border hover:border-accent/50 hover:bg-surface-2/50"
      }`}
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
      <div className="w-12 h-12 bg-accent/10 rounded-xl flex items-center justify-center mx-auto mb-3">
        <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>
      <p className="text-sm font-medium text-text mb-1">PDF dosyasını buraya sürükleyin</p>
      <p className="text-xs text-text-muted">veya dosya seçmek için tıklayın · Maks. 50 MB</p>
    </div>
  );
}

// ── DNA Tab ────────────────────────────────────────────────────────────────────

function DNATab({
  overview,
  brandId,
  agencyId,
  accessToken,
  onRefresh,
}: {
  overview: BrandIdentityOverview;
  brandId: string;
  agencyId: string;
  accessToken: string;
  onRefresh: () => void;
}) {
  const { toast } = useToast();
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [approving, setApproving] = useState(false);

  const profile = overview.profile;
  const ps = profile ? PROFILE_STATUS_CONFIG[profile.status] : null;

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      await brandIdentityApi.uploadDocument(brandId, agencyId, file, accessToken);
      toast("PDF yüklendi ve analiz başlatıldı.", "success");
      onRefresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Yükleme hatası.", "error");
    } finally {
      setUploading(false);
    }
  }

  async function handleAnalyze(docId: string) {
    setAnalyzing(docId);
    try {
      await brandIdentityApi.analyzeDocument(brandId, docId, agencyId, accessToken);
      toast("Analiz tamamlandı.", "success");
      onRefresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Analiz hatası.", "error");
    } finally {
      setAnalyzing(null);
    }
  }

  async function handleSaveProfile(data: BrandIdentityProfileUpdate) {
    try {
      await brandIdentityApi.updateProfile(brandId, agencyId, data, accessToken);
      toast("Marka DNA güncellendi.", "success");
      setEditOpen(false);
      onRefresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Güncelleme hatası.", "error");
      throw err;
    }
  }

  async function handleApprove() {
    setApproving(true);
    try {
      await brandIdentityApi.approveProfile(brandId, agencyId, accessToken);
      toast("Marka DNA onaylandı.", "success");
      onRefresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Onaylama hatası.", "error");
    } finally {
      setApproving(false);
    }
  }

  if (!profile && overview.documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-16 h-16 bg-gradient-to-br from-accent/20 to-accent/5 rounded-2xl flex items-center justify-center mb-4 ring-1 ring-accent/20">
          <svg className="w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 className="text-base font-semibold text-text mb-2">Henüz Marka DNA oluşturulmadı</h3>
        <p className="text-sm text-text-muted mb-1 max-w-sm">
          Kurumsal kimlik PDF&apos;ini yükleyin. Sistem otomatik analiz ederek renk paleti, tipografi, ton ve kuralları çıkarır.
        </p>
        <p className="text-xs text-text-muted/60 mb-8 max-w-sm">
          Analiz sonucu düzenlenebilir ve onaylanabilir.
        </p>
        <div className="w-full max-w-md">
          {uploading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-text-muted">
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Yükleniyor…
            </div>
          ) : (
            <UploadArea onFile={handleUpload} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header hero card */}
      <div className="bg-gradient-to-r from-accent/5 to-transparent border border-border rounded-xl p-5 flex items-start gap-4">
        <div className="w-10 h-10 bg-accent/10 rounded-xl flex items-center justify-center flex-shrink-0">
          <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h2 className="text-sm font-semibold text-text">Marka DNA</h2>
            {ps && (
              <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${ps.cls}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${ps.dot}`} />
                {ps.label}
              </span>
            )}
            {!profile && (
              <span className="text-[11px] font-medium text-text-muted bg-surface-2 px-2 py-0.5 rounded-full">
                Profil Yok
              </span>
            )}
          </div>
          <p className="text-xs text-text-muted">
            Kurumsal kimlikten çıkarılan uygulanabilir marka özeti. Ajans ekibi bu bilgileri brief ve üretim süreçlerinde referans alır.
          </p>
          {profile?.approved_by_name && (
            <p className="text-xs text-text-muted/70 mt-1">
              Onaylayan: {profile.approved_by_name}
              {profile.approved_at && ` · ${new Date(profile.approved_at).toLocaleDateString("tr-TR")}`}
            </p>
          )}
          {profile?.confidence_score != null && (
            <p className="text-xs text-text-muted/60 mt-1">
              Analiz güven skoru: {profile.confidence_score}/95
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {profile && profile.status !== "approved" && (
            <button
              onClick={handleApprove}
              disabled={approving}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-success/10 text-success hover:bg-success/20 transition-colors disabled:opacity-50"
            >
              {approving ? "Onaylanıyor…" : "Onayla"}
            </button>
          )}
          {profile && (
            <button
              onClick={() => setEditOpen(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border text-text-muted hover:text-text hover:border-accent/40 transition-colors"
            >
              Düzenle
            </button>
          )}
          {!uploading ? (
            <label className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:bg-accent/90 transition-colors cursor-pointer shadow-sm">
              PDF Yükle
              <input
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
              />
            </label>
          ) : (
            <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/20 text-accent">
              Yükleniyor…
            </span>
          )}
        </div>
      </div>

      {/* DNA Cards */}
      {profile ? (
        <div className="grid gap-5 lg:grid-cols-2">

          {/* Marka Özeti */}
          <DNACard title="Marka Özeti" colSpan onEdit={() => setEditOpen(true)}>
            {profile.summary ? (
              <p className="text-sm text-text leading-relaxed">{profile.summary}</p>
            ) : (
              <DNAEmpty label="Marka özeti" />
            )}
          </DNACard>

          {/* Renk Paleti */}
          <DNACard title="Renk Paleti" colSpan onEdit={() => setEditOpen(true)}>
            {(profile.primary_colors && profile.primary_colors.length > 0) ||
             (profile.secondary_colors && profile.secondary_colors.length > 0) ? (
              <div className="space-y-5">
                {profile.primary_colors && profile.primary_colors.length > 0 && (
                  <div>
                    <p className="text-xs text-text-muted/70 mb-3 font-medium">Ana Renkler</p>
                    <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
                      {profile.primary_colors.map((c, i) => <ColorSwatch key={i} color={c} />)}
                    </div>
                  </div>
                )}
                {profile.secondary_colors && profile.secondary_colors.length > 0 && (
                  <div>
                    <p className="text-xs text-text-muted/70 mb-3 font-medium">Yardımcı Renkler</p>
                    <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
                      {profile.secondary_colors.map((c, i) => <ColorSwatch key={i} color={c} />)}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <DNAEmpty label="Renk paleti — HEX, RGB veya CMYK renk kodları" />
            )}
          </DNACard>

          {/* Tipografi */}
          <DNACard title="Tipografi" colSpan onEdit={() => setEditOpen(true)}>
            {profile.typography && profile.typography.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {profile.typography.map((f, i) => <FontCard key={i} font={f} />)}
              </div>
            ) : (
              <DNAEmpty label="Tipografi — font adları ve kullanım rolleri" />
            )}
          </DNACard>

          {/* Logo Kuralları */}
          <DNACard title="Logo Kullanım Kuralları" onEdit={() => setEditOpen(true)}>
            {profile.logo_rules && profile.logo_rules.length > 0 ? (
              <ul className="space-y-2">
                {profile.logo_rules.map((rule, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                    {rule}
                  </li>
                ))}
              </ul>
            ) : (
              <DNAEmpty label="Logo kuralları" />
            )}
          </DNACard>

          {/* Görsel Stil */}
          <DNACard title="Görsel Stil" onEdit={() => setEditOpen(true)}>
            {profile.visual_style ? (
              <div className="space-y-3">
                {profile.visual_style.tags && Array.isArray(profile.visual_style.tags) && (profile.visual_style.tags as string[]).length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {(profile.visual_style.tags as string[]).map((tag, i) => (
                      <span key={i} className="text-xs px-2.5 py-1 rounded-full bg-accent/10 text-accent font-medium">{tag}</span>
                    ))}
                  </div>
                )}
                {profile.visual_style.description && (
                  <p className="text-sm text-text">{String(profile.visual_style.description)}</p>
                )}
              </div>
            ) : (
              <DNAEmpty label="Görsel stil ve tasarım ilkeleri" />
            )}
          </DNACard>

          {/* İletişim Tonu */}
          <DNACard title="İletişim Tonu" onEdit={() => setEditOpen(true)}>
            {profile.tone_of_voice ? (
              <div className="space-y-3">
                {profile.tone_of_voice.tags && Array.isArray(profile.tone_of_voice.tags) && (profile.tone_of_voice.tags as string[]).length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {(profile.tone_of_voice.tags as string[]).map((tag, i) => (
                      <span key={i} className="text-xs px-2.5 py-1 rounded-full bg-warning/10 text-warning font-medium">{tag}</span>
                    ))}
                  </div>
                )}
                {profile.tone_of_voice.summary && (
                  <p className="text-sm text-text">{String(profile.tone_of_voice.summary)}</p>
                )}
                {profile.tone_of_voice.preferred_words && Array.isArray(profile.tone_of_voice.preferred_words) && (profile.tone_of_voice.preferred_words as string[]).length > 0 && (
                  <div>
                    <p className="text-xs text-text-muted/70 mb-1.5">Kullanılacak kelimeler</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(profile.tone_of_voice.preferred_words as string[]).map((w, i) => (
                        <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-success/10 text-success">{w}</span>
                      ))}
                    </div>
                  </div>
                )}
                {profile.tone_of_voice.avoid_words && Array.isArray(profile.tone_of_voice.avoid_words) && (profile.tone_of_voice.avoid_words as string[]).length > 0 && (
                  <div>
                    <p className="text-xs text-text-muted/70 mb-1.5">Kaçınılacak kelimeler</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(profile.tone_of_voice.avoid_words as string[]).map((w, i) => (
                        <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-danger/10 text-danger">{w}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <DNAEmpty label="İletişim tonu ve dil özellikleri" />
            )}
          </DNACard>

          {/* Sosyal Medya */}
          <DNACard title="Sosyal Medya Notları" onEdit={() => setEditOpen(true)}>
            {profile.social_media_notes && profile.social_media_notes.length > 0 ? (
              <ul className="space-y-2">
                {profile.social_media_notes.map((note, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-info flex-shrink-0" />
                    {note}
                  </li>
                ))}
              </ul>
            ) : (
              <DNAEmpty label="Sosyal medya ve dijital içerik notları" />
            )}
          </DNACard>

          {/* Yapılacaklar */}
          <DNACard title="Yapılacaklar" accent="success" onEdit={() => setEditOpen(true)}>
            {profile.do_rules && profile.do_rules.length > 0 ? (
              <RuleList rules={profile.do_rules} variant="do" />
            ) : (
              <DNAEmpty label="Doğru kullanım kuralları" />
            )}
          </DNACard>

          {/* Yapılmayacaklar */}
          <DNACard title="Yapılmayacaklar" accent="danger" onEdit={() => setEditOpen(true)}>
            {profile.dont_rules && profile.dont_rules.length > 0 ? (
              <RuleList rules={profile.dont_rules} variant="dont" />
            ) : (
              <DNAEmpty label="Yasak / kaçınılacak kullanımlar" />
            )}
          </DNACard>

          {/* Ajans İçin 5 Kritik Kural */}
          <DNACard title="Ajans İçin 5 Kritik Kural" colSpan accent="accent" onEdit={() => setEditOpen(true)}>
            {profile.key_takeaways && profile.key_takeaways.length > 0 ? (
              <div className="grid sm:grid-cols-2 gap-2">
                {profile.key_takeaways.map((rule, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-surface rounded-lg border border-border">
                    <span className="w-6 h-6 bg-accent/10 rounded-full flex items-center justify-center text-accent text-xs font-bold flex-shrink-0">
                      {i + 1}
                    </span>
                    <p className="text-sm text-text">{rule}</p>
                  </div>
                ))}
              </div>
            ) : (
              <DNAEmpty label="Kritik marka kuralları" />
            )}
          </DNACard>

          {/* Analiz Bilgisi */}
          <div className="lg:col-span-2 bg-surface-2/50 rounded-xl p-4 border border-border/50">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Analiz Bilgisi</h3>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              <div>
                <p className="text-text-muted/60 mb-1">Analiz Durumu</p>
                <p className={`font-medium ${ps?.cls?.split(" ")[0] ?? "text-text"}`}>{ps?.label ?? "—"}</p>
                <p className="text-text-muted/50 mt-0.5">{PROFILE_STATUS_DESC[profile.status] ?? ""}</p>
              </div>
              <div>
                <p className="text-text-muted/60 mb-1">Güven Skoru</p>
                {profile.confidence_score != null && profile.confidence_score > 0 ? (
                  <>
                    <p className={`font-medium ${
                      profile.confidence_score >= 71 ? "text-success" :
                      profile.confidence_score >= 41 ? "text-warning" : "text-danger"
                    }`}>{profile.confidence_score}/95</p>
                    <p className="text-text-muted/50 mt-0.5">
                      {profile.confidence_score >= 71 ? "Yüksek — sonuçlar güvenilir" :
                       profile.confidence_score >= 41 ? "Orta — manuel inceleme önerilir" :
                       "Düşük — PDF metin içermiyor olabilir"}
                    </p>
                  </>
                ) : (
                  <p className="text-text-muted">Hesaplanamadı</p>
                )}
              </div>
              <div>
                <p className="text-text-muted/60 mb-1">Son Güncelleme</p>
                <p className="text-text">{new Date(profile.updated_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}</p>
              </div>
              <div>
                <p className="text-text-muted/60 mb-1">Kaynak Dosya</p>
                {overview.documents[0] ? (
                  <div>
                    <p className="text-text truncate">{overview.documents[0].file_name}</p>
                    {overview.documents[0].extraction_method && (
                      <span className="inline-block mt-1 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-surface-2 text-text-muted border border-border/50">
                        {overview.documents[0].extraction_method}
                      </span>
                    )}
                    {overview.documents[0].page_count && (
                      <p className="text-text-muted/50 mt-0.5">{overview.documents[0].page_count} sayfa</p>
                    )}
                  </div>
                ) : (
                  <p className="text-text-muted/50">Dosya yok</p>
                )}
              </div>
            </div>
            {/* Debug notes (image-based warning, missing deps, etc.) */}
            {overview.documents[0]?.extraction_debug_json?.notes && overview.documents[0].extraction_debug_json.notes.length > 0 && (
              <div className="mt-3 pt-3 border-t border-border/50 space-y-1">
                {overview.documents[0].extraction_debug_json.notes.map((note, i) => {
                  const isMissingDep = note === "pymupdf_unavailable" || note === "pypdf_unavailable";
                  const display = note === "pymupdf_unavailable"
                    ? "PyMuPDF yüklü değil — Docker image'ı rebuild edin veya pip install pymupdf çalıştırın"
                    : note === "pypdf_unavailable"
                    ? "pypdf yüklü değil — Docker image'ı rebuild edin veya pip install pypdf çalıştırın"
                    : note;
                  return (
                  <p key={i} className={`text-xs flex items-start gap-1.5 ${isMissingDep ? "text-danger" : "text-amber-600 dark:text-amber-400"}`}>
                    <span className="mt-0.5 shrink-0">{isMissingDep ? "✕" : "⚠"}</span>
                    <span>{display}</span>
                  </p>
                  );
                })}
              </div>
            )}
            {profile.approved_by_name && (
              <p className="text-xs text-text-muted/60 mt-3 border-t border-border/50 pt-3">
                Onaylayan: <span className="text-text">{profile.approved_by_name}</span>
                {profile.approved_at && ` · ${new Date(profile.approved_at).toLocaleDateString("tr-TR")}`}
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="w-12 h-12 bg-surface-2 rounded-xl flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-text mb-1">Marka DNA profili oluşturulmadı</p>
          <p className="text-xs text-text-muted">PDF yükleyip &quot;Analiz Et&quot;e basın veya Dosyalar sekmesinden mevcut belgeyi analiz edin.</p>
        </div>
      )}

      {editOpen && profile && (
        <EditDrawer
          profile={profile}
          onClose={() => setEditOpen(false)}
          onSave={handleSaveProfile}
        />
      )}
    </div>
  );
}

// ── Documents Tab ────────────────────────────────────────────────────────────

function DocumentsTab({
  docs,
  brandId,
  agencyId,
  accessToken,
  onRefresh,
}: {
  docs: BrandIdentityDocumentRead[];
  brandId: string;
  agencyId: string;
  accessToken: string;
  onRefresh: () => void;
}) {
  const { toast } = useToast();
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState<string | null>(null);

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      await brandIdentityApi.uploadDocument(brandId, agencyId, file, accessToken);
      toast("PDF yüklendi.", "success");
      onRefresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Yükleme hatası.", "error");
    } finally {
      setUploading(false);
    }
  }

  async function handleAnalyze(docId: string) {
    setAnalyzing(docId);
    try {
      await brandIdentityApi.analyzeDocument(brandId, docId, agencyId, accessToken);
      toast("Analiz tamamlandı.", "success");
      onRefresh();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Analiz hatası.", "error");
    } finally {
      setAnalyzing(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Kurumsal Kimlik Dosyaları</h3>
        {!uploading ? (
          <label className="inline-flex items-center gap-2 px-3 py-1.5 bg-accent text-white rounded-lg text-xs font-medium cursor-pointer hover:bg-accent/90 transition-colors shadow-sm">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            PDF Yükle
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
            />
          </label>
        ) : (
          <span className="text-xs text-text-muted animate-pulse">Yükleniyor…</span>
        )}
      </div>

      {docs.length === 0 ? (
        <div className="py-10 text-center">
          {uploading ? (
            <p className="text-sm text-text-muted animate-pulse">PDF yükleniyor…</p>
          ) : (
            <UploadArea onFile={handleUpload} />
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {docs.map(doc => {
            const ds = DOC_STATUS_CONFIG[doc.status] ?? { label: doc.status, cls: "text-text-muted bg-surface-2" };
            return (
              <div key={doc.id} className="flex items-center gap-4 p-4 bg-surface border border-border rounded-xl hover:border-accent/30 transition-colors">
                <div className="w-9 h-9 bg-danger/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text truncate">{doc.file_name}</p>
                  <p className="text-xs text-text-muted">
                    {(doc.file_size / 1024).toFixed(0)} KB ·{" "}
                    {new Date(doc.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}
                  </p>
                  {doc.analysis_error && (
                    <p className="text-xs text-danger mt-0.5">{doc.analysis_error}</p>
                  )}
                </div>
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${ds.cls}`}>
                  {ds.label}
                </span>
                {(doc.status === "uploaded" || doc.status === "failed" || doc.status === "analyzed") && (
                  <button
                    onClick={() => handleAnalyze(doc.id)}
                    disabled={analyzing === doc.id}
                    className="text-xs text-accent hover:underline disabled:opacity-50 flex-shrink-0"
                  >
                    {analyzing === doc.id ? "Analiz ediliyor…" : "Analiz Et"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function LogoUploader({
  brand,
  agencyId,
  accessToken,
  onUpdated,
}: {
  brand: BrandRead;
  agencyId: string;
  accessToken: string;
  onUpdated: (b: BrandRead) => void;
}) {
  const { toast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const logoSrc = brand.logo_url ? API_BASE_URL + brand.logo_url : null;

  async function handleFile(file: File) {
    setUploading(true);
    try {
      const updated = await agencyApi.uploadBrandLogo(brand.id, agencyId, file, accessToken);
      onUpdated(updated);
      toast("Logo güncellendi.", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Logo yüklenemedi.", "error");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete() {
    setUploading(true);
    try {
      const updated = await agencyApi.deleteBrandLogo(brand.id, agencyId, accessToken);
      onUpdated(updated);
      toast("Logo silindi.", "success");
    } catch {
      toast("Logo silinemedi.", "error");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="relative group/logo">
      {/* Logo display */}
      <div className="w-20 h-20 rounded-2xl border-2 border-border bg-surface-2 flex items-center justify-center overflow-hidden shadow-sm">
        {logoSrc ? (
          <img src={logoSrc} alt={brand.name} className="w-full h-full object-contain p-1.5" />
        ) : (
          <span className="text-2xl font-bold text-accent tracking-tight">{brand.name.slice(0, 2).toUpperCase()}</span>
        )}
        {uploading && (
          <div className="absolute inset-0 bg-surface/60 rounded-2xl flex items-center justify-center">
            <svg className="w-5 h-5 text-accent animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        )}
      </div>
      {/* Hover overlay */}
      {!uploading && (
        <div className="absolute inset-0 rounded-2xl bg-black/50 opacity-0 group-hover/logo:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1">
          <button
            onClick={() => inputRef.current?.click()}
            className="text-white text-[10px] font-semibold leading-none"
          >
            {logoSrc ? "Değiştir" : "Logo Ekle"}
          </button>
          {logoSrc && (
            <button onClick={handleDelete} className="text-red-300 text-[9px] leading-none">Sil</button>
          )}
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/svg+xml"
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
      />
    </div>
  );
}

export default function BrandDetailPage() {
  const params = useParams();
  const router = useRouter();
  const brandId = params.id as string;
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? "";

  const [brand, setBrand] = useState<BrandRead | null>(null);
  const [overview, setOverview] = useState<BrandIdentityOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("dna");

  const fetchData = useCallback(async () => {
    if (!accessToken || !agencyId || !brandId) return;
    setLoading(true);
    try {
      const [b, ov] = await Promise.all([
        agencyApi.getBrand(brandId, agencyId, accessToken),
        brandIdentityApi.getOverview(brandId, agencyId, accessToken),
      ]);
      setBrand(b);
      setOverview(ov);
    } catch {
      // errors handled via null states
    } finally {
      setLoading(false);
    }
  }, [accessToken, agencyId, brandId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const TABS: { id: TabKey; label: string }[] = [
    { id: "dna",      label: "Marka DNA" },
    { id: "dosyalar", label: "Kurumsal Kimlik Dosyaları" },
    { id: "genel",    label: "Genel Bilgiler" },
  ];

  if (loading) {
    return (
      <div className="p-8 max-w-5xl mx-auto animate-pulse space-y-6">
        <div className="h-4 bg-surface-2 rounded w-24" />
        <div className="flex items-center gap-4">
          <div className="w-20 h-20 bg-surface-2 rounded-2xl" />
          <div className="space-y-2">
            <div className="h-6 bg-surface-2 rounded w-40" />
            <div className="h-3 bg-surface-2 rounded w-24" />
          </div>
        </div>
        <div className="flex gap-2">
          {[1, 2, 3].map(i => <div key={i} className="h-8 bg-surface-2 rounded-lg w-28" />)}
        </div>
        <div className="h-64 bg-surface-2 rounded-xl" />
      </div>
    );
  }

  if (!brand) {
    return (
      <div className="p-8 max-w-5xl mx-auto text-center py-20">
        <p className="text-text-muted">Marka bulunamadı.</p>
        <button onClick={() => router.back()} className="mt-4 text-sm text-accent hover:underline">Geri dön</button>
      </div>
    );
  }

  const dnaProfile = overview?.profile;
  const primaryColors = (dnaProfile?.primary_colors ?? []).slice(0, 5) as { hex: string }[];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 text-xs text-text-muted mb-5">
        <button onClick={() => router.push("/dashboard/brands")} className="hover:text-text transition-colors">Markalar</button>
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-text">{brand.name}</span>
      </div>

      {/* Brand Header Card */}
      <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-6 shadow-sm">
        {/* Color strip from DNA palette */}
        {primaryColors.length > 0 && (
          <div className="flex h-1.5">
            {primaryColors.map((c, i) => (
              <div key={i} className="flex-1" style={{ backgroundColor: c.hex }} />
            ))}
          </div>
        )}
        <div className="p-6 flex items-center gap-5">
          <LogoUploader
            brand={brand}
            agencyId={agencyId}
            accessToken={accessToken ?? ""}
            onUpdated={setBrand}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <h1 className="text-2xl font-bold text-text leading-tight">{brand.name}</h1>
              <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                brand.status === "active" ? "text-success bg-success/10" : "text-text-muted bg-surface-2"
              }`}>
                {brand.status === "active" ? "Aktif" : brand.status}
              </span>
              {dnaProfile && (
                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                  PROFILE_STATUS_CONFIG[dnaProfile.status]?.cls ?? "text-text-muted bg-surface-2"
                }`}>
                  DNA: {PROFILE_STATUS_CONFIG[dnaProfile.status]?.label ?? dnaProfile.status}
                </span>
              )}
            </div>
            <p className="text-xs text-text-muted/60 font-mono mb-3">{brand.slug}</p>
            {/* Quick color palette */}
            {primaryColors.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-text-muted/50 font-medium uppercase tracking-wider">Palet</span>
                <div className="flex gap-1.5">
                  {primaryColors.map((c, i) => (
                    <div
                      key={i}
                      className="w-5 h-5 rounded-full border border-white/20 shadow-sm ring-1 ring-black/5"
                      style={{ backgroundColor: c.hex }}
                      title={c.hex}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
          {dnaProfile?.tone_of_voice && Array.isArray((dnaProfile.tone_of_voice as {tags?:string[]}).tags) && (
            <div className="hidden lg:flex flex-col gap-1 items-end shrink-0 max-w-[180px]">
              <span className="text-[10px] text-text-muted/50 font-medium uppercase tracking-wider mb-1">Ton</span>
              <div className="flex flex-wrap gap-1 justify-end">
                {((dnaProfile.tone_of_voice as {tags: string[]}).tags).slice(0, 4).map((t, i) => (
                  <span key={i} className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-surface-2 text-text-muted">{t}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border mb-6">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors -mb-px ${
              activeTab === t.id
                ? "text-accent border-b-2 border-accent bg-accent/5"
                : "text-text-muted hover:text-text hover:bg-surface-2"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "dna" && overview && (
        <DNATab
          overview={overview}
          brandId={brandId}
          agencyId={agencyId}
          accessToken={accessToken ?? ""}
          onRefresh={fetchData}
        />
      )}

      {activeTab === "dosyalar" && overview && (
        <DocumentsTab
          docs={overview.documents}
          brandId={brandId}
          agencyId={agencyId}
          accessToken={accessToken ?? ""}
          onRefresh={fetchData}
        />
      )}

      {activeTab === "genel" && (
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Marka Bilgileri</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-text-muted">Durum</dt>
                <dd className="text-text font-medium">{brand.status === "active" ? "Aktif" : brand.status}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">Slug</dt>
                <dd className="text-text font-mono text-xs">{brand.slug}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">Oluşturma Tarihi</dt>
                <dd className="text-text">{new Date(brand.created_at).toLocaleDateString("tr-TR")}</dd>
              </div>
            </dl>
          </div>
          {/* Logo management card */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Marka Logosu</h3>
            <p className="text-xs text-text-muted mb-4">PNG, JPEG, WebP veya SVG · Maks. 5 MB</p>
            <LogoUploader brand={brand} agencyId={agencyId} accessToken={accessToken ?? ""} onUpdated={setBrand} />
          </div>
        </div>
      )}
    </div>
  );
}
