"""A plain folder of Markdown, text and .eml files."""

from __future__ import annotations

import email
import email.policy
import email.utils
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import Participant, Record
from ._files import changed_files, date_from_name, parse_dt, split_frontmatter
from .base import Connector, FetchResult, Source

DEFAULT_INCLUDE = ["**/*.md", "**/*.txt", "**/*.eml"]


class FolderConnector(Connector):
    name = "folder"
    description = "A local folder of .md, .txt and .eml files"

    @property
    def root(self) -> Path:
        if "path" not in self.options:
            raise ValueError("folder connector needs a `path`")
        return Path(self.options["path"]).expanduser()

    def discover(self) -> list[Source]:
        files, _ = changed_files(self.root, self.options.get("include", DEFAULT_INCLUDE), None)
        return [Source(id=str(self.root), label=self.root.name, detail=f"{len(files)} files")]

    def fetch(self, since: str | None) -> FetchResult:
        files, cursor = changed_files(
            self.root, self.options.get("include", DEFAULT_INCLUDE), since,
            self.options.get("exclude", []),
        )
        return FetchResult([{"path": str(p), "rel": str(p.relative_to(self.root))} for p in files], cursor)

    def normalize(self, raw: dict[str, Any]) -> Record:
        path = Path(raw["path"])
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        rid = f"{self.options.get('id_prefix', self.name)}:{raw['rel']}"
        source = self.options.get("id_prefix", self.name)
        if path.suffix == ".eml":
            return _email_record(path, rid, source, mtime)
        meta, body = split_frontmatter(path.read_text(errors="replace"))
        h1 = re.search(r"^# (.+)$", body, re.M)
        title = str(meta.get("title") or (h1.group(1) if h1 else path.stem))
        created = parse_dt(meta.get("date") or meta.get("created"), date_from_name(path, mtime))
        participants = [Participant(name=str(n)) for n in meta.get("attendees", []) or []]
        return Record(
            id=rid,
            source=source,
            kind_hint=meta.get("type") or meta.get("kind") or "document",
            title=title,
            body=body,
            created_at=created,
            updated_at=mtime,
            participants=participants,
            metadata={"path": raw["rel"]},
        )


def _email_record(path: Path, rid: str, source: str, mtime: datetime) -> Record:
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = body_part.get_content() if body_part is not None else ""
    people: dict[str, Participant] = {}
    for header in ("from", "to", "cc"):
        for name, addr in email.utils.getaddresses(msg.get_all(header, [])):
            if addr and addr.lower() not in people:
                people[addr.lower()] = Participant(name=name or addr.split("@")[0], email=addr.lower())
    date = msg.get("date")
    created = email.utils.parsedate_to_datetime(date) if date else mtime
    subject = re.sub(r"^((re|fwd?):\s*)+", "", msg.get("subject", path.stem), flags=re.I)
    return Record(
        id=rid,
        source=source,
        kind_hint="email_thread",
        title=subject,
        body=body,
        created_at=created,
        updated_at=mtime,
        participants=list(people.values()),
        metadata={"path": path.name, "message_id": msg.get("message-id", "")},
    )
