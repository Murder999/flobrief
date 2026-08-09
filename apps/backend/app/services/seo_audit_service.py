"""Real, deterministic technical SEO audit computed from stored settings —
no fabricated scores, no invented keyword/traffic estimates."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.seo_registry import PLANNED_PAGE_KEYS, PUBLIC_PAGE_ROUTES
from app.models.platform_seo_settings import PlatformGrowthSettings, PlatformSeoPageSettings
from app.schemas.platform import (
    PlatformSeoAuditIssue,
    PlatformSeoHealthSummary,
    PlatformSeoPageInventoryItem,
)

_DESCRIPTION_MAX = 160
_DESCRIPTION_MIN_WARN = 50
_SEVERITY_PENALTY = {"critical": 12, "high": 8, "medium": 4, "low": 1}


async def _load_pages(db: AsyncSession) -> dict[str, PlatformSeoPageSettings]:
    result = await db.execute(
        select(PlatformSeoPageSettings).where(PlatformSeoPageSettings.deleted_at.is_(None))
    )
    return {p.page_key: p for p in result.scalars().all()}


async def _load_growth(db: AsyncSession) -> PlatformGrowthSettings | None:
    result = await db.execute(
        select(PlatformGrowthSettings).where(
            PlatformGrowthSettings.setting_key == "default",
            PlatformGrowthSettings.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def run_audit(db: AsyncSession) -> list[PlatformSeoAuditIssue]:
    pages = await _load_pages(db)
    growth = await _load_growth(db)
    issues: list[PlatformSeoAuditIssue] = []

    seen_titles: dict[str, list[str]] = {}
    seen_descriptions: dict[str, list[str]] = {}

    for route in PUBLIC_PAGE_ROUTES:
        page = pages.get(route.page_key)
        if page is None:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="high",
                    page_key=route.page_key,
                    area="seo_meta",
                    problem=f"'{route.label}' için SEO ayarı hiç oluşturulmamış",
                    reason="Gerçek bir public route için metadata tanımlı değil.",
                    suggestion="SEO Meta sekmesinden bu sayfa için ayar oluşturun.",
                )
            )
            continue

        if not page.title:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="critical",
                    page_key=route.page_key,
                    area="seo_meta",
                    problem=f"'{route.label}' sayfasında title eksik",
                    reason="Arama sonuçlarında başlık gösterilmezse tıklama oranı ciddi düşer.",
                    suggestion="SEO Meta sekmesinden bu sayfaya bir title girin.",
                )
            )
        else:
            seen_titles.setdefault(page.title.strip().lower(), []).append(route.page_key)

        if not page.description:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="critical",
                    page_key=route.page_key,
                    area="seo_meta",
                    problem=f"'{route.label}' sayfasında meta description eksik",
                    reason=(
                        "Description eksikse Google rastgele bir metin gösterir, "
                        "dönüşüm oranı düşer."
                    ),
                    suggestion="SEO Meta sekmesinden 50-160 karakter arası bir açıklama girin.",
                )
            )
        else:
            desc_key = page.description.strip().lower()
            seen_descriptions.setdefault(desc_key, []).append(route.page_key)
            desc_len = len(page.description)
            if desc_len > _DESCRIPTION_MAX:
                issues.append(
                    PlatformSeoAuditIssue(
                        severity="medium",
                        page_key=route.page_key,
                        area="seo_meta",
                        problem=f"'{route.label}' description {desc_len} karakter (>160)",
                        reason="Google 160 karakterden uzun açıklamaları arama sonucunda keser.",
                        suggestion="Açıklamayı 160 karakterin altına indirin.",
                    )
                )
            elif desc_len < _DESCRIPTION_MIN_WARN:
                issues.append(
                    PlatformSeoAuditIssue(
                        severity="low",
                        page_key=route.page_key,
                        area="seo_meta",
                        problem=f"'{route.label}' description çok kısa ({desc_len} karakter)",
                        reason="Çok kısa açıklamalar arama sonucunda zayıf görünür.",
                        suggestion="Açıklamayı 50-160 karakter aralığına çıkarın.",
                    )
                )

        if not page.canonical_url:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="medium",
                    page_key=route.page_key,
                    area="seo_meta",
                    problem=f"'{route.label}' canonical URL eksik",
                    reason="Canonical eksikse duplicate content sinyali riskini artırır.",
                    suggestion="SEO Meta sekmesinden canonical URL girin.",
                )
            )
        if not page.indexable:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="high",
                    page_key=route.page_key,
                    area="seo_meta",
                    problem=f"'{route.label}' noindex olarak işaretli",
                    reason="Bu sayfa herkese açık ve gerçek bir route olduğu halde aranamayacak.",
                    suggestion="Bilerek gizlenmediyse indexable ayarını açın.",
                )
            )
        if not page.og_image_url or not page.og_title:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="low",
                    page_key=route.page_key,
                    area="seo_meta",
                    problem=f"'{route.label}' Open Graph bilgisi eksik",
                    reason="Sosyal paylaşımlarda başlıksız/görselsiz kart gösterilir.",
                    suggestion="OG başlık ve görsel ekleyin.",
                )
            )

    for _title, keys in seen_titles.items():
        if len(keys) > 1:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="medium",
                    page_key=None,
                    area="seo_meta",
                    problem=f"Aynı title birden fazla sayfada kullanılıyor: {', '.join(keys)}",
                    reason=(
                        "Duplicate title arama motorlarının sayfaları ayırt "
                        "etmesini zorlaştırır."
                    ),
                    suggestion="Her sayfaya özgün bir title verin.",
                )
            )
    for _desc, keys in seen_descriptions.items():
        if len(keys) > 1:
            issues.append(
                PlatformSeoAuditIssue(
                    severity="medium",
                    page_key=None,
                    area="seo_meta",
                    problem=(
                        "Aynı description birden fazla sayfada kullanılıyor: " f"{', '.join(keys)}"
                    ),
                    reason="Duplicate description arama sonuçlarında ayrışmayı zayıflatır.",
                    suggestion="Her sayfaya özgün bir açıklama verin.",
                )
            )

    if growth is None or not growth.robots_txt:
        issues.append(
            PlatformSeoAuditIssue(
                severity="high",
                page_key=None,
                area="robots",
                problem="robots.txt yapılandırılmamış",
                reason=(
                    "robots.txt yoksa arama motorları varsayılan "
                    "(tamamen izinli) davranışı kullanır."
                ),
                suggestion="robots.txt sekmesinden en az bir Allow ve Sitemap satırı tanımlayın.",
            )
        )
    elif "sitemap:" not in growth.robots_txt.lower():
        issues.append(
            PlatformSeoAuditIssue(
                severity="medium",
                page_key=None,
                area="robots",
                problem="robots.txt içinde Sitemap: satırı yok",
                reason="Arama motorları sitemap konumunu otomatik bulamayabilir.",
                suggestion="robots.txt sonuna 'Sitemap: <public_app_url>/sitemap.xml' ekleyin.",
            )
        )

    if growth is None or not growth.sitemap_last_generated_at:
        issues.append(
            PlatformSeoAuditIssue(
                severity="medium",
                page_key=None,
                area="sitemap",
                problem="sitemap.xml hiç oluşturulmamış",
                reason="Sitemap olmadan arama motorları yeni sayfaları geç keşfeder.",
                suggestion="SEO Merkezi'nden sitemap'i yeniden oluşturun.",
            )
        )

    if growth is None or not growth.public_app_url:
        issues.append(
            PlatformSeoAuditIssue(
                severity="high",
                page_key=None,
                area="seo_meta",
                problem="Public App URL tanımlanmamış",
                reason="Canonical origin ve sitemap URL'leri bu değere dayanır.",
                suggestion="Takip Kodları sekmesinden Public App URL girin.",
            )
        )

    return issues


async def build_page_inventory(db: AsyncSession) -> list[PlatformSeoPageInventoryItem]:
    pages = await _load_pages(db)
    issues = await run_audit(db)
    issue_by_page: dict[str | None, list[PlatformSeoAuditIssue]] = {}
    for issue in issues:
        issue_by_page.setdefault(issue.page_key, []).append(issue)

    items: list[PlatformSeoPageInventoryItem] = []
    for route in PUBLIC_PAGE_ROUTES:
        page = pages.get(route.page_key)
        page_issues = issue_by_page.get(route.page_key, [])
        severity = "healthy"
        if any(i.severity == "critical" for i in page_issues):
            severity = "critical"
        elif page_issues:
            severity = "warning"
        items.append(
            PlatformSeoPageInventoryItem(
                page_key=route.page_key,
                path=route.path,
                label=route.label,
                status="published",
                title=page.title if page else None,
                description=page.description if page else None,
                canonical_url=page.canonical_url if page else None,
                indexable=page.indexable if page else False,
                has_og_image=bool(page.og_image_url) if page else False,
                issue_count=len(page_issues),
                severity=severity,
            )
        )
    for key in PLANNED_PAGE_KEYS:
        page = pages.get(key)
        items.append(
            PlatformSeoPageInventoryItem(
                page_key=key,
                path=None,
                label=key.capitalize(),
                status="not_built",
                title=page.title if page else None,
                description=page.description if page else None,
                canonical_url=page.canonical_url if page else None,
                indexable=False,
                has_og_image=bool(page.og_image_url) if page else False,
                issue_count=0,
                severity="healthy",
            )
        )
    return items


async def build_health_summary(db: AsyncSession) -> PlatformSeoHealthSummary:
    issues = await run_audit(db)
    growth = await _load_growth(db)
    pages = await _load_pages(db)

    critical = sum(1 for i in issues if i.severity in ("critical", "high"))
    warning = sum(1 for i in issues if i.severity in ("medium", "low"))
    penalty = sum(_SEVERITY_PENALTY.get(i.severity, 1) for i in issues)
    health_score = max(0, min(100, 100 - penalty))

    indexable_count = sum(
        1
        for route in PUBLIC_PAGE_ROUTES
        if pages.get(route.page_key) and pages[route.page_key].indexable
    )
    missing_title = sum(
        1
        for route in PUBLIC_PAGE_ROUTES
        if not (pages.get(route.page_key) and pages[route.page_key].title)
    )
    missing_desc = sum(
        1
        for route in PUBLIC_PAGE_ROUTES
        if not (pages.get(route.page_key) and pages[route.page_key].description)
    )

    return PlatformSeoHealthSummary(
        health_score=health_score,
        critical_count=critical,
        warning_count=warning,
        indexable_page_count=indexable_count,
        missing_title_count=missing_title,
        missing_description_count=missing_desc,
        sitemap_configured=bool(growth and growth.sitemap_last_generated_at),
        robots_configured=bool(growth and growth.robots_txt),
        last_audit_at=datetime.now(UTC).isoformat(),
    )
