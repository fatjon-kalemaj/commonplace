"""Secrets come from the environment first, then the OS keychain.
They are never read from config files and never written to disk by commonplace."""

from __future__ import annotations

import os

SERVICE = "commonplace"


class MissingSecret(RuntimeError):
    pass


def _keyring():
    try:
        import keyring  # optional dependency: pip install 'commonplace[keychain]'
    except ImportError:
        return None
    return keyring


def get_secret(name: str, required: bool = True) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    kr = _keyring()
    if kr is not None:
        try:
            value = kr.get_password(SERVICE, name)
        except Exception:  # no backend available, locked keychain, etc.
            value = None
        if value:
            return value
    if required:
        raise MissingSecret(
            f"{name} is not set. Export it, or store it in the OS keychain with "
            f"`commonplace secrets set {name}`."
        )
    return None


def has_secret(name: str) -> bool:
    return get_secret(name, required=False) is not None


def set_secret(name: str, value: str) -> None:
    kr = _keyring()
    if kr is None:
        raise RuntimeError("Install the keychain extra first: pip install 'commonplace[keychain]'")
    kr.set_password(SERVICE, name, value)
