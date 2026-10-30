"""The common record model every connector normalizes into, and the
structured analysis Claude (or the offline analyzer) returns for it."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Participant(BaseModel):
    name: str
    email: str | None = None


class Record(BaseModel):
    """One unit of company memory: a meeting, an email thread, a page, a session."""

    id: str = Field(description="Stable id, '<connector>:<native id>'.")
    source: str = Field(description="Connector name that produced the record.")
    kind_hint: str | None = Field(
        default=None, description="What the connector thinks this is, e.g. 'meeting'."
    )
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
    participants: list[Participant] = Field(default_factory=list)
    url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def content_hash(self) -> str:
        payload = json.dumps(
            {
                "title": self.title,
                "body": self.body,
                "participants": [p.model_dump() for p in self.participants],
                "kind_hint": self.kind_hint,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class Kind(str, Enum):
    meeting = "meeting"
    email_thread = "email_thread"
    document = "document"
    decision = "decision"
    task = "task"
    project = "project"
    person = "person"
    company = "company"
    session = "session"
    note = "note"


class PersonRef(BaseModel):
    name: str = Field(description="Full name as it should appear on the person's note.")
    email: str | None = None
    company: str | None = Field(default=None, description="Company the person works for, if stated.")
    role: str | None = None


class DecisionItem(BaseModel):
    title: str = Field(description="Short statement of what was decided, under 80 characters.")
    rationale: str | None = None
    owner: str | None = Field(default=None, description="Person accountable, full name.")


class TaskItem(BaseModel):
    text: str
    owner: str | None = Field(default=None, description="Person who owns it, full name.")
    due: str | None = Field(default=None, description="Due date as YYYY-MM-DD if stated.")


class Analysis(BaseModel):
    """What the pipeline learns about one record."""

    kind: Kind
    title: str = Field(description="A clear note title, no dates, under 80 characters.")
    summary: str = Field(description="Two to four plain sentences.")
    people: list[PersonRef] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    decisions: list[DecisionItem] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list, description="Up to five lowercase tags.")
