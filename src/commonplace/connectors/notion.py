"""Notion, via the official REST API, read-only.

Auth: create an internal integration at https://www.notion.so/my-integrations
with only the "Read content" capability, share the pages you want synced with
it, and set NOTION_TOKEN (env or keychain). See docs/connectors/notion.md."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..models import Participant, Record
from ..secrets import get_secret
from ._files import parse_dt
from .base import Connector, FetchResult, ReadOnlyHTTP, Source, Transport

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
MAX_DEPTH = 3


def fixture_transport(root: Path) -> Transport:
    """Serves recorded API responses from disk. Used by the offline demo and
    tests, so they exercise the same fetch and normalize code as a live sync."""

    def send(method: str, url: str, headers: dict[str, str], body: bytes | None) -> Any:
        path = urlparse(url).path.removeprefix("/v1/")
        if path == "search":
            return json.loads((root / "search.json").read_text())
        if path.startswith("blocks/") and path.endswith("/children"):
            block_id = path.split("/")[1]
            f = root / "blocks" / f"{block_id}.json"
            return json.loads(f.read_text()) if f.exists() else {"results": [], "has_more": False}
        raise FileNotFoundError(f"no fixture for {method} {url}")

    return send


class NotionConnector(Connector):
    name = "notion"
    description = "Notion pages shared with a read-only integration"
    secrets = ("NOTION_TOKEN",)
    auth_doc = "docs/connectors/notion.md"

    def __init__(self, transport: Transport | None = None, **options: Any) -> None:
        super().__init__(**options)
        if transport is None and options.get("fixtures"):
            transport = fixture_transport(Path(options["fixtures"]).expanduser())
        token = "fixture" if options.get("fixtures") else get_secret("NOTION_TOKEN")
        kwargs = {"transport": transport} if transport else {}
        self.http = ReadOnlyHTTP(
            base_url=API,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            read_posts=("/search", "/databases/"),
            **kwargs,
        )

    def discover(self) -> list[Source]:
        pages = self._search(None)
        return [Source(id=p["id"], label=_title(p), detail=p.get("url", "")) for p in pages]

    def fetch(self, since: str | None) -> FetchResult:
        pages = self._search(since)
        cursor = max((p["last_edited_time"] for p in pages), default=since)
        items = [{"page": p, "blocks": self._blocks(p["id"], 0)} for p in pages]
        return FetchResult(items, cursor)

    def normalize(self, raw: dict[str, Any]) -> Record:
        page = raw["page"]
        now = datetime.now(timezone.utc)
        people = []
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "people":
                people += [Participant(name=u["name"], email=(u.get("person") or {}).get("email"))
                           for u in prop["people"] if u.get("name")]
        return Record(
            id=f"{self.name}:{page['id']}",
            source=self.name,
            kind_hint=_kind_hint(page),
            title=_title(page),
            body=_render(raw["blocks"]),
            created_at=parse_dt(page.get("created_time"), now),
            updated_at=parse_dt(page.get("last_edited_time"), now),
            participants=people,
            url=page.get("url"),
            metadata={"notion_id": page["id"]},
        )

    def _search(self, since: str | None) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        start: str | None = None
        while True:
            payload: dict[str, Any] = {
                "filter": {"property": "object", "value": "page"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                "page_size": 100,
            }
            if start:
                payload["start_cursor"] = start
            resp = self.http.post_query("/search", payload)
            for page in resp.get("results", []):
                if since and page["last_edited_time"] <= since:
                    return pages  # results are newest first, so we can stop here
                if not page.get("archived") and not page.get("in_trash"):
                    pages.append(page)
            if not resp.get("has_more"):
                return pages
            start = resp.get("next_cursor")

    def _blocks(self, block_id: str, depth: int) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        start: str | None = None
        while True:
            qs = f"?page_size=100" + (f"&start_cursor={start}" if start else "")
            resp = self.http.get(f"/blocks/{block_id}/children{qs}")
            for b in resp.get("results", []):
                b["_depth"] = depth
                blocks.append(b)
                if b.get("has_children") and depth < MAX_DEPTH and b.get("type") != "child_page":
                    blocks += self._blocks(b["id"], depth + 1)
            if not resp.get("has_more"):
                return blocks
            start = resp.get("next_cursor")


def _plain(rich: list[dict[str, Any]]) -> str:
    return "".join(r.get("plain_text", "") for r in rich)


def _title(page: dict[str, Any]) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return _plain(prop["title"]) or "Untitled"
    return "Untitled"


def _kind_hint(page: dict[str, Any]) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "select" and prop.get("select"):
            value = prop["select"]["name"].lower()
            if value in {"meeting", "decision", "project", "task", "document"}:
                return value
    return "document"


PREFIX = {
    "heading_1": "# ", "heading_2": "## ", "heading_3": "### ",
    "bulleted_list_item": "- ", "numbered_list_item": "1. ", "quote": "> ",
    "callout": "> ",
}


def _render(blocks: list[dict[str, Any]]) -> str:
    out = []
    for b in blocks:
        t = b.get("type", "")
        data = b.get(t, {})
        indent = "  " * b.get("_depth", 0)
        text = _plain(data.get("rich_text", []))
        if t == "to_do":
            out.append(f"{indent}- [{'x' if data.get('checked') else ' '}] {text}")
        elif t == "code":
            out.append(f"```{data.get('language', '')}\n{text}\n```")
        elif t == "child_page":
            out.append(f"{indent}- Subpage: {data.get('title', '')}")
        elif t == "divider":
            out.append("---")
        elif text:
            out.append(indent + PREFIX.get(t, "") + text)
    return "\n".join(out)
