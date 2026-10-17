"""Garde-fous d'entrée : code de langue des sous-titres (nom de fichier sur
disque) et dossiers ouvrables par `POST /api/settings/open-path`."""

import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from app.config import settings
from app.routers import settings as settings_router
from app.utils.subtitles import (
    convert_srt_to_vtt,
    normalize_language_code,
    normalize_language_label,
)


@pytest.mark.parametrize("raw,expected", [
    ("fr", "fr"), (" EN ", "en"), ("pt-br", "pt-br"), ("fra", "fra"),
    ("../x", None), ("fr/../../etc", None), ("", None), ("f", None), ("fr\n", "fr"),
    ("a" * 20, None),
])
def test_language_code_never_carries_a_path(raw, expected):
    assert normalize_language_code(raw) == expected


def test_language_label_is_bounded_and_printable():
    assert normalize_language_label("Fran\x00çais\n", "x") == "Français"
    assert normalize_language_label("", "Français") == "Français"
    assert len(normalize_language_label("a" * 200, "x")) == 40


def test_srt_is_converted_to_webvtt():
    out = convert_srt_to_vtt("1\n00:00:01,500 --> 00:00:02,000\nSalut\n")
    assert out.startswith("WEBVTT") and "00:00:01.500 --> 00:00:02.000" in out


def test_open_path_refuses_directories_outside_the_data_roots():
    for outside in ("/etc", "/", str(Path.home())):
        with pytest.raises(HTTPException) as exc:
            settings_router.open_path(settings_router.OpenPathRequest(path=outside))
        assert exc.value.status_code == 403


def test_open_path_does_not_create_missing_directories(tmp_path):
    missing = Path(settings.media_dir).resolve() / "dossier-inexistant-pour-test"
    with pytest.raises(HTTPException) as exc:
        settings_router.open_path(settings_router.OpenPathRequest(path=str(missing)))
    assert exc.value.status_code == 404
    assert not missing.exists()


def test_open_path_opens_a_data_directory(monkeypatch):
    opened = []
    monkeypatch.setattr(settings_router, "is_android", lambda: False)
    monkeypatch.setattr(settings_router.subprocess, "Popen", lambda cmd, **kw: opened.append(cmd))
    target = Path(settings.media_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    result = settings_router.open_path(settings_router.OpenPathRequest(path=str(target)))
    assert result["path"] == str(target)
    assert opened
