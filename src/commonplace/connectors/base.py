"""The connector contract.

Every connector is read-only and implements three steps:

    discover()           -> what can be read (folders, databases, workspaces)
    fetch(since)         -> raw items changed since the cursor, plus the new cursor
    normalize(raw)       -> a common Record

Connectors never write to the source system. HTTP connectors go through
ReadOnlyHTTP, which refuses any method or endpoint not on an allowlist."""

from __future__ import annotations

import json
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Iterable

from ..models import Record


@dataclass
class Source:
    """Something discover() found, e.g. a folder or a Notion workspace."""

    id: str
    label: str
    detail: str = ""


@dataclass
class FetchResult:
    items: list[Any]
    cursor: str | None


class Connector(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    implemented: ClassVar[bool] = True
    secrets: ClassVar[tuple[str, ...]] = ()
    auth_doc: ClassVar[str] = ""

    def __init__(self, **options: Any) -> None:
        self.options = options

    @abstractmethod
    def discover(self) -> list[Source]: ...

    @abstractmethod
    def fetch(self, since: str | None) -> FetchResult: ...

    @abstractmethod
    def normalize(self, raw: Any) -> Record: ...

    def records(self, since: str | None) -> tuple[list[Record], str | None]:
        result = self.fetch(since)
        return [self.normalize(item) for item in result.items], result.cursor


class StubConnector(Connector):
    """A documented placeholder. Fails loudly with setup instructions."""

    implemented = False

    def _not_yet(self) -> NotImplementedError:
        return NotImplementedError(
            f"The {self.name} connector is a stub. Auth setup and the planned "
            f"read-only scopes are in {self.auth_doc}. Contributions welcome."
        )

    def discover(self) -> list[Source]:
        raise self._not_yet()

    def fetch(self, since: str | None) -> FetchResult:
        raise self._not_yet()

    def normalize(self, raw: Any) -> Record:
        raise self._not_yet()


class ReadOnlyViolation(RuntimeError):
    pass


Transport = Callable[[str, str, dict[str, str], bytes | None], Any]


def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> Any:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


@dataclass
class ReadOnlyHTTP:
    """GET is always allowed. POST is allowed only for endpoints listed in
    `read_posts`, which must be query endpoints (search, database query,
    GraphQL queries). Everything else raises before a request is sent."""

    base_url: str
    headers: dict[str, str]
    read_posts: Iterable[str] = field(default_factory=tuple)
    transport: Transport = urllib_transport

    def get(self, path: str) -> Any:
        return self._send("GET", path, None)

    def post_query(self, path: str, payload: dict[str, Any]) -> Any:
        if not any(path.startswith(p) for p in self.read_posts):
            raise ReadOnlyViolation(f"POST {path} is not an allowlisted read endpoint")
        if str(payload.get("query", "")).lstrip().lower().startswith("mutation"):
            raise ReadOnlyViolation("GraphQL mutations are never allowed")
        return self._send("POST", path, json.dumps(payload).encode())

    def _send(self, method: str, path: str, body: bytes | None) -> Any:
        if method not in {"GET", "POST"}:
            raise ReadOnlyViolation(f"{method} is never allowed")
        return self.transport(method, self.base_url + path, dict(self.headers), body)
