"""Registry of Flobrief's actual public (indexable-eligible) frontend routes.

Kept in sync manually with apps/frontend/app/*. Only routes that genuinely
exist as public pages belong here — private/authenticated routes (platform,
dashboard, brand, approve/[token], report/[token]) must never be listed,
since they must never be indexed or appear in the sitemap.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicPageRoute:
    page_key: str
    path: str
    label: str


PUBLIC_PAGE_ROUTES: tuple[PublicPageRoute, ...] = (
    PublicPageRoute("home", "/", "Ana Sayfa"),
    PublicPageRoute("pricing", "/pricing", "Fiyatlandırma"),
)

# Page keys the SEO editor supports (for pre-launch metadata drafting) but that
# have no corresponding frontend route yet — surfaced as "not yet published"
# in the page inventory rather than silently ignored.
PLANNED_PAGE_KEYS: tuple[str, ...] = ("about", "contact", "features", "blog")

PRIVATE_PATH_PREFIXES: tuple[str, ...] = (
    "/platform",
    "/dashboard",
    "/brand",
    "/approve",
    "/report",
    "/auth",
)


def is_registered_public_path(path: str) -> bool:
    return any(route.path == path for route in PUBLIC_PAGE_ROUTES)
