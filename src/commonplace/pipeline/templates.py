"""Templater-style rendering.

Templates use `<% name %>` placeholders, the same delimiters as the Templater
plugin, so they read naturally in Obsidian. Commonplace renders them itself;
they are not executed by Templater. In the frontmatter, values are written as
YAML (JSON flow style, which is valid YAML), so lists of wikilinks become
proper Obsidian list properties. In the body, values are inserted as text."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

PLACEHOLDER = re.compile(r"<%[-_]?\s*([\w.]+)\s*[-_]?%>")
BUNDLED = Path(__file__).resolve().parents[3] / "templates"

TEMPLATE_FOR_KIND = {
    "meeting": "Meeting",
    "person": "Person",
    "company": "Company",
    "project": "Project",
    "decision": "Decision",
    "daily": "Daily",
}


class TemplateError(ValueError):
    pass


class Templates:
    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder or BUNDLED
        self._cache: dict[str, str] = {}

    def get(self, kind: str) -> str:
        name = TEMPLATE_FOR_KIND.get(kind, "Note")
        if name not in self._cache:
            path = self.folder / f"{name}.md"
            if not path.exists():
                path = BUNDLED / f"{name}.md"
            self._cache[name] = path.read_text()
        return self._cache[name]

    def render(self, kind: str, ctx: dict[str, Any]) -> tuple[dict[str, Any], str]:
        return render(self.get(kind), ctx)


def render(template: str, ctx: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Return (frontmatter dict, body text)."""
    if not template.startswith("---\n"):
        raise TemplateError("template must start with YAML frontmatter")
    end = template.find("\n---\n", 4)
    if end == -1:
        raise TemplateError("unterminated frontmatter")
    fm_src, body_src = template[4:end], template[end + 5:]

    def fm_value(m: re.Match[str]) -> str:
        return json.dumps(_lookup(ctx, m.group(1)), ensure_ascii=False, default=str)

    def body_value(m: re.Match[str]) -> str:
        value = _lookup(ctx, m.group(1))
        return "" if value is None else str(value)

    fm = yaml.safe_load(PLACEHOLDER.sub(fm_value, fm_src)) or {}
    body = PLACEHOLDER.sub(body_value, body_src)
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    fm = {k: v for k, v in fm.items() if v not in (None, "", [])}
    return fm, body


def _lookup(ctx: dict[str, Any], dotted: str) -> Any:
    value: Any = ctx
    for part in dotted.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
    return value
