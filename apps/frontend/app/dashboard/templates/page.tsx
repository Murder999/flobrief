"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useWorkspace } from "@/context/workspace-context";
import {
  templateApi,
  industryApi,
  type TemplateRead,
  type IndustryRead,
  ApiError,
} from "@/lib/api-client";

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
        <svg
          className="w-8 h-8 text-accent"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      </div>

      <h3 className="text-lg font-semibold text-text mb-1">
        Henüz şablon yok
      </h3>

      <p className="text-sm text-text-muted mb-6 max-w-xs">
        Brief şablonları oluşturarak ekibinizin tutarlı brief&apos;ler
        göndermesini sağlayın.
      </p>

      <button
        type="button"
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
  return (
    <div className="bg-surface border border-border rounded-xl p-5 hover:border-accent/30 hover:shadow-sm transition-all group">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="font-semibold text-text truncate">
            {template.name}
          </h3>

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
        <p className="text-sm text-text-muted line-clamp-2 mb-3">
          {template.description}
        </p>
      )}

      <div className="flex items-center gap-2 flex-wrap mb-4">
        {template.industry && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-surface-2 text-text-muted border border-border">
            {template.industry}
          </span>
        )}

        <span className="text-xs text-text-muted">
          {new Date(template.created_at).toLocaleDateString("tr-TR")}
        </span>
      </div>

      <div className="flex items-center gap-2 pt-3 border-t border-border opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity">
        {!template.is_system_template && (
          <Link
            href={`/dashboard/templates/${template.id}/edit`}
            className="flex-1 text-center text-sm font-medium px-3 py-1.5 bg-surface-2 text-text hover:bg-accent hover:text-white rounded-lg transition-colors"
            title="Şablonu Düzenle"
          >
            Düzenle
          </Link>
        )}

        <button
          type="button"
          onClick={() => onDuplicate(template.id)}
          className="flex-1 text-xs font-medium px-3 py-1.5 bg-surface-2 text-text hover:bg-surface-3 rounded-lg transition-colors"
          title="Şablonu Kopyala"
        >
          Kopyala
        </button>

        {!template.is_system_template && template.is_active && (
          <button
            type="button"
            onClick={() => onArchive(template.id)}
            className="text-xs font-medium px-3 py-1.5 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
            title="Şablonu Arşivle"
          >
            Arşivle
          </button>
        )}

        <button
          type="button"
          onClick={() => onUse(template.id)}
          className="flex-1 text-xs font-medium px-3 py-1.5 bg-accent/10 text-accent hover:bg-accent hover:text-white rounded-lg transition-colors"
          title="Şablonu Kullan"
        >
          Kullan
        </button>
      </div>
    </div>
  );
}

export default function TemplatesPage() {
  const router = useRouter();

  const { accessToken } = useAuth();
  const {
    activeAgency,
    isLoading: workspaceLoading,
    isInitialized: workspaceReady,
  } = useWorkspace();

  const [templates, setTemplates] = useState<TemplateRead[]>([]);
  const [industries, setIndustries] = useState<IndustryRead[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState<
    string | undefined
  >(undefined);

  const load = useCallback(async () => {
    if (!accessToken || !activeAgency) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await templateApi.list(
        activeAgency.id,
        accessToken,
        selectedIndustry
      );

      let filtered = data;

      if (searchQuery.trim()) {
        const normalizedQuery = searchQuery.trim().toLocaleLowerCase("tr-TR");

        filtered = data.filter((template) => {
          const name = template.name.toLocaleLowerCase("tr-TR");
          const description =
            template.description?.toLocaleLowerCase("tr-TR") ?? "";

          return (
            name.includes(normalizedQuery) ||
            description.includes(normalizedQuery)
          );
        });
      }

      setTemplates(filtered);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Şablonlar yüklenemedi"
      );
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

  useEffect(() => {
    industryApi
      .list()
      .then(setIndustries)
      .catch(() => {
        setIndustries([]);
      });
  }, []);

  const handleDuplicate = async (id: string) => {
    if (!accessToken || !activeAgency) return;

    setActionLoading(id);

    try {
      await templateApi.duplicate(id, activeAgency.id, accessToken);
      await load();
    } catch {
      // Existing template state is preserved on failure.
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
      // Existing template state is preserved on failure.
    } finally {
      setActionLoading(null);
    }
  };

  const handleUse = (templateId: string) => {
    if (!accessToken || !activeAgency) return;

    router.push(
      `/dashboard/briefs/new?templateId=${encodeURIComponent(templateId)}`
    );
  };

  const systemTemplates = templates.filter(
    (template) => template.is_system_template
  );

  const agencyTemplates = templates.filter(
    (template) => !template.is_system_template
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text">
            Brief Şablonları
          </h1>

          <p className="text-sm text-text-muted mt-1">
            Brief formlarınızı şablonlarla standartlaştırın
          </p>
        </div>

        <Link
          href="/dashboard/templates/new"
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>

          Yeni Şablon
        </Link>
      </div>

      {/* Search and Filters Bar */}
      <div className="mb-6 bg-surface border border-border rounded-xl p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="template-search"
              className="block text-xs font-medium text-text-muted mb-1.5"
            >
              Şablon Ara
            </label>

            <input
              id="template-search"
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Şablon adı veya açıklama..."
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            />
          </div>

          <div>
            <label
              htmlFor="template-category"
              className="block text-xs font-medium text-text-muted mb-1.5"
            >
              Kategori
            </label>

            <select
              id="template-category"
              value={selectedIndustry ?? ""}
              onChange={(event) =>
                setSelectedIndustry(event.target.value || undefined)
              }
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
            >
              <option value="">Tüm kategoriler</option>

              {industries.map((industry) => (
                <option key={industry.code} value={industry.code}>
                  {industry.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {!isLoading && !activeAgency ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 bg-accent/10 rounded-2xl flex items-center justify-center mb-4">
            <svg
              className="w-8 h-8 text-accent/40"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>

          <h3 className="text-lg font-semibold text-text mb-1">
            Ajans seçilmedi
          </h3>

          <p className="text-sm text-text-muted mb-6 max-w-xs">
            Şablonları görüntülemek için bir ajans seçin veya oluşturun.
          </p>

          <Link
            href="/onboarding/create-agency"
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            Ajans Oluştur
          </Link>
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, index) => (
            <TemplateCardSkeleton key={index} />
          ))}
        </div>
      ) : error ? (
        <div
          role="alert"
          className="bg-danger/10 border border-danger/20 rounded-xl p-4 text-sm text-danger"
        >
          {error}

          <button
            type="button"
            onClick={() => void load()}
            className="ml-2 underline"
          >
            Tekrar dene
          </button>
        </div>
      ) : templates.length === 0 ? (
        <EmptyTemplates
          onNew={() => router.push("/dashboard/templates/new")}
        />
      ) : (
        <div className="space-y-8">
          {agencyTemplates.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-text-muted uppercase tracking-wider mb-4">
                Ajans Şablonları
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agencyTemplates.map((template) => (
                  <TemplateCard
                    key={template.id}
                    template={template}
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
                {systemTemplates.map((template) => (
                  <TemplateCard
                    key={template.id}
                    template={template}
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
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-4 right-4 bg-surface border border-border rounded-lg px-4 py-2 text-sm text-text shadow-lg"
        >
          İşleniyor…
        </div>
      )}
    </div>
  );
}