from __future__ import annotations

import os
import platform
from datetime import date, datetime

from fpdf import FPDF  # type: ignore[import-untyped]

from app.models.report import Report, ReportSnapshot

# ── Turkish char transliteration for Latin-1 core fonts ──────────────────────
_TR_TABLE = str.maketrans(
    {
        "ş": "s",
        "Ş": "S",
        "ğ": "g",
        "Ğ": "G",
        "ı": "i",
        "İ": "I",
        "…": "...",
        "—": "--",
    }
)


def _s(text: str) -> str:
    """Ensure text is renderable by Latin-1 core fonts.

    ç/ö/ü/Ç/Ö/Ü are in Latin-1 and pass through unchanged.
    ş/Ş/ğ/Ğ/ı/İ and Unicode punctuation are transliterated.
    If a Unicode TTF is configured, this function is bypassed.
    """
    if _UNICODE_FONT:
        return text
    return text.translate(_TR_TABLE)


def _detect_unicode_font() -> str | None:
    """Return path to a system Unicode TTF font, or None if unavailable."""
    candidates: list[str] = []
    if platform.system() == "Windows":
        win_fonts = r"C:\Windows\Fonts"
        candidates = [
            os.path.join(win_fonts, "arial.ttf"),
            os.path.join(win_fonts, "calibri.ttf"),
        ]
    elif platform.system() == "Darwin":
        candidates = [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    return next((p for p in candidates if os.path.exists(p)), None)


def _detect_unicode_font_bold() -> str | None:
    if platform.system() == "Windows":
        p = r"C:\Windows\Fonts\arialbd.ttf"
        return p if os.path.exists(p) else None
    elif platform.system() == "Darwin":
        return None
    else:
        p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        return p if os.path.exists(p) else None


_UNICODE_FONT: str | None = _detect_unicode_font()
_UNICODE_FONT_BOLD: str | None = _detect_unicode_font_bold()

# ── PostPiloter brand palette (dark-UI matching hex approximations for PDF) ───
_BG = (17, 17, 24)  # #111118 surface
_ACCENT = (99, 102, 241)  # #6366F1 indigo
_TEXT = (240, 240, 248)  # #F0F0F8
_MUTED = (136, 136, 168)  # #8888A8
_SUCCESS = (16, 185, 129)  # #10B981
_WARNING = (245, 158, 11)  # #F59E0B
_BORDER = (42, 42, 58)  # #2A2A3A
_WHITE = (255, 255, 255)


def _fmt_date(d: date | str) -> str:
    if isinstance(d, str):
        return d
    return d.strftime("%d %B %Y")


def _fmt_num(n: int | float | None) -> str:
    if n is None:
        return "-"
    if isinstance(n, float):
        return f"{n:.1f}"
    return str(n)


_FONT_REGULAR = "MainFont" if _UNICODE_FONT else "Helvetica"
_FONT_BOLD = (
    "MainFontBold" if _UNICODE_FONT_BOLD else ("MainFont" if _UNICODE_FONT else "Helvetica")
)


class _FloBriefPDF(FPDF):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        if _UNICODE_FONT:
            self.add_font(_FONT_REGULAR, style="", fname=_UNICODE_FONT)
        if _UNICODE_FONT_BOLD and _UNICODE_FONT_BOLD != _UNICODE_FONT:
            self.add_font(_FONT_BOLD, style="", fname=_UNICODE_FONT_BOLD)

    def header(self) -> None:
        pass

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(_FONT_REGULAR, "", 8)
        self.set_text_color(*_MUTED)
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        self.cell(
            0,
            6,
            f"PostPiloter - {date_str}     Sayfa {self.page_no()}",
            align="C",
        )


class ReportExportService:
    @staticmethod
    def build_pdf_bytes(report: Report, snapshot: ReportSnapshot) -> bytes:
        m = snapshot.metrics
        pdf = _FloBriefPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=16)
        pdf.add_page()

        # ── Background fill ────────────────────────────────────────────────────
        pdf.set_fill_color(*_BG)
        pdf.rect(0, 0, 210, 297, "F")

        # ── Header strip ───────────────────────────────────────────────────────
        pdf.set_fill_color(*_ACCENT)
        pdf.rect(0, 0, 210, 20, "F")

        pdf.set_xy(14, 6)
        pdf.set_font(_FONT_BOLD, "", 14)
        pdf.set_text_color(*_WHITE)
        pdf.cell(0, 8, "PostPiloter", ln=False)

        pdf.set_xy(14, 24)
        pdf.set_font(_FONT_BOLD, "", 20)
        pdf.set_text_color(*_TEXT)
        pdf.cell(0, 10, _s(report.title), ln=True)

        period_str = f"{_fmt_date(report.period_start)}  --  {_fmt_date(report.period_end)}"
        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 10)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 7, _s(period_str), ln=True)

        report_type_labels = {
            "monthly_brand": _s("Aylık Marka Raporu"),
            "agency_overview": _s("Ajans Genel Ozeti"),
            "campaign_summary": _s("Kampanya Ozeti"),
        }
        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            0,
            6,
            _s(report_type_labels.get(report.report_type, report.report_type)),
            ln=True,
        )
        pdf.ln(4)

        # ── KPI card row (4 cards) ─────────────────────────────────────────────
        kpis = [
            (_s("Brief Olusturuldu"), _fmt_num(m.get("created_briefs_count")), _ACCENT),
            (_s("Onaylanan Brief"), _fmt_num(m.get("approved_briefs_count")), _SUCCESS),
            (_s("Revizyon Istendi"), _fmt_num(m.get("revision_requested_count")), _WARNING),
            (_s("Yayinlanan Icerik"), _fmt_num(m.get("published_calendar_items_count")), _SUCCESS),
        ]
        card_w, card_h = 43, 26
        col_gap = 3.6
        start_x = 14.0
        y = pdf.get_y()

        for i, (label, value, color) in enumerate(kpis):
            x = start_x + i * (card_w + col_gap)
            pdf.set_fill_color(26, 26, 36)
            pdf.set_draw_color(*_BORDER)
            pdf.rect(x, y, card_w, card_h, "FD")
            pdf.set_fill_color(*color)
            pdf.rect(x, y, card_w, 2, "F")
            pdf.set_xy(x + 3, y + 5)
            pdf.set_font(_FONT_BOLD, "", 16)
            pdf.set_text_color(*_TEXT)
            pdf.cell(card_w - 6, 10, value, ln=False)
            pdf.set_xy(x + 3, y + 16)
            pdf.set_font(_FONT_REGULAR, "", 7)
            pdf.set_text_color(*_MUTED)
            pdf.cell(card_w - 6, 5, label, ln=False)

        pdf.set_y(y + card_h + 8)

        # ── Brief Performance Section ──────────────────────────────────────────
        ReportExportService._section_title(pdf, _s("Brief Performansi"))

        rows = [
            (_s("Olusturulan Brief"), m.get("created_briefs_count", 0)),
            (_s("Onaylanan Brief"), m.get("approved_briefs_count", 0)),
            (_s("Revizyon Istenen"), m.get("revision_requested_count", 0)),
            (_s("Bekleyen Onay"), m.get("pending_approvals_count", 0)),
        ]
        avg_h = m.get("average_approval_time_hours")
        if avg_h is not None:
            rows.append((_s("Ort. Onay Suresi"), f"{avg_h:.1f} saat"))  # type: ignore[arg-type]

        for label, val in rows:
            ReportExportService._kv_row(pdf, label, str(val))

        pdf.ln(4)

        # ── Calendar Section ───────────────────────────────────────────────────
        ReportExportService._section_title(pdf, _s("Icerik Takvimi"))
        rows2 = [
            (_s("Yayinlanan Icerik"), m.get("published_calendar_items_count", 0)),
            (_s("Planlanan Icerik"), m.get("planned_calendar_items_count", 0)),
        ]
        for label, val in rows2:
            ReportExportService._kv_row(pdf, label, str(val))

        pdf.ln(3)

        # ── Platform Distribution bar chart ────────────────────────────────────
        platforms: dict = m.get("platform_distribution", {})
        if platforms:
            ReportExportService._section_title(pdf, _s("Platform Dagilimi"))
            total_items = sum(platforms.values()) or 1
            bar_max_w = 120.0
            bar_h = 7.0
            bar_gap = 2.5
            pcolors = {
                "instagram": (225, 48, 108),
                "facebook": (24, 119, 242),
                "tiktok": (105, 201, 208),
                "linkedin": (10, 102, 194),
                "youtube": (255, 0, 0),
                "x": (29, 155, 240),
            }
            sorted_platforms = sorted(platforms.items(), key=lambda x: x[1], reverse=True)[:6]
            y = pdf.get_y()
            for plat, cnt in sorted_platforms:
                ratio = cnt / total_items
                bar_w = max(4.0, ratio * bar_max_w)
                color = pcolors.get(plat.lower(), _ACCENT)
                pdf.set_xy(14, y)
                pdf.set_font(_FONT_REGULAR, "", 8)
                pdf.set_text_color(*_MUTED)
                pdf.cell(30, bar_h, plat.capitalize(), align="L")
                pdf.set_fill_color(*color)
                pdf.rect(45, y + 1, bar_w, bar_h - 2, "F")
                pdf.set_xy(45 + bar_w + 2, y)
                pdf.set_font(_FONT_BOLD, "", 8)
                pdf.set_text_color(*_TEXT)
                pdf.cell(20, bar_h, str(cnt), align="L")
                y += bar_h + bar_gap
            pdf.set_y(y + 3)

        # ── Status Distribution ────────────────────────────────────────────────
        cal_status: dict = m.get("calendar_status_distribution", {})
        if cal_status:
            ReportExportService._section_title(pdf, _s("Icerik Durum Ozeti"))
            status_labels = {
                "planned": "Planlandi",
                "in_design": "Tasarimda",
                "waiting_approval": "Onay Bekliyor",
                "approved": "Onaylandi",
                "scheduled": "Zamanlandi",
                "published": "Yayinlandi",
                "cancelled": "Iptal",
            }
            for status, cnt in sorted(cal_status.items(), key=lambda x: x[1], reverse=True):
                ReportExportService._kv_row(pdf, status_labels.get(status, status), str(cnt))

        pdf.ln(4)

        # ── Most Revised Briefs ────────────────────────────────────────────────
        revised: list = m.get("most_revised_briefs", [])
        if revised:
            ReportExportService._section_title(pdf, _s("En Cok Revizyon Istenen Briefler"))
            for entry in revised[:5]:
                rev_cnt = entry.get("revision_count", 0)
                brief_id = str(entry.get("brief_id", ""))[:8]
                ReportExportService._kv_row(pdf, f"Brief #{brief_id}...", f"{rev_cnt} revizyon")

        # ── Generated timestamp ────────────────────────────────────────────────
        pdf.ln(8)
        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 8)
        pdf.set_text_color(*_MUTED)
        now_str = datetime.utcnow().strftime("%d.%m.%Y %H:%M")
        footer_line = f"Bu rapor {now_str} UTC'de PostPiloter tarafindan olusturuldu."
        pdf.cell(0, 5, footer_line)

        return bytes(pdf.output())

    @staticmethod
    def _section_title(pdf: _FloBriefPDF, title: str) -> None:
        pdf.set_x(14)
        pdf.set_font(_FONT_BOLD, "", 11)
        pdf.set_text_color(*_TEXT)
        pdf.cell(0, 8, title, ln=True)
        y = pdf.get_y()
        pdf.set_draw_color(*_ACCENT)
        pdf.set_line_width(0.4)
        pdf.line(14, y, 14 + 40, y)
        pdf.ln(3)

    @staticmethod
    def _kv_row(pdf: _FloBriefPDF, label: str, value: str) -> None:
        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(90, 7, label)
        pdf.set_font(_FONT_BOLD, "", 9)
        pdf.set_text_color(*_TEXT)
        pdf.cell(80, 7, value, ln=True)
