"""PII redaction applied to record text before it leaves the machine
(mode 'api') or before it is written anywhere (mode 'vault')."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "money": re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?\s?(?:[kKmMbB]|million|billion)?"),
}

DEFAULT_KINDS = ("email", "phone", "ssn", "card", "iban")


@dataclass
class Redactor:
    mode: str = "off"  # off | api | vault
    kinds: tuple[str, ...] = DEFAULT_KINDS
    custom: list[str] = field(default_factory=list)
    keep_emails_for_participants: bool = True

    def __post_init__(self) -> None:
        if self.mode not in {"off", "api", "vault"}:
            raise ValueError(f"redaction mode must be off, api or vault, not {self.mode!r}")
        unknown = set(self.kinds) - PATTERNS.keys()
        if unknown:
            raise ValueError(f"unknown redaction kinds: {sorted(unknown)}")
        self._custom = [re.compile(p) for p in self.custom]

    @property
    def for_api(self) -> bool:
        return self.mode in {"api", "vault"}

    @property
    def for_vault(self) -> bool:
        return self.mode == "vault"

    def redact(self, text: str) -> str:
        for kind in self.kinds:
            text = PATTERNS[kind].sub(f"[{kind.upper()}]", text)
        for pattern in self._custom:
            text = pattern.sub("[REDACTED]", text)
        return text
