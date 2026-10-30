"""Claude analyzer request shape, tested against a fake client (no network)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from commonplace.config import KnownEntities, KnownPerson
from commonplace.models import Analysis, Kind, Participant, Record
from commonplace.pipeline.analyze import AnalysisRefused, ClaudeAnalyzer, OfflineAnalyzer
from commonplace.redact import Redactor


def record(body="Call me at +1 555 014 2297.\nDecision: ship it (owner: Ana Ruiz)"):
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return Record(id="t:1", source="t", kind_hint="meeting", title="Sync", body=body,
                  created_at=now, updated_at=now, participants=[Participant(name="Ana Ruiz")])


class FakeMessages:
    def __init__(self, stop_reason="end_turn"):
        self.calls = []
        self.stop_reason = stop_reason

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        parsed = Analysis(kind=Kind.meeting, title="Sync", summary="s")
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=parsed)


def fake_client(stop_reason="end_turn"):
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(stop_reason)))


def test_claude_request_uses_structured_output_and_defaults():
    client = fake_client()
    a = ClaudeAnalyzer("claude-opus-5-5", client=client)
    out = a.analyze(record(), KnownEntities(people=[KnownPerson(name="Ana Ruiz")]))
    call = client.beta.messages.calls[0]
    assert out.kind == Kind.meeting
    assert call["model"] == "claude-opus-5-5"
    assert call["output_format"] is Analysis
    assert call["output_config"] == {"effort": "medium"}
    assert call["fallbacks"] == "default"
    assert "person: Ana Ruiz" in call["messages"][0]["content"]


def test_claude_request_is_redacted_before_sending():
    client = fake_client()
    a = ClaudeAnalyzer("claude-opus-5-5", client=client, redact=Redactor(mode="api").redact)
    a.analyze(record(), KnownEntities())
    sent = client.beta.messages.calls[0]["messages"][0]["content"]
    assert "555 014 2297" not in sent and "[PHONE]" in sent


def test_refusal_raises():
    a = ClaudeAnalyzer("claude-opus-5-5", client=fake_client("refusal"))
    with pytest.raises(AnalysisRefused):
        a.analyze(record(), KnownEntities())


def test_offline_extracts_decisions_and_owners():
    known = KnownEntities(people=[KnownPerson(name="Ana Ruiz", aliases=["Ana"])])
    out = OfflineAnalyzer().analyze(record(), known)
    assert out.decisions[0].title == "Ship it" and out.decisions[0].owner == "Ana Ruiz"
    assert [p.name for p in out.people] == ["Ana Ruiz"]
