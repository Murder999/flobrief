"""Template renderer using stdlib string.Template with HTML escaping for XSS safety."""

from __future__ import annotations

import html
from string import Template


class TemplateRenderer:
    """Renders string.Template-syntax templates with HTML-escaped variable values.

    Template syntax: $variable_name or ${variable_name}.
    All variable values are HTML-escaped before substitution, preventing XSS in email bodies.
    """

    @staticmethod
    def render(template_str: str, variables: dict[str, str]) -> str:
        """Render a template string with HTML-escaped variable values."""
        escaped: dict[str, str] = {k: html.escape(str(v)) for k, v in variables.items()}
        return Template(template_str).safe_substitute(escaped)

    @staticmethod
    def render_plain(template_str: str, variables: dict[str, str]) -> str:
        """Render a template string without HTML escaping (for plain text bodies)."""
        return Template(template_str).safe_substitute(variables)
