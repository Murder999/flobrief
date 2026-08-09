"""Real Google PageSpeed Insights integration (no fabricated scores).

Returns a distinct 'not_configured' state when PAGESPEED_API_KEY is unset,
so the frontend can render a setup card instead of fake numbers.
"""

from __future__ import annotations

import httpx

from app.core.config import settings

_PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class PageSpeedNotConfiguredError(Exception):
    pass


class PageSpeedApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


def is_pagespeed_configured() -> bool:
    return bool(settings.PAGESPEED_API_KEY)


async def run_pagespeed_check(url: str, strategy: str) -> dict:
    if not is_pagespeed_configured():
        raise PageSpeedNotConfiguredError()
    if strategy not in ("mobile", "desktop"):
        strategy = "mobile"

    params = {
        "url": url,
        "key": settings.PAGESPEED_API_KEY,
        "strategy": strategy,
        "category": ["PERFORMANCE", "ACCESSIBILITY", "BEST_PRACTICES", "SEO"],
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(_PSI_ENDPOINT, params=params)
        except httpx.RequestError as err:
            raise PageSpeedApiError(502, f"PageSpeed API'ye ulaşılamadı: {err}") from err

    if resp.status_code == 429:
        raise PageSpeedApiError(
            429, "PageSpeed API rate limit aşıldı. Lütfen daha sonra tekrar deneyin."
        )
    if resp.status_code != 200:
        detail = (
            resp.json().get("error", {}).get("message", resp.text) if resp.content else resp.text
        )
        raise PageSpeedApiError(resp.status_code, f"PageSpeed API hatası: {detail}")

    data = resp.json()
    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    def _score(cat_key: str) -> int | None:
        cat = categories.get(cat_key)
        if not cat or cat.get("score") is None:
            return None
        return round(cat["score"] * 100)

    def _metric(audit_key: str) -> str | None:
        audit = audits.get(audit_key)
        return audit.get("displayValue") if audit else None

    return {
        "url": url,
        "strategy": strategy,
        "performance_score": _score("performance"),
        "accessibility_score": _score("accessibility"),
        "best_practices_score": _score("best-practices"),
        "seo_score": _score("seo"),
        "lcp": _metric("largest-contentful-paint"),
        "cls": _metric("cumulative-layout-shift"),
        "fcp": _metric("first-contentful-paint"),
        "tbt": _metric("total-blocking-time"),
    }
