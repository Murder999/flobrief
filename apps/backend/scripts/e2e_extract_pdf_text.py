"""Extracts text from a PDF file using pypdf, for e2e specs that need to
verify real content of a downloaded invoice PDF (e.g.
invoice-lifecycle-flow.spec.ts) without shipping a PDF-parsing dependency
into the frontend toolchain.

The backend's PDFs use a composite/Type0 font (an embedded Unicode TTF, so
Turkish characters render correctly) -- their content streams reference
glyph indices via a ToUnicode CMap rather than literal ASCII text bytes, so
a naive zlib-inflate + substring search on the raw PDF bytes cannot recover
the rendered words. pypdf already implements the CID/ToUnicode decoding
needed and is the same library `test_pdf_contains_draft_wording_and_never_
leaks_cost_rate`-style backend tests rely on, so this script reuses it
rather than re-implementing PDF text extraction in Node.

Usage:
  python e2e_extract_pdf_text.py <path-to-pdf>   -> prints extracted text to stdout
"""
from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: e2e_extract_pdf_text.py <path-to-pdf>", file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1])
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
