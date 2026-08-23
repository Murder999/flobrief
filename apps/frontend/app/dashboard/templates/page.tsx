"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import { templateApi, industryApi, type TemplateRead, type IndustryRead, ApiError } from "@/lib/api-client";

const FIELD_COUNT_PLACEHOLDER = "—";

function TemplateCardSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="h-5 bg-surface-2 rounded w-40" />
        <div className="h-5 bg-surface-2 rounded w-16" />
      </div>
      <div className="h-4 bg-surface-2 rounded w-full mb-2" />
      <div className="h-4 bg-surface-2 rounded w-3/4 mb-4" />
      <div className="flex gap-2">
        <div className="h-6 bg-surface-2 rounded w-20" />
        <div className="h-6 bg-surface-2 rounded w-16" />
      </div>
    </div>
  );
}

function EmptyTemplates({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 bg-accent/10 rounded-2xl flex items-center justify-center mb-4">
        <svg className="w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-text mb-1">Henüz şablon yok</h3>
      <p className="text-sm text-text-muted mb-6 max-w-xs">
        Brief şablonları oluşturarak ekibinizin tutarlı brief&apos;ler göndermesini sağlayın.
      </p>
      <button
        onClick={onNew}
        className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
      >
        İlk şablonu oluştur
      </button>
    </div>
  );
}

function TemplateCard({
  template,
  onDuplicate,
  onArchive,
  onUse,
}: {
  template: TemplateRead;
  onDuplicate: (id: string) => void;
  onArchive: (id: string) => void;
  onUse: (templateId: string) => void;
}) {
  const gradientClasses = useTemplateGradient(template.id);

  return (
    <div
      className="bg-surface border border-border rounded-xl p-5 hover:border-accent/30 hover:shadow-sm transition-all group"
      style={{
          background: gradientClasses.background,
          backgroundImage: `linear-gradient(135deg, ${gradientClasses.stop1}, ${gradientClasses.stop2})`,
          border: gradientClasses.border,
        }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="font-semibold text-text truncate">{template.name}</h3>
          {template.is_system_template && (
            <span className="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 bg-blue-50 text-blue-600 border border-blue-200 rounded-full">
              Sistem
            </span>
          )}
          {!template.is_active && (
            <span className="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded-full">
              Arşiv
            </span>
          )}
        </div>
      </div>

      {template.description && (
        <p className="text-sm text-text-muted line-clamp-2 mb-3">{template.description}</p>
      )}

      <div className="flex items-center gap-2 flex-wrap mb-4">
        {template.industry && (
          <span className="text-xs px-2 py-0.5 rounded-full">
            {template.industry}
          </span>
        )}
        <span className="text-xs text-text-muted">
          {new Date(template.created_at).toLocaleDateString("tr-TR")}
        </span>
      </div>

      <div className="flex items-center gap-2 pt-3 border-t border-border opacity-0 group-hover:opacity-100 transition-opacity">
        {!template.is_system_template && (
          <Link
            href={`/dashboard/templates/${template.id}/edit`}
            className="flex-1 text-sm font-medium px-3 py-1.5 bg-surface-2 text-text hover:bg-accent hover:text-white rounded-lg transition-colors"
            title="Şablonu Düzenle"
          >
            Düzenle
          </Link>
        )}
        <button
          onClick={() => onDuplicate(template.id)}
          className="flex-1 text-xs font-medium px-3 py-1.5 bg-surface-2 text-text hover:bg-surface-3 rounded-lg transition-colors"
          title="Şablonu Kopyala"
        >
          Kopyala
        </button>
        {!template.is_system_template && template.is_active && (
          <button
            onClick={() => onArchive(template.id)}
            className="text-xs font-medium px-3 py-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
            title="Şablonu Arşivle"
          >
            Arşivle
          </button>
        )}
        <button
          onClick={() => onUse(template.id)}
          className="flex-1 text-xs font-medium px-3 py-1.5 bg-accent/10 text-accent rounded-lg transition-colors"
          title="Şablonu Kullan"
        >
          Kullan
        </button>
      </div>
    </div>
  );
}

function useTemplateGradient(templateId: string) {
  const hash = templateId.split("-").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const hues = [200, 250, 180, 140];
  const hue = hues[hash % hues.length];
  const isDark = hue > 220;
  const bg = isDark ? "rgba(0,0,0,0.03)" : "rgba(255,255,255,0.03)";
  const color = isDark ? `hsl(${hue}, 30%, 90%)` : `hsl(${hue}, 30%, 20%)`;
  const stop1 = isDark ? `hsl(${hue}, 30%, 70%)` : `hsl(${hue}, 30%, 80%)`;
  const stop2 = isDark ? `hsl(${hue}, 30%, 50%)` : `hsl(${hue}, 30%, 60%)`;
  return { background: bg, border: color, text: color, stop1, stop2, hue };
}

export default function TemplatesPage() {
  const { accessToken } = useAuth();
  const { activeAgency, isLoading: workspaceLoading, isInitialized: workspaceReady } = useWorkspace();

  const [templates, setTemplates] = useState<TemplateRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState<string | undefined>(undefined);

  const load = useCallback(async () => {
    if (!accessToken || !activeAgency) return;
    setIsLoading(true);
    setError(null);
    try {
      const industryFilter = selectedIndustry ? `industry=${selectedIndustry}` : undefined;
      const searchFilter = searchQuery ? `&search=${searchQuery}` : undefined;
      const url = `/api/v1/templates${industryFilter ? `?industry=${industryFilter}` : ""}${searchQuery ? (industryFilter ? "&" : "?") + `search=${searchQuery}` : ""}`;
      const data = await templateApi.list(activeAgency.id, accessToken, selectedIndustry);
      let filtered = data;

      if (searchQuery) {
        filtered = data.filter((t) =>
          t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (t.description?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false)
        );
      }

      setTemplates(filtered);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Şablonlar yüklenemedi");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, activeAgency, searchQuery, selectedIndustry]);

  useEffect(() => {
    if (workspaceReady && !workspaceLoading && !activeAgency) {
      setIsLoading(false);
    }
  }, [workspaceReady, workspaceLoading, activeAgency]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDuplicate = async (id: string) => {
    if (!accessToken || !activeAgency) return;
    setActionLoading(id);
    try {
      await templateApi.duplicate(id, activeAgency.id, accessToken);
      await load();
    } catch {
      /* ignore */
    } finally {
      setActionLoading(null);
    }
  };

  const handleArchive = async (id: string) => {
    if (!accessToken || !activeAgency) return;
    setActionLoading(id);
    try {
      await templateApi.archive(id, activeAgency.id, accessToken);
      await load();
    } catch {
      /* ignore */
    } finally {
      setActionLoading(null);
    }
  };

  const handleUse = async (templateId: string) => {
    if (!accessToken || !activeAgency) return;
    setActionLoading(templateId);
    try {
      // Navigate to new brief with template selected, or just mark it
      // For now, we'll just set the state and let the caller handle navigation
      setActionLoading(null);
      // Could trigger navigation or state management here
    } catch {
      setActionLoading(null);
    }
  };

  // Load industries for filter
  const [industries, setIndustries] = useState<IndustryRead[]>([]);
  useEffect(() => {
    industryApi.list().then(setIndustries).catch(() => {});
  }, []);

  const systemTemplates = templates.filter((t) => t.is_system_template);
  const agencyTemplates = templates.filter((t) => !t.is_system_template);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text">Brief Şablonları</h1>
          <p className="text-sm text-text-muted mt-1">
            Brief formlarınızı şablonlarla standartlaştırın
          </p>
        </div>
        <Link
          href="/dashboard/templates/new"
          className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Yeni Şablon
        </Link>
      </div>

      {/* Search and Filters Bar */}
      <div className="mb-6 bg-surface border border-border rounded-xl p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Search */}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Şabloon Ara</label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Şabloon adı veya açıklama..."
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            />
          </div>

          {/* Industry Filter */}
          <div>
            <label className="block text-xs font-medium text-text-muted mb-1.5">Kategori</label>
            <select
              value={selectedIndustry || ""}
              onChange={(e) => setSelectedIndustry(e.target.value || "")}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            >
              <option value="">Tüm kategoriler</option>
              {industries.map((ind) => (
                <option key={ind.code} value={ind.code}>
                  {ind.name}
                </option>
              ))}
            </select>
          </div>

          {/* CTA */}
          <div />
        </div>
      </div>

      {!isLoading && !activeAgency ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 bg-accent/10 rounded-2xl flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-accent/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-text mb-1">Ajans seçilmedi</h3>
          <p className="text-sm text-text-muted mb-6 max-w-xs">Şablonları görüntülemek için bir ajans seçin veya oluşturun.</p>
          <a href="/onboarding/create-agency" className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors">
            Ajans Oluştur
          </a>
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <TemplateCardSkeleton key={i} />)}
        </div>
      ) : error ? (
        <div className="bg-danger/10 border border-danger/20 rounded-xl p-4 text-sm text-danger">
          {error}
          <button onClick={load} className="ml-2 underline">Tekrar dene</button>
        </div>
      ) : templates.length === 0 ? (
        <EmptyTemplates onNew={() => window.location.assign("/dashboard/templates/new")} />
      ) : (
        <div className="space-y-8">
          {agencyTemplates.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wider mb-4">
                Ajans Şablonları
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agencyTemplates.map((t) => (
                  <TemplateCard
                    key={t.id}
                    template={t}
                    onDuplicate={handleDuplicate}
                    onArchive={handleArchive}
                    onUse={handleUse}
                  />
                ))}
              </div>
            </section>
          )}

          {systemTemplates.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wider mb-4">
                Sistem Şablonları
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {systemTemplates.map((t) => (
                  <TemplateCard
                    key={t.id}
                    template={t}
                    onDuplicate={handleDuplicate}
                    onArchive={handleArchive}
                    onUse={handleUse}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {actionLoading && (
        <div className="fixed bottom-4 right-4 bg-surface border border-border rounded-lg px-4 py-2 text-sm text-text shadow-lg">
          İşleniyor…
        </div>
      )}
    </div>
  );
}