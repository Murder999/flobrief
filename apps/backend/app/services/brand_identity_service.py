"""Brand Identity / Marka DNA service.

Handles PDF upload, text extraction (pypdf), rule-based brand DNA parsing,
profile management, and revision tracking.
"""

from __future__ import annotations

import io
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.brand_identity import (
    BrandIdentityDocument,
    BrandIdentityProfile,
    BrandIdentityRevision,
)
from app.models.user import User
from app.schemas.brand_identity import (
    BrandDNASummary,
    BrandIdentityDocumentRead,
    BrandIdentityOverview,
    BrandIdentityProfileRead,
    BrandIdentityProfileUpdate,
    BrandIdentityRevisionRead,
)
from app.services.storage_service import get_storage_backend, normalize_filename

_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/x-pdf",
    }
)
_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB

# Well-known font names for heuristic extraction
_KNOWN_FONTS = [
    "Helvetica",
    "Arial",
    "Roboto",
    "Montserrat",
    "Open Sans",
    "Lato",
    "Poppins",
    "Raleway",
    "Nunito",
    "Inter",
    "Source Sans",
    "Playfair",
    "Oswald",
    "Merriweather",
    "PT Sans",
    "Ubuntu",
    "Fira",
    "Nunito Sans",
    "Barlow",
    "Noto Sans",
    "DM Sans",
    "IBM Plex",
    "Gotham",
    "Futura",
    "Garamond",
    "Times New Roman",
    "Georgia",
    "Verdana",
    "Tahoma",
    "Trebuchet",
    "Century Gothic",
    "Gill Sans",
    "Brandon Grotesque",
    "Proxima Nova",
    "Avenir",
    "Univers",
    "Trade Gothic",
    "Bodoni",
    "Calibri",
    "Cambria",
    "Optima",
    "Bebas Neue",
    "Cabin",
    "Aktif",
    "Museo",
    "Neue Haas",
    "Akzidenz",
    "DIN",
    "FF DIN",
    "Source Pro",
    "Work Sans",
    "Mulish",
    "Karla",
    "Space Grotesk",
]

# Section header keywords (TR/EN) mapped to section type
_SECTION_HEADERS: list[tuple[str, str]] = [
    (
        r"renk\s*paleti?|renkler|kurumsal\s*renkler?"
        r"|primary\s*colou?rs?|brand\s*colou?rs?|colou?r\s*palette?",
        "color",
    ),
    (r"tipografi|yazı\s*tipi(?:leri)?|fontlar?|typography|typeface|type\s*family", "typography"),
    (
        r"logo\s*kullanım|logo\s*kuralları?|logo\s*alanı"
        r"|logo\s*uygulamaları?|logo\s*yasakları?|amblem|logotype|logo\s*spec",
        "logo",
    ),
    (
        r"iletişim\s*(?:dili|tonu?)|ton(?:u?\s*ve\s*dil)?|yazı\s*(?:dili|tonu?)"
        r"|tone\s*of\s*voice|brand\s*voice|dil\s*(?:klavuzu?|ve\s*ton)",
        "tone",
    ),
    (
        r"sosyal\s*medya|dijital\s*medya|social\s*media" r"|dijital\s*iletisim|icerik\s*kurallari?",
        "social",
    ),
    (
        r"dogru\s*kullanim|olmasi\s*gereken|yapilacaklar?" r"|correct\s*usage|uygun\s*kullanim",
        "do",
    ),
    (
        r"yanlis\s*kullanim|yasak\s*kullanim|yapilmayacaklar?"
        r"|kacinilamasi\s*gereken|incorrect|forbidden|uygunsuz",
        "dont",
    ),
    (
        r"gorsel\s*(?:kimlik|dil|stil)|visual\s*(?:identity|style|language)"
        r"|tasarim\s*ilkeleri?",
        "visual",
    ),
]

_TONE_ADJECTIVES_TR = [
    "güvenilir",
    "profesyonel",
    "sade",
    "net",
    "anlaşılır",
    "kurumsal",
    "dinamik",
    "yenilikçi",
    "samimi",
    "ciddi",
    "modern",
    "yaratıcı",
    "teknolojik",
    "insancıl",
    "sürdürülebilir",
    "minimal",
    "premium",
    "yalın",
    "şeffaf",
    "pozitif",
    "enerjik",
    "güçlü",
    "cesur",
    "sıcak",
    "sofistike",
    "zarif",
]
_TONE_ADJECTIVES_EN = [
    "professional",
    "trustworthy",
    "innovative",
    "reliable",
    "modern",
    "simple",
    "clear",
    "corporate",
    "dynamic",
    "creative",
    "minimal",
    "authentic",
    "bold",
    "warm",
    "elegant",
    "sophisticated",
    "energetic",
]


def _extract_pdf_text(data: bytes) -> tuple[str, bool]:
    """Legacy wrapper — used by tests. Delegates to full extractor."""
    result = _extract_pdf_data(data)
    return result["text"], result["is_image_based"]


def _extract_pdf_data(data: bytes) -> dict[str, Any]:
    """Full extraction: text + font metadata + visual colors + debug info.

    Returns a dict with keys:
      text, is_image_based, page_count, method,
      fonts_from_pdf, visual_colors, debug
    """
    debug: dict[str, Any] = {
        "page_count": 0,
        "text_length": 0,
        "extraction_method": "none",
        "is_image_based": True,
        "hex_count_in_text": 0,
        "rgb_count_in_text": 0,
        "font_metadata_count": 0,
        "visual_colors_extracted": 0,
        "notes": [],
    }

    text = ""
    page_count = 0
    fonts_from_pdf: list[dict[str, Any]] = []
    visual_colors: list[dict[str, Any]] = []

    # ── 0. Dependency availability check ─────────────────────────────────────
    _pymupdf_available = False
    _pypdf_available = False
    try:
        import fitz as _fitz_check  # noqa: F401

        _pymupdf_available = True
    except ImportError:
        debug["notes"].append("pymupdf_unavailable")
    try:
        import pypdf as _pypdf_check  # noqa: F401

        _pypdf_available = True
    except ImportError:
        debug["notes"].append("pypdf_unavailable")

    debug["pymupdf_available"] = _pymupdf_available
    debug["pypdf_available"] = _pypdf_available

    if not _pymupdf_available and not _pypdf_available:
        debug["extraction_method"] = "missing_deps"
        debug["notes"].append(
            "PDF analiz kütüphaneleri yüklü değil: PyMuPDF ve pypdf eksik. "
            "Backend ortamında kurulum gerekli."
        )
        return {
            "text": "",
            "is_image_based": False,
            "page_count": 0,
            "method": "missing_deps",
            "fonts_from_pdf": [],
            "visual_colors": [],
            "debug": debug,
            "missing_deps": True,
        }

    # ── 1. PyMuPDF (primary) ──────────────────────────────────────────────────
    pymupdf_ok = False
    try:
        import fitz  # type: ignore[import]  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        page_count = len(doc)
        debug["page_count"] = page_count

        pages_text: list[str] = []
        font_counts: dict[str, list[float]] = {}

        for page in doc:
            page_text = page.get_text("text") or ""
            pages_text.append(page_text)

            # Collect font spans for metadata extraction
            try:
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block.get("type") == 0:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                fn = span.get("font", "")
                                sz = float(span.get("size", 0))
                                if fn and sz > 5:
                                    font_counts.setdefault(fn, []).append(sz)
            except Exception:
                pass

        text = "\n".join(pages_text).strip()
        debug["extraction_method"] = "pymupdf"
        pymupdf_ok = True

        # Font metadata extraction
        if font_counts:
            avg_sizes = {f: sum(s) / len(s) for f, s in font_counts.items()}
            sorted_f = sorted(avg_sizes.items(), key=lambda x: -x[1])
            roles = ["Başlık", "Alt Başlık", "Gövde", "Vurgu", "Küçük"]
            for i, (fname, avg_sz) in enumerate(sorted_f[:5]):
                clean = re.sub(r"^[A-Z]{6}\+", "", fname).strip()
                if not clean or len(clean) < 2:
                    continue
                w = "Bold" if "bold" in fname.lower() else None
                fonts_from_pdf.append(
                    {
                        "role": roles[i] if i < len(roles) else None,
                        "family": clean,
                        "weight": w,
                        "source": "pdf_font_metadata",
                        "usage": (
                            f"Ort. {avg_sz:.0f}pt — PDF'te {len(font_counts[fname])} kullanım"
                        ),
                    }
                )
            debug["font_metadata_count"] = len(fonts_from_pdf)

        # Visual color extraction (render first 6 pages to image)
        visual_colors = _extract_visual_colors_from_doc(doc, max_pages=6)
        debug["visual_colors_extracted"] = len(visual_colors)

        doc.close()
    except Exception as exc:
        debug["notes"].append(f"PyMuPDF hatası: {type(exc).__name__}: {exc!s:.100}")

    # ── 2. pypdf fallback (if PyMuPDF gave no text) ────────────────────────────
    if not text and not pymupdf_ok:
        try:
            import pypdf  # type: ignore[import]

            reader = pypdf.PdfReader(io.BytesIO(data))
            if page_count == 0:
                page_count = len(reader.pages)
                debug["page_count"] = page_count
            pages_text2 = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages_text2).strip()
            if text:
                debug["extraction_method"] = "pypdf"
        except Exception as exc:
            debug["notes"].append(f"pypdf hatası: {type(exc).__name__}: {exc!s:.80}")

    text_len = len(text)
    is_image_based = text_len < 150
    debug["text_length"] = text_len
    debug["is_image_based"] = is_image_based

    # Count inline color codes in text
    debug["hex_count_in_text"] = len(re.findall(r"#[0-9a-fA-F]{6}\b", text))
    debug["rgb_count_in_text"] = len(
        re.findall(
            r"R[GB]?B?\s*[:\s(]?\s*\d{1,3}\s*[,\s]\s*\d{1,3}\s*[,\s]\s*\d{1,3}", text, re.IGNORECASE
        )
    )

    if is_image_based:
        debug["notes"].append(
            "PDF görsel tabanlı veya metin çıkarılamadı. "
            "OCR gerekmektedir. Manuel veri girişi önerilir."
        )
    if not fonts_from_pdf and text:
        debug["notes"].append("Font metadata bulunamadı; metin tabanlı tahminden çıkarılıyor.")

    return {
        "text": text,
        "is_image_based": is_image_based,
        "page_count": page_count,
        "method": debug["extraction_method"],
        "fonts_from_pdf": fonts_from_pdf,
        "visual_colors": visual_colors,
        "debug": debug,
    }


def _extract_visual_colors_from_doc(doc: Any, max_pages: int = 6) -> list[dict[str, Any]]:
    """Render PDF pages and extract dominant non-neutral colors using PIL."""
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        return []

    color_votes: dict[str, int] = {}
    pages_checked = min(len(doc), max_pages)

    for page_num in range(pages_checked):
        try:
            page = doc[page_num]
            # Render at 72 DPI to keep it fast
            mat = page.get_pixmap(matrix=page.transformation_matrix, dpi=72)  # type: ignore[attr-defined]
            img_bytes = mat.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            # Downsample for speed
            img = img.resize((150, int(150 * img.height / img.width)), Image.LANCZOS)
            # Quantize to extract dominant colors
            quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
            palette = quantized.getpalette() or []
            for i in range(16):
                r, g, b = palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2]
                brightness = (r + g + b) / 3
                saturation = max(r, g, b) - min(r, g, b)
                # Skip near-white, near-black, near-gray
                if brightness > 235 or brightness < 20 or saturation < 35:
                    continue
                # Also skip muted/desaturated grays
                if saturation < 50 and brightness > 150:
                    continue
                hex_v = _rgb_to_hex(r, g, b)
                color_votes[hex_v] = color_votes.get(hex_v, 0) + 1
        except Exception:
            continue

    # Sort by vote count, return top 8
    sorted_colors = sorted(color_votes.items(), key=lambda x: -x[1])
    result: list[dict[str, Any]] = []
    seen_close: list[tuple[int, int, int]] = []

    for hex_v, _ in sorted_colors[:20]:
        # Parse back to RGB to check closeness
        rv = int(hex_v[1:3], 16)
        gv = int(hex_v[3:5], 16)
        bv = int(hex_v[5:7], 16)
        # Merge very similar colors (within 25 units per channel)
        is_dup = any(
            abs(rv - er) < 25 and abs(gv - eg) < 25 and abs(bv - eb) < 25
            for er, eg, eb in seen_close
        )
        if not is_dup:
            seen_close.append((rv, gv, bv))
            result.append(
                {
                    "hex": hex_v,
                    "name": "Tahmini Renk",
                    "rgb": f"{rv}, {gv}, {bv}",
                    "source": "visual_extraction",
                    "confidence": "estimated",
                    "usage": "PDF görsel paletinden tahmini çıkarıldı — manuel doğrulama önerilir.",
                }
            )
        if len(result) >= 8:
            break

    return result


# ── Color helpers ──────────────────────────────────────────────────────────────


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def _cmyk_to_hex(c: float, m: float, y: float, k: float) -> str:
    r = int(255 * (1 - c / 100) * (1 - k / 100))
    g = int(255 * (1 - m / 100) * (1 - k / 100))
    b = int(255 * (1 - y / 100) * (1 - k / 100))
    return _rgb_to_hex(r, g, b)


def _extract_hex_colors(text: str) -> list[dict[str, Any]]:
    """Find HEX color codes in text (used by tests — delegates to full extractor)."""
    return _extract_colors(text)[:10]


def _extract_colors(text: str) -> list[dict[str, Any]]:
    """Extract colors from HEX, RGB, and CMYK formats."""
    seen: set[str] = set()
    colors: list[dict[str, Any]] = []

    def _add(hex_val: str, rgb: str | None = None, usage: str | None = None) -> None:
        if hex_val not in seen and hex_val != "#000000" or not seen:
            # Skip pure black unless it's the only color (common PDF artifact)
            if hex_val == "#000000" and len(seen) == 0:
                return
            seen.add(hex_val)
            colors.append({"hex": hex_val, "name": None, "rgb": rgb, "usage": usage})

    # HEX: #XXXXXX or #XXX
    for m in re.finditer(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", text):
        raw = m.group(1)
        if len(raw) == 3:
            raw = raw[0] * 2 + raw[1] * 2 + raw[2] * 2
        _add(f"#{raw.upper()}")
        if len(colors) >= 10:
            break

    # RGB: R: 5 G: 37 B: 98 | RGB(5, 37, 98) | R 5 G 37 B 98 | 5 37 98 (after RGB label)
    for m in re.finditer(
        r"R[GB]?B?\s*[:\s(]?\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})",
        text,
        re.IGNORECASE,
    ):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if r <= 255 and g <= 255 and b <= 255:
            _add(_rgb_to_hex(r, g, b), rgb=f"{r}, {g}, {b}")
        if len(colors) >= 10:
            break

    # CMYK: C: 95 M: 62 Y: 0 K: 62  or  95/62/0/62
    for m in re.finditer(
        r"C[:\s]+(\d{1,3})\s*[,/]\s*M[:\s]*(\d{1,3})\s*[,/]\s*Y[:\s]*(\d{1,3})\s*[,/]\s*K[:\s]*(\d{1,3})",
        text,
        re.IGNORECASE,
    ):
        c, mv, y, k = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if all(v <= 100 for v in [c, mv, y, k]):
            _add(_cmyk_to_hex(c, mv, y, k), usage=f"CMYK {c}/{mv}/{y}/{k}")
        if len(colors) >= 10:
            break

    return colors[:10]


# ── Font helpers ───────────────────────────────────────────────────────────────


def _extract_fonts(text: str) -> list[dict[str, Any]]:
    """Heuristic font name extraction from known list."""
    lower_text = text.lower()
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Determine roles from context around font name
    font_role_patterns = [
        (r"(başlık|header|heading|title|manşet)", "Başlık"),
        (r"(gövde|body|metin|text|paragraf)", "Gövde"),
        (r"(alt\s*başlık|subhead|subtitle)", "Alt Başlık"),
        (r"(vurgu|accent|highlight|öne\s*çıkan)", "Vurgu"),
        (r"(alıntı|quote|citation)", "Alıntı"),
    ]

    for font in _KNOWN_FONTS:
        fl = re.escape(font.lower())
        # Require word boundary so "Inter" doesn't match "internal", "Mark" ≠ "marka"
        if re.search(r"\b" + fl + r"\b", lower_text) and font not in seen:
            seen.add(font)
            # Look for role context around this font name
            role = None
            idx = lower_text.find(fl)
            context = lower_text[max(0, idx - 80) : idx + 80]
            for pat, role_label in font_role_patterns:
                if re.search(pat, context, re.IGNORECASE):
                    role = role_label
                    break

            # Look for weight context
            weight = None
            _weight_pat = r"\b(bold|regular|light|medium|semibold|thin|black|700|400|300|600|800)\b"
            weight_m = re.search(_weight_pat, context, re.IGNORECASE)
            if weight_m:
                weight = weight_m.group(1).capitalize()

            found.append(
                {
                    "role": role,
                    "family": font,
                    "weight": weight,
                    "usage": None,
                }
            )
        if len(found) >= 6:
            break
    return found


# ── Section splitter ───────────────────────────────────────────────────────────


def _split_sections(text: str) -> dict[str, str]:
    """Split text into named sections by header keyword matching."""
    lines = text.split("\n")
    sections: dict[str, list[str]] = {"general": []}
    current = "general"

    for line in lines:
        stripped = line.strip()
        # Short lines (< 80 chars) that match a header pattern become section markers
        if 3 <= len(stripped) <= 80:
            matched_sec = None
            for pattern, sec_name in _SECTION_HEADERS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    matched_sec = sec_name
                    break
            if matched_sec:
                current = matched_sec
                sections.setdefault(current, [])
                continue
        sections.setdefault(current, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


# ── Rule/list extractor ────────────────────────────────────────────────────────


def _extract_rules(text: str, max_rules: int = 10) -> list[str]:
    """Extract bullet/numbered list items from a text block."""
    rules: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        # Strip common bullet characters
        cleaned = re.sub(r"^[•‣⁃●◦∙\-\*>]\s+", "", s)
        # Strip leading numbers/letters: "1." "a)" "i."
        cleaned = re.sub(r"^(?:\d+|[a-zA-Z])[.)]\s+", "", cleaned)
        if len(cleaned) > 25:
            rules.append(cleaned[:400].strip())
        if len(rules) >= max_rules:
            break
    return rules


# ── Summary ────────────────────────────────────────────────────────────────────


def _extract_summary(text: str) -> str | None:
    """First 2-3 meaningful sentences."""
    sentences = re.split(r"[.!?]\s+", text[:4000])
    meaningful = [s.strip() for s in sentences if len(s.strip()) > 40]
    if not meaningful:
        return None
    return ". ".join(meaningful[:3]) + "."


# ── Tone of voice ──────────────────────────────────────────────────────────────


def _extract_tone(sections: dict[str, str], full_text: str) -> dict[str, Any] | None:
    """Extract tone of voice description and tags."""
    tone_text = sections.get("tone", "") or ""
    search_text = tone_text if tone_text else full_text[:3000]

    tags: list[str] = []
    seen_tags: set[str] = set()
    all_adjs = _TONE_ADJECTIVES_TR + _TONE_ADJECTIVES_EN
    for adj in all_adjs:
        if re.search(adj, search_text, re.IGNORECASE):
            tag = adj.replace(r"\s*", " ").strip().capitalize()
            # Normalize whitespace in tag
            tag = re.sub(r"\s+", " ", tag)
            if tag not in seen_tags:
                seen_tags.add(tag)
                tags.append(tag)
        if len(tags) >= 8:
            break

    # Extract a summary sentence from tone section
    tone_summary = None
    if tone_text:
        sentences = re.split(r"[.!?]\s+", tone_text)
        for s in sentences:
            if len(s.strip()) > 40:
                tone_summary = s.strip()[:300]
                break

    if not tags and not tone_summary:
        return None

    return {
        "summary": tone_summary,
        "tags": tags[:6],
        "preferred_words": [],
        "avoid_words": [],
    }


# ── Visual style ───────────────────────────────────────────────────────────────


def _extract_visual_style(sections: dict[str, str], full_text: str) -> dict[str, Any] | None:
    """Extract visual style tags and description."""
    vis_text = sections.get("visual", "") or ""
    search_text = vis_text if vis_text else full_text[:3000]

    style_keywords = [
        r"minimali?s[tm]",
        r"premium",
        r"modern",
        r"klasik",
        r"kurumsal",
        r"sade",
        r"geometric",
        r"geometrik",
        r"flat",
        r"clean",
        r"temiz",
        r"bold",
        r"cesur",
        r"dinamik",
        r"zarif",
        r"elegant",
        r"sofistike",
        r"teknolojik",
        r"yenilikçi",
        r"innovative",
    ]
    tags: list[str] = []
    seen_t: set[str] = set()
    for kw in style_keywords:
        if re.search(kw, search_text, re.IGNORECASE):
            tag = re.sub(r"[\\?]", "", kw).replace(r"\b", "").strip().capitalize()
            tag = re.sub(r"\s+", " ", tag)
            if tag not in seen_t:
                seen_t.add(tag)
                tags.append(tag)
        if len(tags) >= 6:
            break

    desc = None
    if vis_text:
        sentences = re.split(r"[.!?]\s+", vis_text)
        for s in sentences:
            if len(s.strip()) > 40:
                desc = s.strip()[:300]
                break

    if not tags and not desc:
        return None

    return {"description": desc, "tags": tags[:6]}


# ── Main DNA parser ────────────────────────────────────────────────────────────


def _parse_brand_dna(text: str) -> dict[str, Any]:
    """Legacy entry point — used by unit tests. Calls full builder with no visual data."""
    return _build_dna_from_extraction(text, fonts_from_pdf=[], visual_colors=[])


def _build_dna_from_extraction(
    text: str,
    fonts_from_pdf: list[dict[str, Any]],
    visual_colors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build brand DNA dict from all extraction sources."""
    empty: dict[str, Any] = {
        "summary": None,
        "primary_colors": None,
        "secondary_colors": None,
        "typography": None,
        "logo_rules": None,
        "visual_style": None,
        "tone_of_voice": None,
        "social_media_notes": None,
        "do_rules": None,
        "dont_rules": None,
        "key_takeaways": None,
        "confidence_score": 0,
    }

    # ── Colors ─────────────────────────────────────────────────────────────────
    text_colors = _extract_colors(text) if text else []

    # Merge: text colors take priority (they have explicit hex/rgb values);
    # visual colors fill in what text couldn't find
    seen_hex: set[str] = set()
    merged_colors: list[dict[str, Any]] = []
    for c in text_colors:
        if c["hex"] not in seen_hex:
            seen_hex.add(c["hex"])
            merged_colors.append(c)
    for c in visual_colors:
        if c["hex"] not in seen_hex and len(merged_colors) < 10:
            seen_hex.add(c["hex"])
            merged_colors.append(c)

    primary_colors = merged_colors[:5] if merged_colors else None
    secondary_colors = merged_colors[5:10] if len(merged_colors) > 5 else None

    # ── Typography ─────────────────────────────────────────────────────────────
    # PDF font metadata takes priority; fall back to heuristic text search
    if fonts_from_pdf:
        typography: list[dict[str, Any]] | None = fonts_from_pdf[:6]
    else:
        sections_tmp = _split_sections(text) if text else {}
        typo_text = sections_tmp.get("typography", "") or ""
        found = _extract_fonts(typo_text if typo_text else text)
        typography = found if found else None

    # ── Text sections ──────────────────────────────────────────────────────────
    if not text or not text.strip():
        kt = []
        if primary_colors:
            kt.append(
                "Renk paleti görselden çıkarıldı: "
                + ", ".join(c["hex"] for c in primary_colors[:3])
            )
        if typography:
            kt.append("PDF font metadata: " + ", ".join(f["family"] for f in typography[:3]))
        return {
            **empty,
            "primary_colors": primary_colors,
            "secondary_colors": secondary_colors,
            "typography": typography,
            "key_takeaways": kt if kt else None,
            "confidence_score": (
                min(len(primary_colors or []) * 5, 20) + min(len(typography or []) * 5, 15)
            ),
        }

    sections = _split_sections(text)

    general_text = sections.get("general", "") or text
    summary = _extract_summary(general_text) or _extract_summary(text)

    logo_text = sections.get("logo", "")
    logo_rules = _extract_rules(logo_text, 8) if logo_text else None

    visual_style = _extract_visual_style(sections, text)
    tone_of_voice = _extract_tone(sections, text)

    social_text = sections.get("social", "")
    social_notes = _extract_rules(social_text, 6) if social_text else None

    do_text = sections.get("do", "")
    do_rules = _extract_rules(do_text, 8) if do_text else None

    dont_text = sections.get("dont", "")
    dont_rules = _extract_rules(dont_text, 8) if dont_text else None

    # Key takeaways synthesized from all found data
    takeaways: list[str] = []
    if primary_colors:
        src = (
            " (tahmini)"
            if any(c.get("source") == "visual_extraction" for c in primary_colors)
            else ""
        )
        takeaways.append(
            f"Ana renk paleti{src}: " + ", ".join(c["hex"] for c in primary_colors[:3])
        )
    if typography:
        takeaways.append("Tipografi: " + ", ".join(f["family"] for f in typography[:3]))
    if logo_rules:
        takeaways.append(logo_rules[0][:120])
    if tone_of_voice and tone_of_voice.get("tags"):
        takeaways.append("İletişim tonu: " + ", ".join(tone_of_voice["tags"][:4]))
    if dont_rules:
        takeaways.append("Kaçınılacak: " + dont_rules[0][:120])
    if visual_style and visual_style.get("tags"):
        takeaways.append("Görsel stil: " + ", ".join(visual_style["tags"][:3]))

    key_takeaways = takeaways[:5] if takeaways else None

    # Confidence score (0–95)
    score = 0
    has_text_colors = any(c.get("source") != "visual_extraction" for c in (primary_colors or []))
    if has_text_colors and primary_colors:
        score += min(len(primary_colors) * 8, 25)
    elif primary_colors:
        score += min(len(primary_colors) * 4, 15)  # visual = lower confidence
    if typography:
        meta_fonts = [f for f in typography if f.get("source") == "pdf_font_metadata"]
        score += min(len(meta_fonts) * 8 + len(typography) * 3, 20)
    if summary:
        score += 15
    if logo_rules:
        score += 10
    if tone_of_voice:
        score += 10
    if do_rules or dont_rules:
        score += 5
    if visual_style:
        score += 5
    score = min(score, 95)

    return {
        "summary": summary,
        "primary_colors": primary_colors,
        "secondary_colors": secondary_colors,
        "typography": typography,
        "logo_rules": logo_rules,
        "visual_style": visual_style,
        "tone_of_voice": tone_of_voice,
        "social_media_notes": social_notes,
        "do_rules": do_rules,
        "dont_rules": dont_rules,
        "key_takeaways": key_takeaways,
        "confidence_score": score,
    }


def _profile_snapshot(profile: BrandIdentityProfile) -> dict[str, Any]:
    return {
        "status": profile.status,
        "summary": profile.summary,
        "primary_colors": profile.primary_colors,
        "secondary_colors": profile.secondary_colors,
        "typography": profile.typography,
        "logo_rules": profile.logo_rules,
        "visual_style": profile.visual_style,
        "tone_of_voice": profile.tone_of_voice,
        "social_media_notes": profile.social_media_notes,
        "do_rules": profile.do_rules,
        "dont_rules": profile.dont_rules,
        "key_takeaways": profile.key_takeaways,
    }


class BrandIdentityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._storage = get_storage_backend()

    async def _require_brand(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        *,
        platform_admin: bool = False,
    ) -> Brand:
        stmt = select(Brand).where(Brand.id == brand_id, Brand.deleted_at.is_(None))
        if not platform_admin and agency_id is not None:
            stmt = stmt.where(Brand.agency_id == agency_id)
        result = await self.db.execute(stmt)
        brand = result.scalar_one_or_none()
        if not brand:
            raise HTTPException(status_code=404, detail="Marka bulunamadı")
        if not platform_admin and agency_id is not None and brand.agency_id != agency_id:
            raise HTTPException(status_code=403, detail="Bu markaya erişim yetkiniz yok")
        return brand

    async def get_overview(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        *,
        platform_admin: bool = False,
    ) -> BrandIdentityOverview:
        await self._require_brand(brand_id, agency_id, platform_admin=platform_admin)
        profile = await self._active_profile(brand_id)
        docs = await self._list_documents(brand_id)
        return BrandIdentityOverview(
            profile=BrandIdentityProfileRead.model_validate(profile) if profile else None,
            documents=[BrandIdentityDocumentRead.model_validate(d) for d in docs],
        )

    async def upload_document(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        file: UploadFile,
        user: User,
    ) -> BrandIdentityDocumentRead:
        await self._require_brand(brand_id, agency_id)
        content_type = file.content_type or ""
        if content_type not in _ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=422,
                detail="Yalnızca PDF dosyası yüklenebilir. Dosya türü: application/pdf",
            )
        data = await file.read()
        if len(data) > _MAX_PDF_BYTES:
            raise HTTPException(
                status_code=422,
                detail="PDF dosyası 50 MB'ı aşamaz",
            )
        original_name = file.filename or "identity.pdf"
        safe_name = normalize_filename(original_name)
        storage_key = f"brand-identity/{brand_id}/{safe_name}"
        await self._storage.save(data, storage_key)

        doc = BrandIdentityDocument(
            brand_id=brand_id,
            agency_id=agency_id,
            uploaded_by_id=user.id,
            file_name=original_name[:500],
            storage_key=storage_key,
            file_size=len(data),
            content_type=content_type,
            status="uploaded",
        )
        self.db.add(doc)
        await self.db.flush()

        doc.status = "processing"
        try:
            pdf_result = _extract_pdf_data(data)
            doc.page_count = pdf_result["page_count"] or None
            doc.extraction_method = pdf_result["method"]
            doc.extraction_debug_json = pdf_result["debug"]

            if pdf_result.get("missing_deps"):
                doc.status = "failed"
                doc.analysis_error = (
                    "PDF analiz kütüphaneleri yüklü değil: PyMuPDF ve pypdf eksik. "
                    "Backend ortamında kurulum gerekli."
                )
            else:
                text = pdf_result["text"]
                is_image_based = pdf_result["is_image_based"]
                doc.extracted_text = text[:50000] if text else None
                dna = _build_dna_from_extraction(
                    text,
                    fonts_from_pdf=pdf_result["fonts_from_pdf"],
                    visual_colors=pdf_result["visual_colors"],
                )
                doc.status = "needs_review" if is_image_based else "analyzed"

                profile = await self._active_profile(brand_id)
                if profile is None:
                    profile_status = "needs_review" if is_image_based else "ai_generated"
                    profile = BrandIdentityProfile(
                        brand_id=brand_id,
                        agency_id=agency_id,
                        source_document_id=doc.id,
                        status=profile_status,
                        is_active=True,
                        **{k: v for k, v in dna.items()},
                    )
                    self.db.add(profile)
                else:
                    profile.source_document_id = doc.id
                    profile.status = "needs_review" if is_image_based else "ai_generated"
                    for key, val in dna.items():
                        setattr(profile, key, val)
                    profile.approved_by_id = None
                    profile.approved_by_name = None
                    profile.approved_at = None

        except Exception as exc:
            doc.status = "failed"
            doc.analysis_error = str(exc)[:500]

        await self.db.commit()
        await self.db.refresh(doc)
        return BrandIdentityDocumentRead.model_validate(doc)

    async def analyze_document(
        self,
        brand_id: uuid.UUID,
        document_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        user: User,
    ) -> BrandIdentityDocumentRead:
        await self._require_brand(brand_id, agency_id)
        doc = await self._get_document(document_id, brand_id)

        doc.status = "processing"
        doc.analysis_error = None
        await self.db.flush()

        storage_path = self._storage.get_path(doc.storage_key)
        try:
            with open(storage_path, "rb") as f:
                data = f.read()
            pdf_result = _extract_pdf_data(data)
            doc.page_count = pdf_result["page_count"] or None
            doc.extraction_method = pdf_result["method"]
            doc.extraction_debug_json = pdf_result["debug"]

            if pdf_result.get("missing_deps"):
                doc.status = "failed"
                doc.analysis_error = (
                    "PDF analiz kütüphaneleri yüklü değil: PyMuPDF ve pypdf eksik. "
                    "Backend ortamında kurulum gerekli."
                )
            else:
                text = pdf_result["text"]
                is_image_based = pdf_result["is_image_based"]
                doc.extracted_text = text[:50000] if text else None
                dna = _build_dna_from_extraction(
                    text,
                    fonts_from_pdf=pdf_result["fonts_from_pdf"],
                    visual_colors=pdf_result["visual_colors"],
                )
                doc.status = "needs_review" if is_image_based else "analyzed"

                profile = await self._active_profile(brand_id)
                profile_status = "needs_review" if is_image_based else "ai_generated"
                if profile is None:
                    profile = BrandIdentityProfile(
                        brand_id=brand_id,
                        agency_id=agency_id,
                        source_document_id=doc.id,
                        status=profile_status,
                        is_active=True,
                        **{k: v for k, v in dna.items()},
                    )
                    self.db.add(profile)
                else:
                    before = _profile_snapshot(profile)
                    profile.source_document_id = doc.id
                    profile.status = profile_status
                    for key, val in dna.items():
                        setattr(profile, key, val)
                    profile.approved_by_id = None
                    profile.approved_by_name = None
                    profile.approved_at = None
                    self.db.add(
                        BrandIdentityRevision(
                            profile_id=profile.id,
                            changed_by_id=user.id,
                            changed_by_name=user.full_name,
                            before_json=before,
                            after_json=_profile_snapshot(profile),
                            change_note="Otomatik analiz tekrar çalıştırıldı",
                        )
                    )
        except Exception as exc:
            doc.status = "failed"
            doc.analysis_error = str(exc)[:500]

        await self.db.commit()
        await self.db.refresh(doc)
        return BrandIdentityDocumentRead.model_validate(doc)

    async def list_documents(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID | None,
    ) -> list[BrandIdentityDocumentRead]:
        await self._require_brand(brand_id, agency_id)
        docs = await self._list_documents(brand_id)
        return [BrandIdentityDocumentRead.model_validate(d) for d in docs]

    async def update_profile(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        data: BrandIdentityProfileUpdate,
        user: User,
    ) -> BrandIdentityProfileRead:
        await self._require_brand(brand_id, agency_id)
        profile = await self._active_profile(brand_id)
        if profile is None:
            profile = BrandIdentityProfile(
                brand_id=brand_id,
                agency_id=agency_id,
                status="draft",
                is_active=True,
            )
            self.db.add(profile)
            await self.db.flush()

        before = _profile_snapshot(profile)
        update_fields = data.model_dump(exclude={"change_note"}, exclude_unset=True)
        for key, val in update_fields.items():
            setattr(profile, key, val)

        if profile.status == "approved":
            profile.status = "reviewed"
            profile.approved_by_id = None
            profile.approved_by_name = None
            profile.approved_at = None

        self.db.add(
            BrandIdentityRevision(
                profile_id=profile.id,
                changed_by_id=user.id,
                changed_by_name=user.full_name,
                before_json=before,
                after_json=_profile_snapshot(profile),
                change_note=data.change_note,
            )
        )
        await self.db.commit()
        await self.db.refresh(profile)
        return BrandIdentityProfileRead.model_validate(profile)

    async def approve_profile(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        user: User,
    ) -> BrandIdentityProfileRead:
        await self._require_brand(brand_id, agency_id)
        profile = await self._active_profile(brand_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Marka DNA profili bulunamadı")

        before = _profile_snapshot(profile)
        profile.status = "approved"
        profile.approved_by_id = user.id
        profile.approved_by_name = user.full_name
        profile.approved_at = datetime.now(UTC)

        self.db.add(
            BrandIdentityRevision(
                profile_id=profile.id,
                changed_by_id=user.id,
                changed_by_name=user.full_name,
                before_json=before,
                after_json=_profile_snapshot(profile),
                change_note="Marka DNA profili onaylandı",
            )
        )
        await self.db.commit()
        await self.db.refresh(profile)
        return BrandIdentityProfileRead.model_validate(profile)

    async def list_revisions(
        self,
        brand_id: uuid.UUID,
        agency_id: uuid.UUID | None,
    ) -> list[BrandIdentityRevisionRead]:
        await self._require_brand(brand_id, agency_id)
        profile = await self._active_profile(brand_id)
        if profile is None:
            return []
        result = await self.db.execute(
            select(BrandIdentityRevision)
            .where(BrandIdentityRevision.profile_id == profile.id)
            .order_by(BrandIdentityRevision.created_at.desc())
        )
        revisions = result.scalars().all()
        return [BrandIdentityRevisionRead.model_validate(r) for r in revisions]

    async def get_dna_summary(
        self,
        brand_id: uuid.UUID,
    ) -> BrandDNASummary:
        """Lightweight summary for brief/deliverable panels."""
        profile = await self._active_profile(brand_id)
        if profile is None:
            return BrandDNASummary(
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
        return BrandDNASummary(
            profile_id=profile.id,
            status=profile.status,
            summary=profile.summary,
            primary_colors=profile.primary_colors,
            typography=profile.typography,
            tone_of_voice=profile.tone_of_voice,
            key_takeaways=profile.key_takeaways,
            dont_rules=profile.dont_rules,
            approved_by_name=profile.approved_by_name,
            approved_at=profile.approved_at,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _active_profile(self, brand_id: uuid.UUID) -> BrandIdentityProfile | None:
        result = await self.db.execute(
            select(BrandIdentityProfile).where(
                BrandIdentityProfile.brand_id == brand_id,
                BrandIdentityProfile.is_active.is_(True),
                BrandIdentityProfile.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    async def _list_documents(self, brand_id: uuid.UUID) -> list[BrandIdentityDocument]:
        result = await self.db.execute(
            select(BrandIdentityDocument)
            .where(
                BrandIdentityDocument.brand_id == brand_id,
                BrandIdentityDocument.deleted_at.is_(None),
            )
            .order_by(BrandIdentityDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_document(
        self, document_id: uuid.UUID, brand_id: uuid.UUID
    ) -> BrandIdentityDocument:
        result = await self.db.execute(
            select(BrandIdentityDocument).where(
                BrandIdentityDocument.id == document_id,
                BrandIdentityDocument.brand_id == brand_id,
                BrandIdentityDocument.deleted_at.is_(None),
            )
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Belge bulunamadı")
        return doc
