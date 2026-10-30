"""Helpers shared by connectors that read local files."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


def mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def changed_files(root: Path, patterns: Iterable[str], since: str | None,
                  exclude: Iterable[str] = ()) -> tuple[list[Path], str | None]:
    """Files under root matching patterns whose mtime is after `since`.
    Returns them sorted, plus the newest mtime seen (the next cursor)."""
    seen: set[Path] = set()
    for pattern in patterns:
        seen.update(p for p in root.glob(pattern) if p.is_file())
    excluded = {p for pattern in exclude for p in root.glob(pattern)}
    files = sorted(p for p in seen - excluded if not any(part.startswith(".") for part in p.relative_to(root).parts))
    cursor = since
    out = []
    for p in files:
        m = mtime_iso(p)
        if since is None or m > since:
            out.append(p)
        if cursor is None or m > cursor:
            cursor = m
    return out, cursor


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            try:
                meta = yaml.safe_load(text[4:end]) or {}
            except yaml.YAMLError:
                meta = {}
            if isinstance(meta, dict):
                return meta, text[end + 4:].lstrip("\n")
    return {}, text


def parse_dt(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif hasattr(value, "year") and not isinstance(value, str):  # date
        dt = datetime(value.year, value.month, value.day)
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    else:
        return fallback
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


FILENAME_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def date_from_name(path: Path, fallback: datetime) -> datetime:
    """Many exports start the filename with the date; prefer it over mtime."""
    m = FILENAME_DATE.match(path.name)
    return parse_dt(m.group(1), fallback) if m else fallback
