import type { MetadataRoute } from "next";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8003";
const DEFAULT_PUBLIC_URL = "https://flobrief.com";

interface PublicSitemapPage {
  path: string;
  updated_at: string | null;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  let publicUrl = DEFAULT_PUBLIC_URL;
  let pages: PublicSitemapPage[] = [{ path: "/", updated_at: null }];

  try {
    const [robotsRes, pagesRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/public/seo/robots`, { next: { revalidate: 300 } }),
      fetch(`${API_BASE}/api/v1/public/seo/sitemap-pages`, { next: { revalidate: 300 } }),
    ]);
    if (robotsRes.ok) {
      const data = await robotsRes.json();
      if (data.public_app_url) publicUrl = data.public_app_url.replace(/\/$/, "");
    }
    if (pagesRes.ok) {
      const data: PublicSitemapPage[] = await pagesRes.json();
      if (data.length > 0) pages = data;
    }
  } catch {
    // Backend unreachable at build time — fall back to the home page only,
    // never a fabricated/expanded page list.
  }

  return pages.map((page) => ({
    url: `${publicUrl}${page.path === "/" ? "" : page.path}`,
    lastModified: page.updated_at ? new Date(page.updated_at) : new Date(),
    changeFrequency: page.path === "/" ? "weekly" : "monthly",
    priority: page.path === "/" ? 1.0 : 0.7,
  }));
}
