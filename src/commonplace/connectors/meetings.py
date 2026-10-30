"""Meeting transcripts and voice notes from exported files.

Works offline against the exports these tools produce:

- Fireflies: JSON transcript export (title, date, participants, sentences[])
- Granola: Markdown note export (frontmatter or an "Attendees:" line)
- Wispr Flow: plain-text dictated notes

The live Fireflies and Granola APIs are stubbed in stubs.py."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import Participant, Record
from ._files import changed_files, date_from_name, parse_dt, split_frontmatter
from .base import Connector, FetchResult, Source

PATTERNS = ["**/*.json", "**/*.md", "**/*.txt"]


class MeetingExportsConnector(Connector):
    name = "meeting_exports"
    description = "Exported transcripts from Fireflies (JSON), Granola (MD), Wispr Flow (TXT)"

    @property
    def root(self) -> Path:
        if "path" not in self.options:
            raise ValueError("meeting_exports connector needs a `path`")
        return Path(self.options["path"]).expanduser()

    def discover(self) -> list[Source]:
        files, _ = changed_files(self.root, PATTERNS, None)
        return [Source(id=str(self.root), label=self.root.name, detail=f"{len(files)} exports")]

    def fetch(self, since: str | None) -> FetchResult:
        files, cursor = changed_files(self.root, PATTERNS, since)
        return FetchResult([{"path": str(p), "rel": str(p.relative_to(self.root))} for p in files], cursor)

    def normalize(self, raw: dict[str, Any]) -> Record:
        path = Path(raw["path"])
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        rid = f"{self.name}:{raw['rel']}"
        if path.suffix == ".json":
            return self._fireflies(json.loads(path.read_text()), rid, mtime)
        meta, body = split_frontmatter(path.read_text(errors="replace"))
        if path.suffix == ".md":
            attendees = list(meta.get("attendees", []) or [])
            m = re.search(r"^Attendees:\s*(.+)$", body, re.M)
            if m and not attendees:
                attendees = [a.strip() for a in m.group(1).split(",") if a.strip()]
            h1 = re.search(r"^# (.+)$", body, re.M)
            return Record(
                id=rid, source=self.name, kind_hint="meeting",
                title=str(meta.get("title") or (h1.group(1) if h1 else path.stem)),
                body=body, created_at=parse_dt(meta.get("date"), date_from_name(path, mtime)), updated_at=mtime,
                participants=[Participant(name=a) for a in attendees],
                metadata={"app": "granola", "path": raw["rel"]},
            )
        # Wispr Flow and other dictated notes: first line is the title.
        lines = body.strip().splitlines()
        title = lines[0].lstrip("# ").strip() if lines else path.stem
        return Record(
            id=rid, source=self.name, kind_hint="note", title=title,
            body="\n".join(lines[1:]).strip(),
            created_at=parse_dt(meta.get("date"), date_from_name(path, mtime)), updated_at=mtime,
            metadata={"app": "wispr_flow", "path": raw["rel"]},
        )

    def _fireflies(self, data: dict[str, Any], rid: str, mtime: datetime) -> Record:
        speakers: dict[str, Participant] = {}
        lines = []
        for s in data.get("sentences", []):
            name = s.get("speaker_name") or "Unknown"
            speakers.setdefault(name, Participant(name=name))
            lines.append(f"**{name}:** {s.get('text', '')}")
        emails = data.get("participants", [])
        for e in emails:
            if "@" in e and not any(p.email == e for p in speakers.values()):
                match = next((p for p in speakers.values() if p.email is None
                              and p.name.split()[0].lower() == e.split("@")[0].split(".")[0].lower()), None)
                if match:
                    match.email = e
        body = "\n".join(lines)
        summary = data.get("summary") or {}
        if summary.get("action_items"):
            body += "\n\n## Action items\n" + summary["action_items"]
        return Record(
            id=rid, source=self.name, kind_hint="meeting",
            title=data.get("title", "Untitled meeting"), body=body,
            created_at=parse_dt(data.get("date"), mtime), updated_at=mtime,
            participants=list(speakers.values()),
            metadata={"app": "fireflies", "duration_min": str(data.get("duration", ""))},
        )
