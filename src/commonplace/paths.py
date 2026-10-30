"""Path guards. The vault holds real records, so it must never live inside a
git checkout of this repo (or any repo), where it could be committed."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class UnsafeVaultPath(ValueError):
    pass


def git_root(path: Path) -> Path | None:
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def check_vault_path(vault: Path, repo_root: Path = REPO_ROOT, allow_git: bool = False) -> Path:
    """Return the resolved vault path, or raise if it sits inside the repo
    or inside any other git working tree."""
    vault = vault.expanduser().resolve()
    if is_inside(vault, repo_root):
        raise UnsafeVaultPath(
            f"Vault {vault} is inside the commonplace repo ({repo_root}). "
            "Real records must stay out of the repo. Pick a path outside it."
        )
    if not allow_git:
        root = git_root(vault)
        if root is not None:
            raise UnsafeVaultPath(
                f"Vault {vault} is inside the git working tree {root}. "
                "Pass --allow-git-vault if you version your vault on purpose."
            )
    return vault
