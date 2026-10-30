"""Privacy guarantees that must never regress."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from commonplace.config import Config
from commonplace.connectors import ReadOnlyHTTP, ReadOnlyViolation
from commonplace.connectors.notion import NotionConnector
from commonplace.paths import REPO_ROOT, UnsafeVaultPath, check_vault_path
from commonplace.redact import Redactor


TOKEN_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),         # Anthropic API keys
    re.compile(r"\b(?:secret|ntn)_[A-Za-z0-9]{30,}"),  # Notion integration tokens
]


def test_vault_inside_repo_is_rejected():
    with pytest.raises(UnsafeVaultPath):
        check_vault_path(REPO_ROOT / "vault")
    with pytest.raises(UnsafeVaultPath):
        check_vault_path(REPO_ROOT / "demo" / "data" / "my-vault")


def test_config_with_vault_inside_repo_fails_to_load():
    with pytest.raises(UnsafeVaultPath):
        Config.from_dict({"vault": str(REPO_ROOT / "notes")})


def test_vault_inside_another_git_repo_needs_opt_in(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(UnsafeVaultPath):
        check_vault_path(tmp_path / "vault", repo_root=REPO_ROOT)
    assert check_vault_path(tmp_path / "vault", repo_root=REPO_ROOT, allow_git=True)


def test_vault_outside_repo_is_accepted(tmp_path: Path):
    assert check_vault_path(tmp_path / "vault") == (tmp_path / "vault").resolve()


def test_example_configs_point_outside_the_repo():
    for path in REPO_ROOT.glob("*.toml"):
        data = tomllib.loads(path.read_text())
        if "vault" in data:
            vault = Path(data["vault"]).expanduser()
            assert not vault.resolve().is_relative_to(REPO_ROOT), f"{path.name} puts the vault in the repo"


def test_no_vault_or_state_committed_inside_repo():
    """Fails if anything that looks like a vault or sync state sits in the repo tree."""
    offenders = [
        p for p in REPO_ROOT.rglob("*")
        if p.name in {".obsidian", ".commonplace"} and ".venv" not in p.parts
    ]
    assert offenders == [], f"vault data inside the repo: {offenders}"


def test_gitignore_covers_vaults_and_secrets():
    ignored = (REPO_ROOT / ".gitignore").read_text()
    for pattern in (".obsidian/", ".commonplace/", ".env", "commonplace.toml"):
        assert pattern in ignored


def test_tracked_files_contain_no_obvious_secrets():
    try:
        files = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True,
                               text=True, check=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("not a git checkout")
    for name in files:
        path = REPO_ROOT / name
        if path.suffix in {".py", ".md", ".toml", ".json", ".txt", ".eml", ".jsonl", ".example"}:
            text = path.read_text(errors="ignore")
            for pattern in TOKEN_PATTERNS:
                assert not pattern.search(text), f"{name} contains something shaped like a token"


def test_read_only_http_blocks_writes():
    calls = []
    http = ReadOnlyHTTP("https://api.example", {}, read_posts=("/search",),
                        transport=lambda *a: calls.append(a) or {})
    http.get("/pages/1")
    http.post_query("/search", {})
    with pytest.raises(ReadOnlyViolation):
        http.post_query("/pages", {"parent": {}})
    with pytest.raises(ReadOnlyViolation):
        http._send("PATCH", "/pages/1", b"{}")
    with pytest.raises(ReadOnlyViolation):
        http.post_query("/search", {"query": "  mutation { deleteTranscript(id: 1) }"})
    assert [c[0] for c in calls] == ["GET", "POST"]


def test_notion_connector_only_issues_read_requests(config):
    seen = []
    fixtures = Path(config.connectors["notion"]["fixtures"])
    from commonplace.connectors.notion import fixture_transport
    inner = fixture_transport(fixtures)

    def spy(method, url, headers, body):
        seen.append((method, url.split("/v1/")[1].split("?")[0]))
        return inner(method, url, headers, body)

    conn = NotionConnector(transport=spy, fixtures=str(fixtures))
    records, _ = conn.records(None)
    assert len(records) == 4
    for method, path in seen:
        assert method == "GET" or path == "search", (method, path)


def test_redaction():
    r = Redactor(mode="api", custom=[r"Project Falcon"])
    text = "Call +1 555 014 2297 or jen@copperline.example, SSN 123-45-6789, re Project Falcon"
    out = r.redact(text)
    assert "555" not in out and "@" not in out and "6789" not in out and "Falcon" not in out
    assert "[PHONE]" in out and "[EMAIL]" in out and "[SSN]" in out
    assert r.for_api and not r.for_vault


def test_redaction_mode_vault_redacts_written_notes(config, vault):
    from commonplace.pipeline.analyze import OfflineAnalyzer
    from commonplace.pipeline.run import Pipeline

    config.redactor = Redactor(mode="vault")
    pipe = Pipeline(config, OfflineAnalyzer(), log=lambda *_: None)
    pipe.run(*pipe.collect(only=["mail"]))
    note = (vault / "Emails" / "2026-09-12 Loan file sample for the pilot.md").read_text()
    assert "555 014 2297" not in note and "[PHONE]" in note


def test_secrets_come_from_env_not_config(monkeypatch):
    from commonplace import secrets

    monkeypatch.setenv("NOTION_TOKEN", "from-env")
    assert secrets.get_secret("NOTION_TOKEN") == "from-env"
    monkeypatch.delenv("NOTION_TOKEN")
    monkeypatch.setattr(secrets, "_keyring", lambda: None)
    with pytest.raises(secrets.MissingSecret):
        secrets.get_secret("NOTION_TOKEN")
