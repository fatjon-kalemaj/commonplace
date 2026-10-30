from __future__ import annotations

from pathlib import Path

import pytest

from commonplace.demo import demo_config


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return tmp_path / "vault"


@pytest.fixture
def config(vault: Path):
    return demo_config(vault)
