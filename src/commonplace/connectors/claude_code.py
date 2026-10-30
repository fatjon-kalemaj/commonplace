"""Claude Code session transcripts on this machine.

Claude Code stores one JSONL file per session under ~/.claude/projects/<project>/.
Each line is an event; we keep user and assistant text and drop tool calls,
tool output, thinking blocks and injected system reminders by default."""

from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import Record
from ._files import changed_files, parse_dt
from .base import Connector, FetchResult, Source

REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
COMMAND_NOISE = ("<command-", "<local-command", "Caveat: The messages below")


class ClaudeCodeConnector(Connector):
    name = "claude_code"
    description = "Claude Code session transcripts (~/.claude/projects/**/*.jsonl)"

    @property
    def root(self) -> Path:
        return Path(self.options.get("path", "~/.claude/projects")).expanduser()

    def discover(self) -> list[Source]:
        if not self.root.exists():
            return []
        return [
            Source(id=d.name, label=d.name, detail=f"{len(list(d.glob('*.jsonl')))} sessions")
            for d in sorted(self.root.iterdir()) if d.is_dir()
        ]

    def fetch(self, since: str | None) -> FetchResult:
        if not self.root.exists():
            return FetchResult([], since)
        files, cursor = changed_files(self.root, ["*/*.jsonl"], since)
        items = []
        for path in files:
            events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            cwd = next((e.get("cwd") for e in events if e.get("cwd")), "")
            if any(fnmatch.fnmatch(cwd, pat) for pat in self.options.get("exclude_cwd", [])):
                continue
            items.append({"path": str(path), "events": events})
        return FetchResult(items, cursor)

    def normalize(self, raw: dict[str, Any]) -> Record:
        events = raw["events"]
        path = Path(raw["path"])
        include_tools = self.options.get("include_tool_output", False)
        turns: list[str] = []
        first_user = ""
        summary = ""
        times: list[datetime] = []
        cwd = branch = ""
        for e in events:
            if e.get("type") == "summary":
                summary = e.get("summary", "")
                continue
            if e.get("type") not in {"user", "assistant"} or e.get("isMeta") or e.get("isSidechain"):
                continue
            cwd = cwd or e.get("cwd", "")
            branch = branch or e.get("gitBranch", "")
            if e.get("timestamp"):
                times.append(parse_dt(e["timestamp"], datetime.now(timezone.utc)))
            text = _text(e.get("message", {}).get("content"), include_tools)
            if not text:
                continue
            role = "User" if e["type"] == "user" else "Claude"
            if role == "User" and not first_user:
                first_user = text
            turns.append(f"**{role}:** {text}")
        now = datetime.now(timezone.utc)
        project = Path(cwd).name if cwd else path.parent.name
        title = summary or _first_line(first_user) or f"Session {path.stem[:8]}"
        return Record(
            id=f"{self.name}:{path.stem}",
            source=self.name,
            kind_hint="session",
            title=title,
            body="\n\n".join(turns),
            created_at=min(times) if times else now,
            updated_at=max(times) if times else now,
            metadata={"project": project, "cwd": cwd, "branch": branch, "session_id": path.stem},
        )


def _text(content: Any, include_tools: bool) -> str:
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = []
        for block in content:
            kind = block.get("type")
            if kind == "text":
                parts.append(block.get("text", ""))
            elif include_tools and kind == "tool_use":
                parts.append(f"[tool: {block.get('name')}]")
            elif include_tools and kind == "tool_result":
                c = block.get("content")
                parts.append(c if isinstance(c, str) else json.dumps(c)[:2000])
    else:
        return ""
    text = REMINDER.sub("", "\n".join(parts)).strip()
    if text.startswith(COMMAND_NOISE):
        return ""
    return text


def _first_line(text: str, limit: int = 70) -> str:
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"
