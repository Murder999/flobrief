import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://postpiloter.com";

const FALLBACK_ROBOTS = `User-agent: *
Allow: /
Disallow: /platform/
Disallow: /dashboard/
Disallow: /brand/
Disallow: /approve/
Disallow: /report/
Disallow: /api/

Sitemap: https://postpiloter.com/sitemap.xml`;

const PLATFORM_DISALLOW = "Disallow: /platform/";

function enforcePrivateRoutes(body: string): string {
  if (body.includes(PLATFORM_DISALLOW)) return body;
  return `${body.trim()}\n\nUser-agent: *\n${PLATFORM_DISALLOW}`;
}

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

  return new NextResponse(enforcePrivateRoutes(body), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
