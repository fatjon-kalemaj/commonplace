"""Configuration. Lives outside the repo by default
(~/.config/commonplace/config.toml) and never holds secrets."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import check_vault_path
from .redact import DEFAULT_KINDS, Redactor

DEFAULT_CONFIG_PATH = Path("~/.config/commonplace/config.toml").expanduser()
DEFAULT_MODEL = "claude-opus-5-5"


@dataclass
class KnownPerson:
    name: str
    email: str | None = None
    company: str | None = None
    role: str | None = None
    aliases: list[str] = field(default_factory=list)


@dataclass
class KnownEntities:
    """Optional gazetteer. Claude uses it to keep names canonical; the offline
    analyzer uses it as its only source of entity names."""

    people: list[KnownPerson] = field(default_factory=list)
    companies: dict[str, list[str]] = field(default_factory=dict)  # name -> aliases/domains
    projects: dict[str, list[str]] = field(default_factory=dict)  # name -> aliases

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnownEntities:
        return cls(
            people=[KnownPerson(**p) for p in data.get("people", [])],
            companies={c["name"]: c.get("aliases", []) for c in data.get("companies", [])},
            projects={p["name"]: p.get("aliases", []) for p in data.get("projects", [])},
        )


@dataclass
class Config:
    vault: Path
    model: str = DEFAULT_MODEL
    effort: str = "medium"
    use_fallbacks: bool = True
    max_record_chars: int = 400_000
    redactor: Redactor = field(default_factory=Redactor)
    connectors: dict[str, dict[str, Any]] = field(default_factory=dict)
    known: KnownEntities = field(default_factory=KnownEntities)
    allow_git_vault: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_dir: Path | None = None) -> Config:
        if "vault" not in data:
            raise ValueError("config needs a `vault` path")
        red = data.get("redaction", {})
        known = data.get("known_entities", {})
        if isinstance(known, str):  # path to a separate TOML file
            known_path = _resolve(known, base_dir)
            known = tomllib.loads(known_path.read_text())
        allow_git = bool(data.get("allow_git_vault", False))
        vault = check_vault_path(_resolve(data["vault"], base_dir), allow_git=allow_git)
        connectors = {
            name: {k: (str(_resolve(v, base_dir)) if k == "path" else v) for k, v in opts.items()}
            for name, opts in data.get("connectors", {}).items()
        }
        return cls(
            vault=vault,
            model=data.get("model", DEFAULT_MODEL),
            effort=data.get("effort", "medium"),
            use_fallbacks=data.get("use_fallbacks", True),
            max_record_chars=int(data.get("max_record_chars", 400_000)),
            redactor=Redactor(
                mode=red.get("mode", "off"),
                kinds=tuple(red.get("kinds", DEFAULT_KINDS)),
                custom=list(red.get("custom", [])),
            ),
            connectors=connectors,
            known=KnownEntities.from_dict(known),
            allow_git_vault=allow_git,
        )

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = (path or DEFAULT_CONFIG_PATH).expanduser()
        if not path.exists():
            raise FileNotFoundError(
                f"No config at {path}. Copy commonplace.example.toml there and edit it."
            )
        return cls.from_dict(tomllib.loads(path.read_text()), base_dir=path.parent)


def _resolve(value: str, base_dir: Path | None) -> Path:
    p = Path(value).expanduser()
    if not p.is_absolute() and base_dir is not None:
        p = base_dir / p
    return p
