from __future__ import annotations

from pathlib import Path

from commonplace.pipeline.writer import END, START, VaultWriter, parse_note


def make(vault: Path, state: dict | None = None) -> VaultWriter:
    return VaultWriter(vault, {} if state is None else state)


def test_create_then_unchanged(tmp_path: Path):
    state: dict = {}
    w = make(tmp_path, state)
    assert w.write("People/A.md", "person:a", {"type": "person"}, "# A\n").status == "created"
    assert w.write("People/A.md", "person:a", {"type": "person"}, "# A\n").status == "unchanged"
    text = (tmp_path / "People/A.md").read_text()
    assert START in text and END in text and "cp_hash:" in text


def test_update_preserves_human_tail_and_properties(tmp_path: Path):
    state: dict = {}
    w = make(tmp_path, state)
    w.write("People/A.md", "person:a", {"type": "person", "role": "CEO"}, "# A\n")
    path = tmp_path / "People/A.md"
    text = path.read_text()
    text = text.replace("type: person", "type: person\nmet_at: conference")  # human property
    text += "\nMy own notes about A.\n"  # human text after the managed block
    path.write_text(text)
    assert w.write("People/A.md", "person:a", {"type": "person", "role": "CTO"}, "# A\nnew\n").status == "updated"
    fm, _, body, tail = parse_note(path.read_text())
    assert fm["role"] == "CTO" and fm["met_at"] == "conference"
    assert "new" in body and "My own notes about A." in tail


def test_human_edit_inside_managed_block_is_never_clobbered(tmp_path: Path):
    state: dict = {}
    w = make(tmp_path, state)
    w.write("People/A.md", "person:a", {"type": "person"}, "# A\noriginal\n")
    path = tmp_path / "People/A.md"
    edited = path.read_text().replace("original", "corrected by a human")
    path.write_text(edited)
    result = w.write("People/A.md", "person:a", {"type": "person"}, "# A\nmachine update\n")
    assert result.status == "edited"
    assert path.read_text() == edited
    pending = tmp_path / ".commonplace/pending/People/A.md"
    assert "machine update" in pending.read_text()


def test_human_edit_to_managed_property_is_detected(tmp_path: Path):
    w = make(tmp_path)
    w.write("People/A.md", "person:a", {"type": "person", "role": "CEO"}, "# A\n")
    path = tmp_path / "People/A.md"
    path.write_text(path.read_text().replace("role: CEO", "role: Founder"))
    assert w.write("People/A.md", "person:a", {"type": "person", "role": "CTO"}, "# A\n").status == "edited"


def test_notes_without_marker_are_foreign(tmp_path: Path):
    (tmp_path / "People").mkdir()
    (tmp_path / "People/A.md").write_text("# A\nhand written\n")
    assert make(tmp_path).write("People/A.md", "person:a", {"type": "person"}, "# A\n").status == "foreign"
    assert (tmp_path / "People/A.md").read_text() == "# A\nhand written\n"


def test_dry_run_writes_nothing(tmp_path: Path):
    w = VaultWriter(tmp_path, {}, dry_run=True)
    assert w.write("People/A.md", "person:a", {"type": "person"}, "# A\n").status == "created"
    assert not (tmp_path / "People").exists()
