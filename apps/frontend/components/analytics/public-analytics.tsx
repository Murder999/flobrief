"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import Script from "next/script";

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

const PUBLIC_TRACKING_PATHS = new Set(["/", "/pricing", "/contact", "/demo"]);

export function PublicAnalytics() {
  const pathname = usePathname();
  const shouldTrack = PUBLIC_TRACKING_PATHS.has(pathname);
  const initialPath = useRef(pathname);
  const [tracking, setTracking] = useState<{ gaId: string | null; gtmId: string | null }>({
    gaId: null,
    gtmId: null,
  });

  useEffect(() => {
    if (!shouldTrack) return;
    const pageKey = `${pathname}${window.location.search}:${performance.timeOrigin}`;
    const sentKey = `postpiloter_analytics_sent:${pageKey}`;
    if (sessionStorage.getItem(sentKey)) return;

    const sessionKey = "postpiloter_analytics_session";
    let sessionId = sessionStorage.getItem(sessionKey);
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem(sessionKey, sessionId);
    }

    let referrerHost: string | null = null;
    if (document.referrer) {
      try {
        const host = new URL(document.referrer).hostname.toLowerCase();
        referrerHost = host && host !== window.location.hostname.toLowerCase() ? host : null;
      } catch {
        referrerHost = null;
      }
    }
    const query = new URLSearchParams(window.location.search);
    sessionStorage.setItem(sentKey, "1");
    void fetch("/api/v1/public/seo/analytics/events", {
      method: "POST",
      credentials: "omit",
      keepalive: true,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        path: pathname,
        referrer_host: referrerHost,
        utm_source: query.get("utm_source"),
        utm_medium: query.get("utm_medium"),
      }),
    })
      .then((response) => {
        if (!response.ok) sessionStorage.removeItem(sentKey);
      })
      .catch(() => sessionStorage.removeItem(sentKey));
  }, [pathname, shouldTrack]);

  useEffect(() => {
    if (!shouldTrack || tracking.gaId || tracking.gtmId) return;
    let cancelled = false;
    void fetch("/api/v1/public/seo/robots", { credentials: "omit" })
      .then((response) => response.ok ? response.json() : null)
      .then((data: { google_analytics_id?: string | null; google_tag_manager_id?: string | null } | null) => {
        if (cancelled || !data) return;
        const gaId = /^G-[A-Z0-9]+$/i.test(data.google_analytics_id ?? "")
          ? data.google_analytics_id ?? null
          : null;
        const gtmId = /^GTM-[A-Z0-9]+$/i.test(data.google_tag_manager_id ?? "")
          ? data.google_tag_manager_id ?? null
          : null;
        setTracking({ gaId, gtmId });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [shouldTrack, tracking.gaId, tracking.gtmId]);

  useEffect(() => {
    if (
      pathname === initialPath.current ||
      !shouldTrack ||
      !tracking.gaId ||
      !window.gtag
    ) return;
    window.gtag("event", "page_view", {
      page_path: pathname,
      page_location: window.location.href,
      page_title: document.title,
    });
  }, [pathname, shouldTrack, tracking.gaId]);

  if (!shouldTrack) return null;

  return (
    <>
      {tracking.gaId && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(tracking.gaId)}`}
            strategy="afterInteractive"
          />
          <Script id="postpiloter-ga4" strategy="afterInteractive">
            {`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}window.gtag=gtag;gtag('js',new Date());gtag('config',${JSON.stringify(tracking.gaId)},{anonymize_ip:true});`}
          </Script>
        </>
      )}
      {tracking.gtmId && (
        <Script id="postpiloter-gtm" strategy="afterInteractive">
          {`(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer',${JSON.stringify(tracking.gtmId)});`}
        </Script>
      )}
    </>
  );
}
