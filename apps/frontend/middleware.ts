import { NextResponse, type NextRequest } from "next/server";
import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE_NAME,
  LOCALE_HEADER_NAME,
  localeFromAcceptLanguage,
  localeFromCountry,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/config";

function isCrawler(request: NextRequest): boolean {
  return /bot|crawler|spider|crawling/i.test(request.headers.get("user-agent") ?? "");
}

function resolveRequestLocale(request: NextRequest): Locale {
  if (request.nextUrl.pathname === "/tr" || request.nextUrl.pathname.startsWith("/tr/")) return "tr";

  return (
    normalizeLocale(request.cookies.get(LOCALE_COOKIE_NAME)?.value) ??
    localeFromAcceptLanguage(request.headers.get("accept-language")) ??
    localeFromCountry(request.headers.get("cf-ipcountry") ?? request.headers.get("x-vercel-ip-country")) ??
    DEFAULT_LOCALE
  );
}

export function middleware(request: NextRequest) {
  const locale = resolveRequestLocale(request);

  if (request.nextUrl.pathname === "/" && locale === "tr" && !isCrawler(request)) {
    const target = request.nextUrl.clone();
    target.pathname = "/tr";
    return NextResponse.redirect(target, 307);
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(LOCALE_HEADER_NAME, locale);

  if (request.nextUrl.pathname === "/tr" || request.nextUrl.pathname.startsWith("/tr/")) {
    const target = request.nextUrl.clone();
    target.pathname = request.nextUrl.pathname === "/tr" ? "/" : request.nextUrl.pathname.slice(3);
    return NextResponse.rewrite(target, { request: { headers: requestHeaders } });
  }

  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|media|uploads).*)"],
};
