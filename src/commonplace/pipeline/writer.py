"""Writes notes into the vault without clobbering human edits.

A generated note has a managed part (the frontmatter keys commonplace sets,
and the body between the %% commonplace:start %% / %% commonplace:end %%
markers) and a human part (any other frontmatter keys, and everything after
the end marker). The frontmatter property `cp_hash` is the hash of the
managed part as last written.

On each write:
- no file yet             -> create
- file without cp_hash    -> a human note; never touched (status: foreign)
- managed part changed    -> a human edited it; left alone, proposed version
  since last write           saved under .commonplace/pending/ (status: edited)
- same managed content    -> nothing to do (status: unchanged)
- otherwise               -> replace the managed part, keep the human part
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..state import STATE_DIR

START = "%% commonplace:start %%"
END = "%% commonplace:end %%"
HASH_KEY = "cp_hash"
ID_KEY = "cp_id"


@dataclass
class WriteResult:
    path: str
    status: str  # created | updated | unchanged | edited | foreign


def managed_hash(fm: dict[str, Any], keys: list[str], body: str) -> str:
    payload = json.dumps({k: fm.get(k) for k in sorted(keys)}, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256((payload + "\0" + body.strip()).encode()).hexdigest()[:16]


def parse_note(text: str) -> tuple[dict[str, Any], str, str | None, str]:
    """Return (frontmatter, text before start marker, managed body or None, tail)."""
    fm: dict[str, Any] = {}
    rest = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm = yaml.safe_load(text[4:end]) or {}
            rest = text[end + 5:]
    if START in rest and END in rest:
        head, _, after = rest.partition(START)
        managed, _, tail = after.partition(END)
        return fm, head, managed.strip("\n"), tail
    return fm, rest, None, ""


def compose(fm: dict[str, Any], body: str, tail: str = "\n", head: str = "") -> str:
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=1000).strip()
    return f"---\n{fm_text}\n---\n{head}{START}\n{body.strip()}\n{END}\n{tail.lstrip(chr(10)) if tail.strip() else ''}"


class VaultWriter:
    def __init__(self, vault: Path, notes_state: dict[str, Any], dry_run: bool = False) -> None:
        self.vault = vault
        self.notes_state = notes_state
        self.dry_run = dry_run

    def write(self, rel_path: str, note_id: str, fm: dict[str, Any], body: str) -> WriteResult:
        keys = list(fm.keys()) + [ID_KEY]
        fm = {**fm, ID_KEY: note_id}
        new_hash = managed_hash(fm, keys, body)
        path = self.vault / rel_path
        if not path.exists():
            self._save(path, compose({**fm, HASH_KEY: new_hash}, body), rel_path, keys, new_hash)
            return WriteResult(rel_path, "created")

        old_fm, head, old_body, tail = parse_note(path.read_text())
        if HASH_KEY not in old_fm or old_body is None:
            return WriteResult(rel_path, "foreign")
        old_keys = self.notes_state.get(rel_path, {}).get("keys") or keys
        current = managed_hash(old_fm, old_keys, old_body)
        if current != old_fm[HASH_KEY]:
            self._pending(rel_path, compose({**fm, HASH_KEY: new_hash}, body))
            return WriteResult(rel_path, "edited")
        if current == new_hash:
            return WriteResult(rel_path, "unchanged")
        human = {k: v for k, v in old_fm.items() if k not in old_keys and k != HASH_KEY}
        merged = {**fm, **human, HASH_KEY: new_hash}
        self._save(path, compose(merged, body, tail, head), rel_path, keys, new_hash)
        return WriteResult(rel_path, "updated")

    def _save(self, path: Path, text: str, rel_path: str, keys: list[str], h: str) -> None:
        if self.dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.notes_state[rel_path] = {"hash": h, "keys": keys}

    def _pending(self, rel_path: str, text: str) -> None:
        if self.dry_run:
            return
        p = self.vault / STATE_DIR / "pending" / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
