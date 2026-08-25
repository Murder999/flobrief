"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BarChart3,
  Bell,
  BookOpen,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FilePlus2,
  Layers3,
  MessageSquareMore,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { useLocale } from "@/context/locale-context";
import { cn } from "@/lib/utils";
import {
  HELP_CONFIG,
  helpArticleKey,
  helpCategoryKey,
  helpCommonKey,
  helpFaqKey,
  helpQuickActionKey,
  type HelpArticleMeta,
  type HelpPortal,
} from "./help-center-data";

const QUICK_ACTION_ICONS = {
  brief: FilePlus2,
  approval: CheckCircle2,
  revision: MessageSquareMore,
  notifications: Bell,
  brand: Building2,
  template: Layers3,
  report: BarChart3,
} as const;

const CATEGORY_ICONS = [BookOpen, FilePlus2, CheckCircle2, Layers3, Sparkles, Bell, BarChart3, SlidersHorizontal];

function splitList(value: string): string[] {
  return value.split("|").map((item) => item.trim()).filter(Boolean);
}

function normalizeSearch(value: string): string {
  return value
    .toLocaleLowerCase("tr-TR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ı/g, "i");
}

export function HelpCenter({ portal }: { portal: HelpPortal }) {
  const { locale, t } = useLocale();
  const router = useRouter();
  const config = HELP_CONFIG[portal];
  const allArticles = config.categories.flatMap((category) =>
    category.articles.map((article) => ({ article, category }))
  );
  const [selectedTopic, setSelectedTopic] = useState(config.defaultTopic);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  useEffect(() => {
    const validTopics = new Set(config.categories.flatMap((category) => category.articles.map((article) => article.id)));
    const topic = new URLSearchParams(window.location.search).get("topic");
    if (topic && validTopics.has(topic)) setSelectedTopic(topic);
  }, [config]);

  useEffect(() => {
    document.title = `${t(helpCommonKey("title"))} | PostPiloter`;
  }, [locale, t]);

  const selectedEntry = allArticles.find(({ article }) => article.id === selectedTopic) ?? allArticles[0];
  const activeCategory = selectedEntry.category;
  const selectedArticle = selectedEntry.article;
  const articleTitle = t(helpArticleKey(portal, selectedArticle.id, "title"));

  const searchResults = deferredQuery.trim()
    ? allArticles.filter(({ article, category }) => {
        const searchable = [
          t(helpArticleKey(portal, article.id, "title")),
          t(helpArticleKey(portal, article.id, "summary")),
          t(helpArticleKey(portal, article.id, "purpose")),
          t(helpArticleKey(portal, article.id, "steps")),
          t(helpArticleKey(portal, article.id, "notes")),
          t(helpArticleKey(portal, article.id, "keywords")),
          t(helpFaqKey(portal, category.id, "question")),
          t(helpFaqKey(portal, category.id, "answer")),
        ].join(" ");
        return normalizeSearch(searchable).includes(normalizeSearch(deferredQuery.trim()));
      })
    : [];

  function selectTopic(article: HelpArticleMeta) {
    startTransition(() => {
      setSelectedTopic(article.id);
      setQuery("");
      router.replace(`${config.basePath}?topic=${encodeURIComponent(article.id)}`, { scroll: false });
    });
  }

  function selectCategory(categoryId: string) {
    const category = config.categories.find((item) => item.id === categoryId);
    if (category?.articles[0]) selectTopic(category.articles[0]);
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 sm:py-7 lg:px-8" data-testid={`${portal}-help-center`}>
      <header className="max-w-3xl">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent-subtle px-3 py-1 text-xs font-semibold text-accent">
          <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
          {t(helpCommonKey(portal === "agency" ? "agencyPortal" : "brandPortal"))}
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-text sm:text-3xl">{t(helpCommonKey("title"))}</h1>
        <p className="mt-2 text-sm leading-6 text-text-muted sm:text-base">{t(helpCommonKey("subtitle"))}</p>
      </header>

      <section className="mt-6" aria-label={t(helpCommonKey("searchLabel"))}>
        <label htmlFor={`${portal}-help-search`} className="sr-only">{t(helpCommonKey("searchLabel"))}</label>
        <div className="relative max-w-3xl">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-muted" aria-hidden="true" />
          <input
            id={`${portal}-help-search`}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t(helpCommonKey("searchPlaceholder"))}
            className="h-12 w-full rounded-2xl border border-border bg-surface pl-12 pr-12 text-sm text-text shadow-sm outline-none transition focus:border-accent/50 focus:ring-4 focus:ring-accent/10"
          />
          {query ? (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label={t(helpCommonKey("clearSearch"))}
              className="absolute right-2 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-xl text-text-muted hover:bg-hover hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : null}
        </div>

        <div aria-live="polite" aria-atomic="true" className="sr-only">
          {deferredQuery.trim()
            ? searchResults.length
              ? t(helpCommonKey("resultCount"), { count: searchResults.length })
              : t(helpCommonKey("noResultsTitle"))
            : ""}
        </div>

        {deferredQuery.trim() ? (
          <div className="mt-3 max-w-3xl overflow-hidden rounded-2xl border border-border bg-surface shadow-card" data-testid="help-search-results">
            {searchResults.length ? (
              <ul className="divide-y divide-border">
                {searchResults.map(({ article, category }) => (
                  <li key={article.id}>
                    <button
                      type="button"
                      onClick={() => selectTopic(article)}
                      className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/30"
                    >
                      <Search className="h-4 w-4 flex-none text-text-muted group-hover:text-accent" aria-hidden="true" />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-text">{t(helpArticleKey(portal, article.id, "title"))}</span>
                        <span className="mt-0.5 block truncate text-xs text-text-muted">{t(helpCategoryKey(portal, category.id))}</span>
                      </span>
                      <ChevronRight className="h-4 w-4 flex-none text-text-muted" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="px-6 py-8 text-center" data-testid="help-empty-state">
                <Search className="mx-auto h-7 w-7 text-text-muted" aria-hidden="true" />
                <h2 className="mt-3 text-sm font-semibold text-text">{t(helpCommonKey("noResultsTitle"))}</h2>
                <p className="mt-1 text-sm text-text-muted">{t(helpCommonKey("noResultsDescription"))}</p>
              </div>
            )}
          </div>
        ) : null}
      </section>

      <section className="mt-7" aria-labelledby={`${portal}-quick-actions`}>
        <div className="mb-3 flex items-center gap-3">
          <h2 id={`${portal}-quick-actions`} className="text-sm font-semibold text-text">{t(helpCommonKey("quickActions"))}</h2>
          <div className="h-px flex-1 bg-border" />
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="help-quick-actions">
          {config.quickActions.map((action) => {
            const Icon = QUICK_ACTION_ICONS[action.icon];
            return (
              <Link
                key={action.id}
                href={action.href}
                className="group min-w-0 rounded-2xl border border-border bg-surface p-4 transition-all hover:-translate-y-0.5 hover:border-border-hover hover:shadow-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-subtle text-accent">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <ArrowRight className="h-4 w-4 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden="true" />
                </div>
                <span className="mt-3 block text-sm font-semibold text-text">{t(helpQuickActionKey(portal, action.id, "title"))}</span>
                <span className="mt-1 hidden text-xs leading-5 text-text-muted sm:block">{t(helpQuickActionKey(portal, action.id, "description"))}</span>
              </Link>
            );
          })}
        </div>
      </section>

      <div className="mt-8 border-t border-border pt-6 lg:grid lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-10">
        <aside aria-label={t(helpCommonKey("categories"))}>
          <div className="lg:hidden">
            <label htmlFor={`${portal}-help-category`} className="mb-2 block text-xs font-semibold uppercase tracking-wider text-text-muted">
              {t(helpCommonKey("categories"))}
            </label>
            <div className="relative">
              <select
                id={`${portal}-help-category`}
                value={activeCategory.id}
                onChange={(event) => selectCategory(event.target.value)}
                className="h-11 w-full appearance-none rounded-xl border border-border bg-surface px-4 pr-10 text-sm font-medium text-text outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/20"
              >
                {config.categories.map((category) => (
                  <option key={category.id} value={category.id}>{t(helpCategoryKey(portal, category.id))}</option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" aria-hidden="true" />
            </div>
          </div>

          <nav className="hidden lg:block" data-testid="help-categories">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">{t(helpCommonKey("categories"))}</p>
            <div className="space-y-1">
              {config.categories.map((category, index) => {
                const Icon = CATEGORY_ICONS[index % CATEGORY_ICONS.length];
                const active = category.id === activeCategory.id;
                return (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() => selectCategory(category.id)}
                    className={cn(
                      "flex min-h-10 w-full items-center gap-2.5 rounded-xl px-3 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30",
                      active ? "bg-accent-subtle text-accent" : "text-text-secondary hover:bg-hover hover:text-text"
                    )}
                    aria-current={active ? "true" : undefined}
                  >
                    <Icon className="h-4 w-4 flex-none" aria-hidden="true" />
                    <span>{t(helpCategoryKey(portal, category.id))}</span>
                  </button>
                );
              })}
            </div>
          </nav>

          <div className="mt-4 border-t border-border pt-4" data-testid="help-topics">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">{t(helpCommonKey("inThisCategory"))}</p>
            <div className="flex gap-2 overflow-x-auto pb-2 lg:block lg:space-y-1 lg:overflow-visible lg:pb-0">
              {activeCategory.articles.map((article) => {
                const active = article.id === selectedArticle.id;
                return (
                  <button
                    key={article.id}
                    type="button"
                    onClick={() => selectTopic(article)}
                    className={cn(
                      "min-h-10 flex-none rounded-xl border px-3 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 lg:w-full",
                      active
                        ? "border-accent/30 bg-accent-subtle font-medium text-accent"
                        : "border-border bg-surface text-text-secondary hover:border-border-hover hover:text-text"
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    {t(helpArticleKey(portal, article.id, "title"))}
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        <article className="mt-6 min-w-0 lg:mt-0" data-testid="help-article">
          <div className="border-b border-border pb-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">{t(helpCategoryKey(portal, activeCategory.id))}</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-text" tabIndex={-1}>{articleTitle}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{t(helpArticleKey(portal, selectedArticle.id, "summary"))}</p>
          </div>

          <div className="max-w-3xl divide-y divide-border">
            <section className="py-6">
              <h3 className="text-base font-semibold text-text">{t(helpCommonKey("purposeTitle"))}</h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{t(helpArticleKey(portal, selectedArticle.id, "purpose"))}</p>
            </section>

            <section className="py-6">
              <h3 className="text-base font-semibold text-text">{t(helpCommonKey("howToTitle"))}</h3>
              <ol className="mt-4 space-y-3">
                {splitList(t(helpArticleKey(portal, selectedArticle.id, "steps"))).map((step, index) => (
                  <li key={step} className="flex gap-3 text-sm leading-6 text-text-secondary">
                    <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-accent-subtle text-xs font-semibold text-accent">{index + 1}</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </section>

            <section className="py-6">
              <h3 className="text-base font-semibold text-text">{t(helpCommonKey("notesTitle"))}</h3>
              <ul className="mt-3 space-y-2">
                {splitList(t(helpArticleKey(portal, selectedArticle.id, "notes"))).map((note) => (
                  <li key={note} className="flex gap-2.5 text-sm leading-6 text-text-secondary">
                    <CheckCircle2 className="mt-1 h-4 w-4 flex-none text-success" aria-hidden="true" />
                    <span>{note}</span>
                  </li>
                ))}
              </ul>
              {selectedArticle.href ? (
                <Link
                  href={selectedArticle.href}
                  className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-accent px-4 text-sm font-semibold text-white transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2"
                >
                  {t(helpCommonKey("relatedPage"))}
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Link>
              ) : null}
            </section>

            <section className="py-6">
              <h3 className="text-base font-semibold text-text">{t(helpCommonKey("faqTitle"))}</h3>
              <details className="group mt-3 rounded-xl border border-border bg-surface open:border-border-hover">
                <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-sm font-medium text-text outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/30 [&::-webkit-details-marker]:hidden">
                  {t(helpFaqKey(portal, activeCategory.id, "question"))}
                  <ChevronRight className="h-4 w-4 flex-none text-text-muted transition-transform group-open:rotate-90" aria-hidden="true" />
                </summary>
                <p className="border-t border-border px-4 py-3 text-sm leading-6 text-text-muted">{t(helpFaqKey(portal, activeCategory.id, "answer"))}</p>
              </details>
            </section>
          </div>
        </article>
      </div>
    </main>
  );
}
