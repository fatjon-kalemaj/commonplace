"""Offline demo: build a vault from the synthetic Tallgrass Labs dataset in
demo/data using the rule-based analyzer. Nothing leaves the machine."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from .config import Config
from .paths import REPO_ROOT

DEMO_DIR = REPO_ROOT / "demo"
DEFAULT_DEMO_VAULT = Path("~/commonplace-demo-vault")

# Obsidian graph colors per folder (decimal RGB, Obsidian's format).
GRAPH_GROUPS = [
    ("path:People", 0x4E79A7), ("path:Companies", 0xE15759), ("path:Projects", 0x59A14F),
    ("path:Meetings", 0xF28E2B), ("path:Decisions", 0xB07AA1), ("path:Emails", 0x76B7B2),
    ("path:Sessions", 0xEDC948), ("path:Daily", 0xBAB0AC),
]


def demo_config(vault: Path) -> Config:
    data = DEMO_DIR / "data"
    known = tomllib.loads((DEMO_DIR / "tallgrass.toml").read_text())
    return Config.from_dict({
        "vault": str(vault),
        "redaction": {"mode": "off"},
        "known_entities": known,
        "connectors": {
            "claude_code": {"path": str(data / "claude-projects")},
            "meeting_exports": {"path": str(data / "meetings")},
            "mail": {"type": "folder", "path": str(data / "mail"), "include": ["**/*.eml"]},
            "notes": {"type": "folder", "path": str(data / "docs")},
            "notion": {"fixtures": str(data / "notion")},
        },
    })


def write_obsidian_settings(vault: Path) -> None:
    obs = vault / ".obsidian"
    obs.mkdir(parents=True, exist_ok=True)
    graph = obs / "graph.json"
    if not graph.exists():
        graph.write_text(json.dumps({
            "colorGroups": [{"query": q, "color": {"a": 1, "rgb": rgb}} for q, rgb in GRAPH_GROUPS],
            "hideUnresolved": True,
            "showTags": False,
        }, indent=2))
