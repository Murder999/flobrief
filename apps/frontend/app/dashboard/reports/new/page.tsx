"use client";

import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { reportApi, agencyApi, type ReportType, type BrandRead } from "@/lib/api-client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const REPORT_TYPES: { value: ReportType; label: string; description: string }[] = [
  {
    value: "monthly_brand",
    label: "Aylık Marka Raporu",
    description: "Bir markanın aylık brief ve içerik performansını özetler.",
  },
  {
    value: "agency_overview",
    label: "Ajans Genel Özeti",
    description: "Tüm markalar için ajans genelinde performans analizi.",
  },
  {
    value: "campaign_summary",
    label: "Kampanya Özeti",
    description: "Belirli bir dönem için kampanya performans raporu.",
  },
];

function today() {
  return new Date().toISOString().slice(0, 10);
}

function firstOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function NewReportPage() {
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();
  const agencyId = activeAgency?.id ?? null;
  const router = useRouter();

  const [reportType, setReportType] = useState<ReportType>("monthly_brand");
  const [periodStart, setPeriodStart] = useState(firstOfMonth());
  const [periodEnd, setPeriodEnd] = useState(today());
  const [title, setTitle] = useState("");
  const [brandId, setBrandId] = useState<string>("");
  const [brands, setBrands] = useState<BrandRead[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !agencyId) return;
    agencyApi.listBrands(agencyId, accessToken).then(setBrands).catch(() => {});
  }, [accessToken, agencyId]);

  const selectedTypeDef = REPORT_TYPES.find((t) => t.value === reportType)!;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken || !agencyId) return;
    if (!title.trim()) {
      setError("Rapor başlığı gerekli.");
      return;
    }
    if (periodStart > periodEnd) {
      setError("Başlangıç tarihi bitiş tarihinden sonra olamaz.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const report = await reportApi.create(
        {
          report_type: reportType,
          period_start: periodStart,
          period_end: periodEnd,
          title: title.trim(),
          brand_id: brandId || null,
        },
        agencyId,
        accessToken
      );
      router.push(`/dashboard/reports/${report.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rapor oluşturulamadı.");
      setSubmitting(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-8">
        <button
          onClick={() => router.back()}
          className="text-sm text-text-muted hover:text-text transition-colors mb-4 flex items-center gap-1"
        >
          ← Geri
        </button>
        <h1 className="text-2xl font-semibold text-text">Yeni Rapor Oluştur</h1>
        <p className="text-sm text-text-muted mt-1">
          Gerçek verilerden otomatik rapor üretilir.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Report type */}
        <div>
          <label className="block text-sm font-medium text-text mb-3">Rapor Türü</label>
          <div className="space-y-2">
            {REPORT_TYPES.map((rt) => (
              <label
                key={rt.value}
                className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-all ${
                  reportType === rt.value
                    ? "border-accent bg-accent/5"
                    : "border-border bg-surface hover:border-border/80"
                }`}
              >
                <input
                  type="radio"
                  name="reportType"
                  value={rt.value}
                  checked={reportType === rt.value}
                  onChange={() => setReportType(rt.value)}
                  className="mt-0.5 accent-indigo-500"
                />
                <div>
                  <p className="text-sm font-medium text-text">{rt.label}</p>
                  <p className="text-xs text-text-muted mt-0.5">{rt.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Period */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Dönem Başlangıcı
            </label>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:border-accent transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Dönem Bitişi
            </label>
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:border-accent transition-colors"
            />
          </div>
        </div>

        {/* Title */}
        <div>
          <label className="block text-xs font-medium text-text-muted mb-1.5">
            Rapor Başlığı
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={`${selectedTypeDef.label} – ${periodStart.slice(0, 7)}`}
            className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
          />
        </div>

        {/* Brand (optional) */}
        {brands.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">
              Marka (isteğe bağlı)
            </label>
            <select
              value={brandId}
              onChange={(e) => setBrandId(e.target.value)}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text focus:outline-none focus:border-accent transition-colors"
            >
              <option value="">Tüm markalar</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <div className="bg-danger/10 border border-danger/30 rounded-lg p-3 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="flex items-center gap-2 px-5 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-60 transition-colors"
          >
            {submitting ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Oluşturuluyor…
              </>
            ) : (
              "Rapor Oluştur"
            )}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2.5 text-sm text-text-muted hover:text-text transition-colors"
          >
            İptal
          </button>
        </div>
      </form>
    </div>
  );
}
