from __future__ import annotations

from typing import Any

from .base import Connector, FetchResult, ReadOnlyHTTP, ReadOnlyViolation, Source
from .claude_code import ClaudeCodeConnector
from .folder import FolderConnector
from .meetings import MeetingExportsConnector
from .notion import NotionConnector
from .stubs import (
    FirefliesConnector, GmailConnector, GoogleCalendarConnector, GoogleDriveConnector,
    GranolaConnector, OutlookConnector, PostgresConnector, SharePointConnector, TeamsConnector,
)

REGISTRY: dict[str, type[Connector]] = {
    c.name: c
    for c in (
        ClaudeCodeConnector, FolderConnector, MeetingExportsConnector, NotionConnector,
        GmailConnector, GoogleDriveConnector, GoogleCalendarConnector,
        OutlookConnector, TeamsConnector, SharePointConnector,
        FirefliesConnector, GranolaConnector, PostgresConnector,
    )
}


def build(name: str, options: dict[str, Any]) -> Connector:
    """Build a connector from a config section. A section may set `type` to
    reuse a connector under another name, e.g. two folder connectors."""
    opts = {k: v for k, v in options.items() if k not in {"enabled", "type"}}
    kind = options.get("type", name)
    if kind not in REGISTRY:
        raise KeyError(f"unknown connector {kind!r}; known: {', '.join(sorted(REGISTRY))}")
    if kind == "folder":
        opts.setdefault("id_prefix", name)
    return REGISTRY[kind](**opts)


__all__ = ["Connector", "FetchResult", "ReadOnlyHTTP", "ReadOnlyViolation", "Source", "REGISTRY", "build"]
