"""CSV-injection guard (plan §12): invoice/payment exports include
free-text, user-entered descriptions (unlike `TimeReportService.export_csv`,
whose fields are never attacker-controlled leading characters). Any cell
whose first character is `=`, `+`, `-`, or `@` is treated by Excel/Sheets as
the start of a formula, so a value like `=cmd|'/c calc'!A1` could execute
when the exported file is later opened. Prefixing such cells with a literal
single quote neutralizes the formula interpretation while leaving the
visible text intact."""

from __future__ import annotations

_DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def escape_csv_cell(value: str) -> str:
    """Return `value` unchanged unless it starts with a formula-triggering
    character, in which case a leading `'` is prepended."""
    if value and value[0] in _DANGEROUS_PREFIXES:
        return f"'{value}"
    return value
