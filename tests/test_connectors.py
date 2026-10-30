from __future__ import annotations

from pathlib import Path

import pytest

from commonplace import connectors
from commonplace.connectors.claude_code import ClaudeCodeConnector
from commonplace.connectors.folder import FolderConnector
from commonplace.connectors.meetings import MeetingExportsConnector

DATA = Path(__file__).resolve().parents[1] / "demo" / "data"


def test_claude_code_sessions():
    conn = ClaudeCodeConnector(path=str(DATA / "claude-projects"))
    assert len(conn.discover()) == 3
    records, cursor = conn.records(None)
    assert cursor and len(records) == 3
    r = next(r for r in records if "1919" in r.title)
    assert r.kind_hint == "session" and r.metadata["project"] == "underwriting-copilot"
    assert "**User:**" in r.body and "**Claude:**" in r.body
    assert r.created_at.isoformat().startswith("2026-09-19")


def test_claude_code_drops_tool_output_and_reminders(tmp_path: Path):
    import json
    d = tmp_path / "proj"
    d.mkdir()
    events = [
        {"type": "user", "timestamp": "2026-10-01T10:00:00Z", "cwd": "/x/y",
         "message": {"role": "user", "content": "Fix the bug <system-reminder>secret context</system-reminder>"}},
        {"type": "assistant", "timestamp": "2026-10-01T10:01:00Z",
         "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hmm"},
                                                       {"type": "tool_use", "name": "Bash", "input": {}},
                                                       {"type": "text", "text": "Done."}]}},
        {"type": "user", "timestamp": "2026-10-01T10:02:00Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "content": "API_KEY=abc"}]}},
    ]
    (d / "s1.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    records, _ = ClaudeCodeConnector(path=str(tmp_path)).records(None)
    body = records[0].body
    assert "secret context" not in body and "API_KEY" not in body and "hmm" not in body
    assert "Fix the bug" in body and "Done." in body


def test_incremental_fetch_uses_cursor():
    conn = FolderConnector(path=str(DATA / "docs"))
    first, cursor = conn.records(None)
    again, cursor2 = conn.records(cursor)
    assert len(first) == 2 and again == [] and cursor2 == cursor


def test_email_threads_have_participants():
    records, _ = FolderConnector(path=str(DATA / "mail"), include=["*.eml"]).records(None)
    r = next(r for r in records if "Loan file" in r.title)
    assert r.kind_hint == "email_thread" and not r.title.lower().startswith("re:")
    assert {p.email for p in r.participants} >= {"jen.albright@copperline.example", "lena@tallgrass.example"}


def test_meeting_exports_formats():
    records, _ = MeetingExportsConnector(path=str(DATA / "meetings")).records(None)
    apps = {r.metadata["app"] for r in records}
    assert apps == {"fireflies", "granola", "wispr_flow"}
    kickoff = next(r for r in records if r.title == "Copperline kickoff")
    assert any(p.email == "jen.albright@copperline.example" for p in kickoff.participants)


def test_stubs_fail_with_setup_pointer():
    for name, cls in connectors.REGISTRY.items():
        if cls.implemented:
            continue
        conn = cls()
        with pytest.raises(NotImplementedError, match="docs/connectors/"):
            conn.fetch(None)
        assert (Path(__file__).resolve().parents[1] / cls.auth_doc).exists(), cls.auth_doc


def test_unknown_connector():
    with pytest.raises(KeyError):
        connectors.build("dropbox", {})
