from __future__ import annotations

import json
import os
import re
from pathlib import Path

from commonplace.pipeline.analyze import OfflineAnalyzer
from commonplace.pipeline.run import Pipeline
from commonplace.state import SyncState

LINK = re.compile(r"\[\[([^\]|#]+)")


def run(config):
    pipe = Pipeline(config, OfflineAnalyzer(), log=lambda *_: None)
    return pipe.run(*pipe.collect())


def notes(vault: Path) -> dict[str, str]:
    return {str(p.relative_to(vault)): p.read_text() for p in vault.rglob("*.md")
            if not p.relative_to(vault).parts[0].startswith(".")}


def test_demo_builds_expected_structure(config, vault):
    report = run(config)
    assert not report.failed
    files = notes(vault)
    for folder in ("Meetings", "People", "Companies", "Projects", "Decisions", "Daily", "Emails", "Sessions"):
        assert any(f.startswith(folder + "/") for f in files), folder
    assert "People/Jen Albright.md" in files
    assert "Companies/Copperline Credit.md" in files
    assert "Projects/Underwriting Copilot.md" in files


def test_every_wikilink_resolves(config, vault):
    run(config)
    files = notes(vault)
    stems = {Path(f).stem for f in files}
    dangling = {t for text in files.values() for t in LINK.findall(text) if t.strip() not in stems}
    assert dangling == set()


def test_graph_connects_people_companies_projects_meetings(config, vault):
    run(config)
    jen = (vault / "People/Jen Albright.md").read_text()
    assert "[[Copperline Credit]]" in jen
    assert "[[2026-09-08 Copperline kickoff]]" in jen
    kickoff = (vault / "Meetings/2026-09-08 Copperline kickoff.md").read_text()
    assert "[[Underwriting Copilot]]" in kickoff and "[[Jen Albright]]" in kickoff


def test_rerun_is_idempotent(config, vault):
    run(config)
    before = notes(vault)
    report = run(config)
    assert report.analyzed == 0 and report.writes == []
    assert notes(vault) == before


def test_rerun_after_reset_cursor_does_not_duplicate(config, vault):
    """Even if every record is re-fetched, unchanged records are skipped by hash."""
    run(config)
    before = notes(vault)
    state = SyncState.load(vault)
    state.cursors = {}
    state.save()
    report = run(config)
    assert report.analyzed == 0 and report.skipped_unchanged == report.fetched
    assert notes(vault) == before


def test_changed_record_updates_note_without_touching_human_edits(config, vault, tmp_path):
    import shutil
    data = tmp_path / "docs"
    shutil.copytree(Path(config.connectors["notes"]["path"]), data)
    config.connectors = {"notes": {"type": "folder", "path": str(data)}}
    run(config)
    person = vault / "People/Maya Okafor.md"
    person.write_text(person.read_text() + "\nPrefers async updates.\n")
    doc = data / "q4-priorities.md"
    doc.write_text(doc.read_text() + "\n4. Hire a second ML engineer.\n")
    st = doc.stat()
    os.utime(doc, (st.st_atime, st.st_mtime + 10))
    report = run(config)
    assert report.analyzed == 1
    assert "Hire a second ML engineer" in (vault / "Documents/Q4 priorities.md").read_text()
    assert "Prefers async updates." in person.read_text()


def test_dry_run_leaves_vault_empty(config, vault):
    pipe = Pipeline(config, OfflineAnalyzer(), dry_run=True, log=lambda *_: None)
    report = pipe.run(*pipe.collect())
    assert report.writes and not vault.exists()


def test_state_file_lives_in_vault(config, vault):
    run(config)
    state = json.loads((vault / ".commonplace/state.json").read_text())
    assert state["version"] == 1 and len(state["records"]) == 21


def test_tags_are_valid_obsidian_tags():
    from commonplace.pipeline.run import tag
    assert tag("Commercial Real Estate") == "commercial-real-estate"
    assert tag("SOC 2 (Type 1)") == "soc-2-type-1"
