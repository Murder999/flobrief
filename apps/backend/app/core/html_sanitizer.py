"""Minimal safe-HTML sanitizer for brief rich text content.

Strips any tag/attribute not in the allowlist so that user-supplied HTML
cannot execute scripts or load external resources.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "h1",
        "h2",
        "h3",
        "h4",
        "ul",
        "ol",
        "li",
        "a",
        "blockquote",
        "pre",
        "code",
        "span",
        "div",
    }
)

_ALLOWED_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "title", "target", "rel"}),
    "span": frozenset({"class"}),
    "div": frozenset({"class"}),
    "p": frozenset({"class"}),
}

# Allowlist, not blocklist: browsers strip ASCII control characters (tabs,
# newlines, etc.) from *anywhere* in a URL before parsing its scheme, so a
# naive `value.startswith("javascript")` check can be bypassed with e.g.
# "java\tscript:alert(1)". Stripping control chars first and then requiring
# the scheme (if any) to be on an allowlist closes that regardless of how
# the dangerous scheme name is obfuscated.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")
_ALLOWED_URI_SCHEMES = frozenset({"http", "https", "mailto", "tel"})


def _is_safe_href(value: str) -> bool:
    cleaned = _CONTROL_CHARS_RE.sub("", value).strip()
    match = _SCHEME_RE.match(cleaned)
    if not match:
        return True  # no scheme — relative/fragment URL, safe
    return match.group(1).lower() in _ALLOWED_URI_SCHEMES


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._result: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _ALLOWED_TAGS:
            return
        allowed = _ALLOWED_ATTRS.get(tag, frozenset())
        safe_attrs = ""
        for name, value in attrs:
            if name not in allowed:
                continue
            if value is None:
                safe_attrs += f" {name}"
                continue
            if name == "href" and not _is_safe_href(value):
                continue
            v = value.replace('"', "&quot;")
            safe_attrs += f' {name}="{v}"'
        if tag == "a" and 'rel="' not in safe_attrs:
            safe_attrs += ' rel="noopener noreferrer"'
        self._result.append(f"<{tag}{safe_attrs}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _ALLOWED_TAGS:
            self._result.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self._result.append(data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def handle_entityref(self, name: str) -> None:
        self._result.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._result.append(f"&#{name};")

    def get_result(self) -> str:
        return "".join(self._result)


def sanitize_html(html: str | None) -> str | None:
    """Return sanitized HTML with only allowed tags/attrs, or None if input is None."""
    if html is None:
        return None
    sanitizer = _Sanitizer()
    sanitizer.feed(html)
    return sanitizer.get_result()
