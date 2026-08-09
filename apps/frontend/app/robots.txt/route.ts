import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8003";

const FALLBACK_ROBOTS = `User-agent: *
Allow: /
Disallow: /platform/
Disallow: /dashboard/
Disallow: /brand/
Disallow: /approve/
Disallow: /report/
Disallow: /api/

Sitemap: https://flobrief.com/sitemap.xml`;

export async function GET() {
  let body = FALLBACK_ROBOTS;

  try {
    const res = await fetch(`${API_BASE}/api/v1/public/seo/robots`, {
      next: { revalidate: 300 },
    });
    if (res.ok) {
      const data = await res.json();
      if (data.robots_txt) body = data.robots_txt;
    }
  } catch {
    // Backend unreachable — serve the safe fallback rather than a broken response.
  }

  return new NextResponse(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
