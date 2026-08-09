"""Tests for Brand Identity / Marka DNA module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.models.brand_identity import BrandIdentityProfile
from app.models.enums import BrandIdentityDocumentStatus, BrandIdentityProfileStatus
from app.schemas.brand_identity import (
    BrandDNASummary,
    BrandIdentityDocumentRead,
    BrandIdentityOverview,
    BrandIdentityProfileRead,
    BrandIdentityProfileUpdate,
    BrandIdentityRevisionRead,
)
from app.services.brand_identity_service import (
    _extract_fonts,
    _extract_hex_colors,
    _extract_summary,
    _parse_brand_dna,
)

# ── Enum tests ────────────────────────────────────────────────────────────────


def test_brand_identity_document_status_values() -> None:
    assert BrandIdentityDocumentStatus.UPLOADED == "uploaded"
    assert BrandIdentityDocumentStatus.PROCESSING == "processing"
    assert BrandIdentityDocumentStatus.ANALYZED == "analyzed"
    assert BrandIdentityDocumentStatus.NEEDS_REVIEW == "needs_review"
    assert BrandIdentityDocumentStatus.APPROVED == "approved"
    assert BrandIdentityDocumentStatus.FAILED == "failed"


def test_brand_identity_profile_status_values() -> None:
    assert BrandIdentityProfileStatus.DRAFT == "draft"
    assert BrandIdentityProfileStatus.AI_GENERATED == "ai_generated"
    assert BrandIdentityProfileStatus.REVIEWED == "reviewed"
    assert BrandIdentityProfileStatus.APPROVED == "approved"


# ── PDF parsing utility tests ─────────────────────────────────────────────────


def test_extract_hex_colors_basic() -> None:
    text = "Ana renk #052562 ve yardımcı renk #E63946 ve #FFFFFF kullanılır."
    colors = _extract_hex_colors(text)
    hexes = [c["hex"] for c in colors]
    assert "#052562" in hexes
    assert "#E63946" in hexes
    assert "#FFFFFF" in hexes


def test_extract_hex_colors_dedup() -> None:
    text = "#AABBCC #AABBCC #AABBCC"
    colors = _extract_hex_colors(text)
    assert len(colors) == 1


def test_extract_hex_colors_max_10() -> None:
    hexes = " ".join(f"#{i:06X}" for i in range(20))
    colors = _extract_hex_colors(hexes)
    assert len(colors) <= 10


def test_extract_hex_colors_short_form_expanded() -> None:
    text = "Renk: #ABC"
    colors = _extract_hex_colors(text)
    assert colors[0]["hex"] == "#AABBCC"


def test_extract_hex_colors_empty() -> None:
    colors = _extract_hex_colors("Bu metinde renk kodu yok.")
    assert colors == []


def test_extract_fonts_finds_known() -> None:
    text = "Başlık fontu olarak Montserrat kullanılmaktadır. Gövde için Inter tercih edilir."
    fonts = _extract_fonts(text)
    families = [f["family"] for f in fonts]
    assert "Montserrat" in families
    assert "Inter" in families


def test_extract_fonts_empty_when_none() -> None:
    fonts = _extract_fonts("Hiçbir font ismi geçmiyor bu cümlede.")
    assert fonts == []


def test_extract_fonts_max_6() -> None:
    many = "Helvetica Arial Roboto Montserrat Lato Poppins Raleway Inter"
    fonts = _extract_fonts(many)
    assert len(fonts) <= 6


def test_extract_summary_returns_sentences() -> None:
    text = (
        "Bu markanın kimlik dokümanı ajansın tüm üretim süreçlerinde"
        " rehber olacak şekilde hazırlanmıştır. "
        "Premium ve modern bir görünüm hedeflenmekte olup lacivert"
        " ve beyaz tonlar ön plana çıkmaktadır. "
        "Marka iletişiminde resmi ve güven veren bir ton benimsenmektedir."
    )
    summary = _extract_summary(text)
    assert summary is not None
    assert len(summary) > 40


def test_extract_summary_returns_none_for_short() -> None:
    summary = _extract_summary("Kısa.")
    assert summary is None


def test_parse_brand_dna_full_output() -> None:
    text = (
        "Kurumsal kimlik belgesi. Renk paletinde #052562 ana lacivert kullanılır. "
        "Yardımcı renkler #E63946 ve #F4A261. "
        "Montserrat başlık fontu, Inter gövde fontu."
    )
    dna = _parse_brand_dna(text)
    assert "primary_colors" in dna
    assert "secondary_colors" in dna
    assert "typography" in dna
    assert "summary" in dna
    assert "confidence_score" in dna
    assert isinstance(dna["confidence_score"], int)
    assert dna["confidence_score"] >= 0


def test_parse_brand_dna_no_colors_no_fonts() -> None:
    text = "Bu marka premium ve kurumsal bir görünüme sahiptir. Sade tasarım tercih edilir."
    dna = _parse_brand_dna(text)
    assert dna["primary_colors"] is None
    assert dna["typography"] is None


# ── Schema validation tests ───────────────────────────────────────────────────


def test_brand_identity_overview_empty() -> None:
    overview = BrandIdentityOverview(profile=None, documents=[])
    assert overview.profile is None
    assert overview.documents == []


def test_brand_identity_profile_update_partial() -> None:
    data = BrandIdentityProfileUpdate(
        summary="Premium marka.",
        change_note="Test değişikliği",
    )
    assert data.summary == "Premium marka."
    assert data.change_note == "Test değişikliği"
    assert data.primary_colors is None


def test_brand_dna_summary_empty() -> None:
    s = BrandDNASummary(
        profile_id=None,
        status=None,
        summary=None,
        primary_colors=None,
        typography=None,
        tone_of_voice=None,
        key_takeaways=None,
        dont_rules=None,
        approved_by_name=None,
        approved_at=None,
    )
    assert s.profile_id is None
    assert s.status is None


def test_brand_identity_profile_read_from_dict() -> None:
    now = "2026-07-12T10:00:00+00:00"
    pid = uuid.uuid4()
    bid = uuid.uuid4()
    data: dict[str, Any] = {
        "id": pid,
        "brand_id": bid,
        "agency_id": None,
        "source_document_id": None,
        "status": "ai_generated",
        "summary": "Premium marka.",
        "primary_colors": [{"hex": "#052562", "name": "Lacivert"}],
        "secondary_colors": None,
        "typography": [{"family": "Montserrat", "role": "Başlık"}],
        "logo_rules": None,
        "visual_style": {"tags": ["premium", "minimal"]},
        "tone_of_voice": {"formal": True},
        "social_media_notes": None,
        "do_rules": None,
        "dont_rules": None,
        "key_takeaways": ["Lacivert arka plan tercih edilir"],
        "confidence_score": 65,
        "is_active": True,
        "reviewed_by_id": None,
        "approved_by_id": None,
        "reviewed_at": None,
        "approved_at": None,
        "approved_by_name": None,
        "created_at": now,
        "updated_at": now,
    }
    profile = BrandIdentityProfileRead(**data)
    assert profile.status == "ai_generated"
    assert profile.confidence_score == 65
    assert profile.primary_colors is not None
    assert profile.primary_colors[0]["hex"] == "#052562"


def test_brand_identity_document_read_from_dict() -> None:
    now = "2026-07-12T10:00:00+00:00"
    doc = BrandIdentityDocumentRead(
        id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
        agency_id=None,
        uploaded_by_id=None,
        file_name="brand_guideline.pdf",
        file_size=1024000,
        content_type="application/pdf",
        status="analyzed",
        analysis_error=None,
        created_at=now,  # type: ignore[arg-type]
        updated_at=now,  # type: ignore[arg-type]
    )
    assert doc.file_name == "brand_guideline.pdf"
    assert doc.status == "analyzed"


def test_brand_identity_revision_read_fields() -> None:
    now = "2026-07-12T10:00:00+00:00"
    rev = BrandIdentityRevisionRead(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        changed_by_id=None,
        changed_by_name="Test User",
        before_json={"summary": "Eski özet"},
        after_json={"summary": "Yeni özet"},
        change_note="Renk paleti güncellendi",
        created_at=now,  # type: ignore[arg-type]
    )
    assert rev.change_note == "Renk paleti güncellendi"
    assert rev.before_json is not None


# ── Content type validation ───────────────────────────────────────────────────


def test_allowed_content_types() -> None:
    from app.services.brand_identity_service import _ALLOWED_CONTENT_TYPES

    assert "application/pdf" in _ALLOWED_CONTENT_TYPES
    assert "image/jpeg" not in _ALLOWED_CONTENT_TYPES
    assert "application/zip" not in _ALLOWED_CONTENT_TYPES


# ── Confidence score logic ────────────────────────────────────────────────────


def test_confidence_score_increases_with_data() -> None:
    text_rich = (
        "Marka #052562 ana lacivert rengi, #E63946 kırmızı, Montserrat, Inter, Lato. "
        "Bu markanın kurumsal kimliği güçlüdür ve premium bir görünüm hedeflenmektedir. "
        "Sade, minimal tasarım anlayışı benimsenir. "
    )
    text_poor = "Marka."
    dna_rich = _parse_brand_dna(text_rich)
    dna_poor = _parse_brand_dna(text_poor)
    assert (dna_rich["confidence_score"] or 0) > (dna_poor["confidence_score"] or 0)


# ── reviewed_at/approved_at timezone-awareness regression ────────────────────
#
# brand_identity_service.py assigns `profile.approved_at = datetime.now(UTC)`
# (an aware datetime) while the DB columns have always been created as
# `TIMESTAMP WITH TIME ZONE` (see alembic/versions/r8s9t0u1v2w3_add_brand_identity.py).
# The ORM model previously declared these columns as bare `Mapped[datetime | None]`
# with no explicit `DateTime(timezone=True)`, which resolves to a timezone-naive
# SQLAlchemy type. Under the asyncpg dialect this causes bind parameters to be
# cast to `::TIMESTAMP` (no tz) before being written into a `timestamptz` column
# -- a silent instant-shifting round-trip whenever the DB session timezone isn't
# UTC. `Deliverable.submitted_at`/`approved_at` hit the exact same bug and were
# fixed the same way (see migration c9d0e1f2a3b4); this is that same class of
# bug, just never applied to BrandIdentityProfile.


def test_brand_identity_profile_timestamps_declared_timezone_aware() -> None:
    """Static guard: reviewed_at/approved_at must keep DateTime(timezone=True).

    Prevents the mismatch from being reintroduced silently (e.g. by a refactor
    that drops the explicit type and lets it fall back to the untyped default).
    """
    columns = BrandIdentityProfile.__table__.c
    assert columns["reviewed_at"].type.timezone is True
    assert columns["approved_at"].type.timezone is True


async def test_brand_identity_profile_approved_at_round_trips_same_instant() -> None:
    """Live-DB proof: writing an aware datetime.now(UTC) via the ORM (as
    brand_identity_service.py does) and reading it back through raw SQL must
    yield the exact same instant, stored as timestamptz -- not silently
    reinterpreted through a naive-cast round trip.
    """
    agency_id = uuid.uuid4()
    brand_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    known_instant = datetime(2026, 6, 15, 9, 0, 0, tzinfo=UTC)

    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "INSERT INTO agencies (id, name, slug, status, created_at, updated_at) "
                "VALUES (:id, 'TZ Regression Agency', :slug, 'active', now(), now())"
            ),
            {"id": agency_id, "slug": f"tz-regress-{uuid.uuid4().hex[:10]}"},
        )
        await session.execute(
            text(
                "INSERT INTO brands (id, agency_id, name, slug, status, created_at, updated_at) "
                "VALUES (:id, :agency_id, 'TZ Regression Brand', :slug, 'active', now(), now())"
            ),
            {"id": brand_id, "agency_id": agency_id, "slug": f"tz-regress-{uuid.uuid4().hex[:10]}"},
        )
        session.add(
            BrandIdentityProfile(
                id=profile_id,
                brand_id=brand_id,
                agency_id=agency_id,
                status="approved",
                reviewed_at=known_instant,
                approved_at=known_instant,
            )
        )
        await session.commit()

    try:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT approved_at, pg_typeof(approved_at)::text "
                        "FROM brand_identity_profiles WHERE id = :id"
                    ),
                    {"id": profile_id},
                )
            ).first()
            stored_value, pg_type = row[0], row[1]
            assert pg_type == "timestamp with time zone"
            assert stored_value.tzinfo is not None
            assert stored_value == known_instant
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM agencies WHERE id = :id"), {"id": agency_id})
            await session.commit()
