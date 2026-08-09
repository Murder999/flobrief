"""InvoicePdfService: renders a `ClientInvoice` to PDF bytes, imitating the
`_FloBriefPDF` pattern in `report_export_service.py` (own copy, not a shared
import, per that file's own precedent of one PDF builder per document type).

Legal-wording constraint (plan §1/§3/§12): the header must clearly say
"Fatura Taslağı" (draft_invoice) or "Proforma Fatura" (proforma) — never any
wording implying a legally-valid Turkish e-invoice ("e-Fatura").

Client-facing document constraint (plan §3/§12): this PDF must NEVER render
`cost_rate_snapshot_cents` or any other internal-cost/margin figure — only
client-facing billing fields (description/qty/unit/price/tax/discount/
subtotal/total) are read from each line.
"""

from __future__ import annotations

import os
import platform
from datetime import date, datetime

from fpdf import FPDF  # type: ignore[import-untyped]

from app.models.client_invoice import ClientInvoice, ClientInvoiceLine
from app.models.enums import ClientInvoiceDocumentType

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


def _detect_unicode_font() -> str | None:
    candidates: list[str] = []
    if platform.system() == "Windows":
        win_fonts = r"C:\Windows\Fonts"
        candidates = [
            os.path.join(win_fonts, "arial.ttf"),
            os.path.join(win_fonts, "calibri.ttf"),
        ]
    elif platform.system() == "Darwin":
        candidates = ["/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"]
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
    if platform.system() == "Darwin":
        return None
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return p if os.path.exists(p) else None


_UNICODE_FONT: str | None = _detect_unicode_font()
_UNICODE_FONT_BOLD: str | None = _detect_unicode_font_bold()
_FONT_REGULAR = "MainFont" if _UNICODE_FONT else "Helvetica"
_FONT_BOLD = (
    "MainFontBold" if _UNICODE_FONT_BOLD else ("MainFont" if _UNICODE_FONT else "Helvetica")
)


def _s(text: str) -> str:
    if _UNICODE_FONT:
        return text
    return text.translate(_TR_TABLE)


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "-"
    return d.strftime("%d.%m.%Y")


def _fmt_money(cents: int, currency: str) -> str:
    return f"{cents / 100:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")


_ACCENT = (99, 102, 241)
_TEXT = (24, 24, 32)
_MUTED = (110, 110, 130)
_BORDER = (222, 222, 232)
_WHITE = (255, 255, 255)

_DOCUMENT_TITLES = {
    ClientInvoiceDocumentType.DRAFT_INVOICE.value: "FATURA TASLAĞI",
    ClientInvoiceDocumentType.PROFORMA.value: "PROFORMA FATURA",
}


class _InvoicePDF(FPDF):
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
        self.cell(
            0,
            6,
            _s(
                "Bu belge resmi bir e-Fatura degildir; yalnizca bilgilendirme "
                f"amaclidir. Sayfa {self.page_no()}"
            ),
            align="C",
        )


class InvoicePdfService:
    @staticmethod
    def build_pdf_bytes(
        invoice: ClientInvoice,
        lines: list[ClientInvoiceLine],
        agency_name: str,
        brand_name: str,
    ) -> bytes:
        pdf = _InvoicePDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        # ── Header band ──────────────────────────────────────────────────────
        pdf.set_fill_color(*_ACCENT)
        pdf.rect(0, 0, 210, 24, "F")
        pdf.set_xy(14, 7)
        pdf.set_font(_FONT_BOLD, "", 16)
        pdf.set_text_color(*_WHITE)
        title = _DOCUMENT_TITLES.get(invoice.document_type, "FATURA TASLAĞI")
        pdf.cell(0, 10, _s(title), ln=True)
        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 10)
        pdf.cell(0, 6, _s(f"Fatura No: {invoice.invoice_number}"), ln=True)

        pdf.set_y(30)

        # ── Agency / brand columns ──────────────────────────────────────────
        col_w = 90
        y0 = pdf.get_y()
        pdf.set_xy(14, y0)
        pdf.set_font(_FONT_BOLD, "", 10)
        pdf.set_text_color(*_TEXT)
        pdf.cell(col_w, 6, _s("Gonderen (Ajans)"), ln=False)
        pdf.set_xy(14 + col_w, y0)
        pdf.cell(col_w, 6, _s("Alici (Marka)"), ln=True)

        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(col_w, 6, _s(agency_name), ln=False)
        pdf.set_x(14 + col_w)
        pdf.cell(col_w, 6, _s(brand_name), ln=True)

        if invoice.billing_contact_name:
            pdf.set_x(14 + col_w)
            pdf.cell(col_w, 6, _s(invoice.billing_contact_name), ln=True)
        if invoice.billing_contact_email:
            pdf.set_x(14 + col_w)
            pdf.cell(col_w, 6, _s(invoice.billing_contact_email), ln=True)
        if invoice.tax_office or invoice.tax_number:
            pdf.set_x(14 + col_w)
            pdf.cell(
                col_w,
                6,
                _s(f"{invoice.tax_office or ''} {invoice.tax_number or ''}".strip()),
                ln=True,
            )

        pdf.ln(4)

        # ── Dates row ────────────────────────────────────────────────────────
        y = pdf.get_y()
        pdf.set_draw_color(*_BORDER)
        pdf.line(14, y, 196, y)
        pdf.ln(3)
        date_rows = [
            ("Fatura Tarihi", _fmt_date(invoice.issue_date)),
            ("Vade Tarihi", _fmt_date(invoice.due_date)),
            (
                "Hizmet Donemi",
                _s(
                    f"{_fmt_date(invoice.service_period_start)} - "
                    f"{_fmt_date(invoice.service_period_end)}"
                )
                if invoice.service_period_start
                else "-",
            ),
            ("Para Birimi", invoice.currency),
        ]
        for label, value in date_rows:
            pdf.set_x(14)
            pdf.set_font(_FONT_REGULAR, "", 9)
            pdf.set_text_color(*_MUTED)
            pdf.cell(40, 6, _s(label), ln=False)
            pdf.set_font(_FONT_BOLD, "", 9)
            pdf.set_text_color(*_TEXT)
            pdf.cell(0, 6, str(value), ln=True)

        pdf.ln(4)

        # ── Line items table ─────────────────────────────────────────────────
        pdf.set_fill_color(*_ACCENT)
        pdf.set_text_color(*_WHITE)
        pdf.set_font(_FONT_BOLD, "", 8)
        headers = [
            ("Aciklama", 62),
            ("Miktar", 18),
            ("Birim", 18),
            ("B.Fiyat", 24),
            ("Indirim", 20),
            ("KDV%", 14),
            ("Toplam", 26),
        ]
        pdf.set_x(14)
        for label, w in headers:
            pdf.cell(w, 8, _s(label), border=0, fill=True, align="L")
        pdf.ln(8)

        pdf.set_font(_FONT_REGULAR, "", 8)
        pdf.set_text_color(*_TEXT)
        for idx, line in enumerate(lines):
            if pdf.get_y() > 260:
                pdf.add_page()
            fill = idx % 2 == 1
            if fill:
                pdf.set_fill_color(245, 245, 250)
            pdf.set_x(14)
            desc = (line.description or "")[:60]
            pdf.cell(62, 7, _s(desc), fill=fill)
            pdf.cell(18, 7, f"{line.quantity:g}", fill=fill)
            pdf.cell(18, 7, _s(line.unit), fill=fill)
            pdf.cell(24, 7, _fmt_money(line.unit_price_cents, invoice.currency), fill=fill)
            pdf.cell(20, 7, _fmt_money(line.discount_cents, invoice.currency), fill=fill)
            pdf.cell(14, 7, f"%{line.tax_rate_bps / 100:g}", fill=fill)
            pdf.cell(26, 7, _fmt_money(line.total_cents, invoice.currency), fill=fill, ln=True)

        pdf.ln(3)
        y = pdf.get_y()
        pdf.set_draw_color(*_BORDER)
        pdf.line(14, y, 196, y)
        pdf.ln(3)

        # ── Totals ───────────────────────────────────────────────────────────
        totals = [
            ("Ara Toplam", invoice.subtotal_cents),
            ("Indirim", -invoice.discount_cents),
            ("KDV", invoice.tax_cents),
        ]
        for label, cents in totals:
            pdf.set_x(140)
            pdf.set_font(_FONT_REGULAR, "", 9)
            pdf.set_text_color(*_MUTED)
            pdf.cell(30, 6, _s(label), ln=False)
            pdf.set_font(_FONT_BOLD, "", 9)
            pdf.set_text_color(*_TEXT)
            pdf.cell(26, 6, _fmt_money(cents, invoice.currency), ln=True, align="R")

        pdf.set_x(140)
        pdf.set_font(_FONT_BOLD, "", 11)
        pdf.set_text_color(*_ACCENT)
        pdf.cell(30, 8, _s("GENEL TOPLAM"), ln=False)
        pdf.cell(26, 8, _fmt_money(invoice.total_cents, invoice.currency), ln=True, align="R")

        pdf.ln(6)
        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 5, _s(f"Odeme vadesi: {invoice.due_date.strftime('%d.%m.%Y')}"), ln=True)

        if invoice.notes:
            pdf.ln(3)
            pdf.set_x(14)
            pdf.set_font(_FONT_BOLD, "", 9)
            pdf.set_text_color(*_TEXT)
            pdf.cell(0, 6, _s("Notlar"), ln=True)
            pdf.set_x(14)
            pdf.set_font(_FONT_REGULAR, "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(0, 5, _s(invoice.notes))

        pdf.ln(6)
        pdf.set_x(14)
        pdf.set_font(_FONT_REGULAR, "", 7)
        pdf.set_text_color(*_MUTED)
        now_str = datetime.utcnow().strftime("%d.%m.%Y %H:%M")
        pdf.cell(
            0,
            5,
            _s(f"Bu {title.lower()} {now_str} UTC'de Flobrief tarafindan olusturuldu."),
        )

        return bytes(pdf.output())
