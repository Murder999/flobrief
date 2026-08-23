"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { templateApi, industryApi, type IndustryRead, ApiError } from "@/lib/api-client";
import { useEffect } from "react";

export default function NewTemplatePage() {
  const router = useRouter();
  const { accessToken } = useAuth();
  const { activeAgency } = useWorkspace();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [industry, setIndustry] = useState("");
  const [industries, setIndustries] = useState<IndustryRead[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    industryApi.list().then(setIndustries).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken || !activeAgency) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const template = await templateApi.create(
        { name: name.trim(), description: description.trim() || null, industry: industry || null },
        activeAgency.id,
        accessToken
      );
      router.push(`/dashboard/templates/${template.id}/edit`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Şablon oluşturulamadı");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-8">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-sm text-text-muted hover:text-text mb-4 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Geri
        </button>
        <h1 className="text-2xl font-bold text-text">Yeni Şablon</h1>
        <p className="text-sm text-text-muted mt-1">
          Brief şablonunuzun temel bilgilerini girin. Bölüm ve alanları sonraki adımda ekleyebilirsiniz.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-surface border border-border rounded-xl p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-text mb-1.5">
            Şablon Adı <span className="text-danger">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={255}
            placeholder="örn. Sosyal Medya Kampanya Brief'i"
            className="w-full px-3 py-2.5 bg-background border border-border rounded-lg text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-1.5">
            Açıklama
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Bu şablonun amacını kısaca açıklayın…"
            className="w-full px-3 py-2.5 bg-background border border-border rounded-lg text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-1.5">
            Sektör
          </label>
          <select
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="w-full px-3 py-2.5 bg-background border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
          >
            <option value="">Sektör seçin (opsiyonel)</option>
            {industries.map((ind) => (
              <option key={ind.code} value={ind.code}>
                {ind.name}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div className="bg-danger/10 border border-danger/20 rounded-lg px-3 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={() => router.back()}
            className="flex-1 px-4 py-2.5 border border-border rounded-lg text-sm font-medium text-text hover:bg-surface-2 transition-colors"
          >
            İptal
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !name.trim()}
            className="flex-1 px-4 py-2.5 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? "Oluşturuluyor…" : "Oluştur ve Düzenle"}
          </button>
        </div>
      </form>
    </div>
  );
}