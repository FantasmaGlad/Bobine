"""Source de vérité unique du numéro de version ET du commit courant de l'application."""

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from app.config import ROOT_DIR

_FALLBACK_VERSION = "5.1.2"
_FALLBACK_COMMIT = "unknown"


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return ROOT_DIR
    return ROOT_DIR.parent


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Numéro de version nu."""
    env_ver = os.environ.get("BOBINE_VERSION", "").strip()
    if env_ver:
        return env_ver.lstrip("vV")

    for candidate_dir in (_app_root(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent, ROOT_DIR):
        try:
            ver_file = candidate_dir / "VERSION"
            if ver_file.is_file():
                content = ver_file.read_text(encoding="utf-8").strip()
                if content:
                    return content
        except OSError:
            pass

    return _FALLBACK_VERSION


@lru_cache(maxsize=1)
def get_app_commit() -> str:
    """Commit court (7 caractères) du build courant."""
    env_commit = os.environ.get("BOBINE_COMMIT", "").strip()
    if env_commit:
        return env_commit

    for candidate_dir in (_app_root(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent, ROOT_DIR):
        try:
            commit_file = candidate_dir / "COMMIT"
            if commit_file.is_file():
                content = commit_file.read_text(encoding="utf-8").strip()
                if content:
                    return content
        except OSError:
            pass

    return _FALLBACK_COMMIT


def get_app_tag() -> str:
    """Version préfixée "V" (convention de tag Git/GitHub Releases du projet pour le canal Stable, ex."""
    return f"V{get_app_version()}"


def _git_head_short() -> str | None:
    root = _app_root()
    if not (root / ".git").exists():
        return None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=3, check=True,
        )
        return res.stdout.strip() or None
    except Exception:
        return None


def get_build_fingerprint() -> str:
    """Empreinte `version|commit` du code actuellement en cours d'exécution."""
    version = _read_version_uncached()
    commit = _git_head_short() or _read_commit_uncached()
    return f"{version}|{commit}"


def _read_flat_file(name: str) -> str | None:
    for candidate_dir in (_app_root(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent, ROOT_DIR):
        try:
            file = candidate_dir / name
            if file.is_file():
                content = file.read_text(encoding="utf-8").strip()
                if content:
                    return content
        except OSError:
            pass
    return None


def _read_version_uncached() -> str:
    env_ver = os.environ.get("BOBINE_VERSION", "").strip()
    return env_ver.lstrip("vV") if env_ver else (_read_flat_file("VERSION") or _FALLBACK_VERSION)


def _read_commit_uncached() -> str:
    env_commit = os.environ.get("BOBINE_COMMIT", "").strip()
    return env_commit or _read_flat_file("COMMIT") or _FALLBACK_COMMIT
