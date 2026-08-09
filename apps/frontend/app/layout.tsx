import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/context/auth-context";
import { WorkspaceProvider } from "@/context/workspace-context";
import { ToastProvider } from "@/components/ui/toast";
import "../styles/globals.css";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Lets env(safe-area-inset-*) resolve to real values on notched/rounded-
  // corner devices instead of always reading 0 — required by the mobile
  // shell's SafeAreaContainer.
  viewportFit: "cover",
};

const FALLBACK_METADATA: Metadata = {
  title: {
    default: "Flobrief — Agency Brief Management",
    template: "%s | Flobrief",
  },
  description:
    "Premium brief management, approval workflows, and content calendar for agencies and brands.",
  keywords: ["brief management", "agency software", "content approval", "B2B SaaS"],
};

interface PublicPageSeo {
  title: string | null;
  description: string | null;
  canonical_url: string | null;
  og_title: string | null;
  og_description: string | null;
  og_image_url: string | null;
  indexable: boolean;
  follow_links: boolean;
}

export async function generateMetadata(): Promise<Metadata> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/public/seo/pages/home`, {
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(1500),
    });
    if (!res.ok) return FALLBACK_METADATA;
    const seo: PublicPageSeo = await res.json();

    return {
      ...FALLBACK_METADATA,
      title: seo.title
        ? { default: seo.title, template: `%s | ${seo.title}` }
        : FALLBACK_METADATA.title,
      description: seo.description ?? FALLBACK_METADATA.description,
      alternates: seo.canonical_url ? { canonical: seo.canonical_url } : undefined,
      robots: {
        index: seo.indexable,
        follow: seo.follow_links,
      },
      openGraph: {
        title: seo.og_title ?? seo.title ?? undefined,
        description: seo.og_description ?? seo.description ?? undefined,
        images: seo.og_image_url ? [seo.og_image_url] : undefined,
      },
    };
  } catch {
    // Backend unreachable at build/request time — fall back to static metadata
    // rather than rendering a page with no <title>/<meta description>.
    return FALLBACK_METADATA;
  }
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var s=localStorage.getItem('flobrief-theme');var t=s==='dark'?'dark':s==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.setAttribute('data-theme',t);})();`,
          }}
        />
      </head>
      <body className="bg-background text-text antialiased">
        <AuthProvider>
          <WorkspaceProvider>
            <ToastProvider>{children}</ToastProvider>
          </WorkspaceProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
