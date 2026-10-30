"""Sync state, stored inside the vault at .commonplace/state.json.

It records, per connector, the cursor for incremental fetches; per record, the
content hash and cached analysis (so unchanged records are never re-sent to
Claude); per note, the managed hash last written; and the entity index used to
build Person, Company and Project notes across runs."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATE_DIR = ".commonplace"
STATE_FILE = "state.json"
VERSION = 1


@dataclass
class SyncState:
    path: Path
    cursors: dict[str, str] = field(default_factory=dict)
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)  # vault-relative path -> managed hash
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, vault: Path) -> SyncState:
        path = vault / STATE_DIR / STATE_FILE
        if not path.exists():
            return cls(path=path)
        data = json.loads(path.read_text())
        if data.get("version") != VERSION:
            raise RuntimeError(f"Unsupported state version in {path}")
        return cls(
            path=path,
            cursors=data.get("cursors", {}),
            records=data.get("records", {}),
            notes=data.get("notes", {}),
            entities=data.get("entities", {}),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "version": VERSION,
                "cursors": self.cursors,
                "records": self.records,
                "notes": self.notes,
                "entities": self.entities,
            },
            indent=2,
            sort_keys=True,
        )
        # Write atomically so a crash never leaves a half-written state file.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-")
        with os.fdopen(fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp, self.path)
