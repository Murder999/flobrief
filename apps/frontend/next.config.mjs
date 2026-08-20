/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allows a clean verification build without stopping a running standalone
  // preview that legitimately holds the default .next directory open.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Standalone tracing is required only for the self-hosted Docker image.
  // Ordinary local builds mirror Vercel's native build mode.
  output: process.env.DOCKER_BUILD === "true" ? "standalone" : undefined,
  images: {
    remotePatterns: [],
  },
  async headers() {
    return [
      {
        source: "/platform/:path*",
        headers: [
          {
            key: "X-Robots-Tag",
            value: "noindex, nofollow, noarchive, nosnippet, noimageindex",
          },
          { key: "Cache-Control", value: "private, no-store, max-age=0" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
  async rewrites() {
    if (process.env.NEXT_PUBLIC_API_URL) return [];

    // Same-origin rewrite target — defaults to the standard dev backend
    // port; overridable for a controlled, isolated E2E backend instance
    // (e.g. `E2E_REWRITE_API_PORT=8010`) so Playwright never needs
    // NEXT_PUBLIC_API_URL (which disables this rewrite entirely and
    // reintroduces the cross-origin CORS/cookie issues this rewrite exists
    // to avoid).
    const apiPort = process.env.E2E_REWRITE_API_PORT || "8000";

    return [
      {
        source: "/api/v1/:path*",
        destination: `http://127.0.0.1:${apiPort}/api/v1/:path*`,
      },
      {
        source: "/media/:path*",
        destination: `http://127.0.0.1:${apiPort}/media/:path*`,
      },
    ];
  },
  async redirects() {
    return [
      { source: "/login", destination: "/auth/login", permanent: true },
      { source: "/register", destination: "/auth/register", permanent: true },
      { source: "/forgot-password", destination: "/auth/forgot-password", permanent: true },
      { source: "/reset-password", destination: "/auth/reset-password", permanent: true },
      { source: "/verify-email", destination: "/auth/verify-email", permanent: true },
      { source: "/dashboard/team", destination: "/dashboard/settings/members", permanent: true },
      { source: "/dashboard/billing", destination: "/dashboard/settings/billing", permanent: true },
      { source: "/dashboard/branding", destination: "/dashboard/settings/branding", permanent: true },
      { source: "/reports/share/:token", destination: "/report/:token", permanent: true },
    ];
  },
};

export default nextConfig;
