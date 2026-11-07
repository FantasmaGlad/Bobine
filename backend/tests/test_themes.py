"""Thèmes : liste identique côté serveur et côté interface, anciens noms traduits, réglage `theme_mode` validé."""
import os
import re
from pathlib import Path

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.utils import themes  # noqa: E402

PALETTES = Path(__file__).resolve().parents[2] / "frontend/src/lib/themePalettes.ts"


def _ts():
    return PALETTES.read_text(encoding="utf-8")


def test_themes_et_modes_identiques_cote_interface():
    ids = tuple(re.findall(r'\{ id: "([\w-]+)", labelKey', _ts()))
    assert ids == themes.THEMES
    legacy = {name: (theme, mode) for name, theme, mode in re.findall(r'"?([\w-]+)"?: \{ theme: "([\w-]+)", mode: "(\w+)" \}', _ts())}
    assert legacy == themes.LEGACY_THEMES


def test_chaque_ancien_theme_donne_une_couleur_valide():
    assert len(themes.LEGACY_THEMES) == 15
    for theme, mode in themes.LEGACY_THEMES.values():
        assert theme in themes.THEMES and mode in ("light", "dark")


@pytest.mark.parametrize("stored, mode, expected", [
    ("lavande", None, ("orchidee", "light")),
    ("hiver", None, ("ocean", "dark")),
    ("chili", None, ("chili", "dark")),  # nom déjà existant : sans mode enregistré, c'est l'ancien thème sombre
    ("chili", "auto", ("chili", "auto")),  # avec un mode enregistré, c'est le nouveau thème
    ("orchidee", "light", ("orchidee", "light")),
    ("foret", "dark", ("foret", "dark")),
    ("inconnu", "zzz", ("ardoise", "auto")),
    (None, None, ("ardoise", "auto")),
])
def test_resolve(stored, mode, expected):
    assert themes.resolve(stored, mode) == expected


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_le_serveur_traduit_un_ancien_theme_et_valide_le_mode(client):
    original = client.get("/api/settings").json()
    try:
        assert client.put("/api/settings", json={"theme_mode": "nuit"}).status_code == 400
        assert client.put("/api/settings", json={"theme": "violet"}).status_code == 400
        assert client.put("/api/settings", json={"theme": "lavande"}).status_code == 200  # ancien client
        got = client.get("/api/settings").json()
        assert (got["theme"], got["theme_mode"]) == ("orchidee", "light")
        assert client.put("/api/settings", json={"theme": "ocean", "theme_mode": "dark"}).status_code == 200
        got = client.get("/api/settings").json()
        assert (got["theme"], got["theme_mode"]) == ("ocean", "dark")
    finally:
        client.put("/api/settings", json={"theme": original["theme"], "theme_mode": original["theme_mode"]})
