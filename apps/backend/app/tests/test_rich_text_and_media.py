"""Tests for rich text HTML sanitizer and description_html fields."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.api.v1.brand_portal import BrandBriefCreate, BrandBriefUpdate
from app.core.html_sanitizer import sanitize_html
from app.schemas.brief import BriefCreate, BriefRead, BriefUpdate

# ---------------------------------------------------------------------------
# HTML sanitizer
# ---------------------------------------------------------------------------


def test_sanitize_plain_text_passes_through() -> None:
    assert sanitize_html("Merhaba dünya") == "Merhaba dünya"


def test_sanitize_allowed_tags_preserved() -> None:
    html = "<p><strong>Kalın</strong> ve <em>italik</em></p>"
    result = sanitize_html(html)
    assert "<p>" in result
    assert "<strong>" in result
    assert "<em>" in result


def test_sanitize_script_tag_removed() -> None:
    html = '<script>alert("xss")</script><p>Güvenli</p>'
    result = sanitize_html(html)
    # The <script> tag must be stripped so the code cannot execute
    assert "<script>" not in result
    assert "</script>" not in result
    # The <p> wrapper tag must be preserved
    assert "<p>" in result


def test_sanitize_iframe_removed() -> None:
    html = '<iframe src="https://evil.com"></iframe><p>İçerik</p>'
    result = sanitize_html(html)
    assert "<iframe>" not in result
    assert "<p>" in result


def test_sanitize_onclick_attribute_stripped() -> None:
    html = '<p onclick="alert(1)">Tıkla</p>'
    result = sanitize_html(html)
    assert "onclick" not in result
    assert "<p>" in result


def test_sanitize_javascript_href_stripped() -> None:
    html = '<a href="javascript:alert(1)">Tıkla</a>'
    result = sanitize_html(html)
    # href with javascript: must be removed
    assert "javascript:" not in result


def test_sanitize_valid_href_preserved() -> None:
    html = '<a href="https://example.com">Bağlantı</a>'
    result = sanitize_html(html)
    assert 'href="https://example.com"' in result


def test_sanitize_javascript_href_with_embedded_tab_stripped() -> None:
    """Browsers strip control characters (tab/newline) from a URL before
    parsing its scheme, so this is a real bypass of a naive
    startswith("javascript") check — must still be rejected."""
    html = '<a href="java\tscript:alert(1)">Tıkla</a>'
    result = sanitize_html(html)
    assert "href=" not in result


def test_sanitize_javascript_href_with_embedded_newline_stripped() -> None:
    html = '<a href="java\nscript:alert(1)">Tıkla</a>'
    result = sanitize_html(html)
    assert "href=" not in result


def test_sanitize_javascript_href_mixed_case_stripped() -> None:
    html = '<a href="JavaScript:alert(1)">Tıkla</a>'
    result = sanitize_html(html)
    assert "href=" not in result


def test_sanitize_data_href_stripped() -> None:
    html = '<a href="data:text/html,<script>alert(1)</script>">Tıkla</a>'
    result = sanitize_html(html)
    assert "href=" not in result


def test_sanitize_vbscript_href_stripped() -> None:
    html = '<a href="vbscript:msgbox(1)">Tıkla</a>'
    result = sanitize_html(html)
    assert "href=" not in result


def test_sanitize_relative_href_preserved() -> None:
    html = '<a href="/dashboard/briefs/123">Git</a>'
    result = sanitize_html(html)
    assert 'href="/dashboard/briefs/123"' in result


def test_sanitize_mailto_href_preserved() -> None:
    html = '<a href="mailto:test@example.com">E-posta</a>'
    result = sanitize_html(html)
    assert 'href="mailto:test@example.com"' in result


def test_sanitize_img_onerror_tag_removed() -> None:
    """<img> is not in the tag allowlist at all — the classic onerror=
    payload must be stripped tag and all, not just the attribute."""
    html = '<img src=x onerror="alert(1)"><p>Güvenli</p>'
    result = sanitize_html(html)
    assert "<img" not in result
    assert "onerror" not in result
    assert "<p>" in result


def test_sanitize_svg_with_nested_script_removed() -> None:
    html = "<svg><script>alert(1)</script></svg><p>Güvenli</p>"
    result = sanitize_html(html)
    assert "<svg" not in result
    assert "<script>" not in result
    assert "<p>" in result


def test_sanitize_style_attribute_stripped() -> None:
    html = '<div style="background:url(javascript:alert(1))">İçerik</div>'
    result = sanitize_html(html)
    assert "style" not in result
    assert "<div>" in result


def test_sanitize_object_and_embed_removed() -> None:
    html = '<object data="evil.swf"></object><embed src="evil.swf"><p>OK</p>'
    result = sanitize_html(html)
    assert "<object" not in result
    assert "<embed" not in result
    assert "<p>" in result


def test_sanitize_none_returns_none() -> None:
    assert sanitize_html(None) is None


def test_sanitize_empty_string() -> None:
    assert sanitize_html("") == ""


def test_sanitize_heading_preserved() -> None:
    html = "<h2>Başlık 2</h2><h3>Başlık 3</h3>"
    result = sanitize_html(html)
    assert "<h2>" in result
    assert "<h3>" in result


def test_sanitize_lists_preserved() -> None:
    html = "<ul><li>Madde 1</li><li>Madde 2</li></ul>"
    result = sanitize_html(html)
    assert "<ul>" in result
    assert "<li>" in result


def test_sanitize_nested_allowed_tags() -> None:
    html = "<p><strong><em>Kalın İtalik</em></strong></p>"
    result = sanitize_html(html)
    assert "<p>" in result
    assert "<strong>" in result
    assert "<em>" in result


# ---------------------------------------------------------------------------
# BrandBriefCreate / Update includes description_html
# ---------------------------------------------------------------------------


def test_brand_brief_create_accepts_description_html() -> None:
    b = BrandBriefCreate(
        title="Test",
        description_html="<p><strong>Rich</strong> text</p>",
    )
    assert b.description_html == "<p><strong>Rich</strong> text</p>"


def test_brand_brief_create_description_html_defaults_none() -> None:
    b = BrandBriefCreate(title="Test")
    assert b.description_html is None


def test_brand_brief_update_accepts_description_html() -> None:
    u = BrandBriefUpdate(description_html="<p>Updated</p>")
    assert u.description_html == "<p>Updated</p>"


# ---------------------------------------------------------------------------
# BriefRead / BriefCreate / BriefUpdate includes description_html
# ---------------------------------------------------------------------------


def _make_brief_read(**kwargs):
    now = datetime.utcnow()
    uid = uuid.uuid4()
    defaults = dict(
        id=uid,
        agency_id=uid,
        brand_id=None,
        template_id=None,
        title="Test Brief",
        description=None,
        description_html=None,
        status="draft",
        priority="normal",
        deadline=None,
        source=None,
        meta=None,
        created_by_id=uid,
        updated_by_id=None,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return BriefRead(**defaults)


def test_brief_read_description_html_defaults_none() -> None:
    b = _make_brief_read()
    assert b.description_html is None


def test_brief_read_description_html_set() -> None:
    b = _make_brief_read(description_html="<p>Özet</p>")
    assert b.description_html == "<p>Özet</p>"


def test_brief_create_description_html_optional() -> None:
    bc = BriefCreate(title="Test")
    assert bc.description_html is None


def test_brief_create_description_html_set() -> None:
    bc = BriefCreate(title="Test", description_html="<strong>Özet</strong>")
    assert bc.description_html == "<strong>Özet</strong>"


def test_brief_update_description_html_optional() -> None:
    bu = BriefUpdate()
    assert bu.description_html is None


def test_brief_update_description_html_set() -> None:
    bu = BriefUpdate(description_html="<p>Yeni</p>")
    assert bu.description_html == "<p>Yeni</p>"


# ---------------------------------------------------------------------------
# Brand portal templates endpoint schema
# ---------------------------------------------------------------------------


def test_brief_template_read_schema() -> None:
    from app.api.v1.brand_portal import BriefTemplateRead

    t = BriefTemplateRead(
        id=uuid.uuid4(),
        name="Sosyal Medya Şablonu",
        description="Instagram ve TikTok içerikleri için",
        industry="e-commerce",
        is_system_template=True,
    )
    assert t.name == "Sosyal Medya Şablonu"
    assert t.is_system_template is True


def test_brief_template_read_nullable_fields() -> None:
    from app.api.v1.brand_portal import BriefTemplateRead

    t = BriefTemplateRead(
        id=uuid.uuid4(),
        name="Boş Şablon",
        description=None,
        industry=None,
        is_system_template=False,
    )
    assert t.description is None
    assert t.industry is None
