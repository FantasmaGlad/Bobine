"""Le thème par défaut (« lavande », clair) doit être le même partout où il est décidé :
réglage serveur, état initial de l'interface web, couleur du navigateur et écran de chargement
Android (qui s'affiche avant que l'interface web existe). Une divergence se voit au premier
lancement : écran de chargement sombre ou rouge avant l'interface lavande."""

import re
from pathlib import Path

from app.routers import settings

REPO = Path(__file__).resolve().parents[2]
THEME = "lavande"


def _read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def _lavande_tokens() -> dict[str, str]:
    css = _read("frontend/src/app/globals.css")
    block = re.search(r':root\[data-theme="lavande"\]\s*\{(.*?)\n\}', css, re.S).group(1)
    return {name: value.lower() for name, value in re.findall(r"(--(?:bg-main|text-main|accent-primary)):\s*(#[0-9a-fA-F]{6})", block)}


def test_theme_par_defaut_du_serveur_et_de_l_interface():
    assert settings._DEFAULTS["theme"] == THEME
    assert f'const DEFAULT_THEME: Theme = "{THEME}"' in _read("frontend/src/lib/AppSettingsContext.tsx")
    layout = _read("frontend/src/app/layout.tsx")
    assert f'data-theme="{THEME}"' in layout, "le <html> initial doit porter le thème par défaut (sinon flash d'un autre thème)"


def test_couleur_du_navigateur_et_ecran_de_chargement_android_reprennent_les_jetons_lavande():
    tokens = _lavande_tokens()
    assert {"--bg-main", "--text-main", "--accent-primary"} <= tokens.keys()
    assert f'themeColor: "{tokens["--bg-main"]}"' in _read("frontend/src/app/layout.tsx")
    kotlin = _read("android/app/src/main/java/com/bobine/app/NativeBridge.kt")
    for const, token in (("DEFAULT_BACKGROUND", "--bg-main"), ("DEFAULT_TEXT", "--text-main"), ("DEFAULT_ACCENT", "--accent-primary")):
        match = re.search(rf'{const}\s*=\s*"(#[0-9a-fA-F]{{6}})"', kotlin)
        assert match and match.group(1).lower() == tokens[token], f"{const} doit valoir {token} de lavande ({tokens[token]})"
    assert "UI_MODE_NIGHT" not in kotlin, "le thème par défaut ne dépend pas du mode sombre du système"
