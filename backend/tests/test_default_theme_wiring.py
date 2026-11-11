"""Le thème par défaut doit être le même partout où il est décidé : réglage serveur, état initial de l'interface web,
couleur du navigateur et écran de chargement Android (qui s'affiche avant que l'interface web existe). Les couleurs
viennent de `themes.css`, généré depuis `themePalettes.ts` : rien n'est recopié à la main."""

import re
from pathlib import Path

from app.api.routes import settings
from app.utils import themes

REPO = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def _default_light_tokens() -> dict[str, str]:
    css = _read("frontend/src/app/themes.css")
    block = re.search(rf':root\[data-theme="{themes.DEFAULT_THEME}"\]\[data-mode="light"\]\s*\{{(.*?)\n\}}', css, re.S).group(1)
    return {name: value.lower() for name, value in re.findall(r"(--(?:bg-main|text-main|accent-primary)):\s*(#[0-9a-fA-F]{6})", block)}


def test_theme_par_defaut_du_serveur_et_de_l_interface():
    assert settings._DEFAULTS["theme"] == themes.DEFAULT_THEME and settings._DEFAULTS["theme_mode"] == themes.DEFAULT_MODE
    palettes = _read("frontend/src/lib/themePalettes.ts")
    assert f'DEFAULT_THEME: ThemeId = "{themes.DEFAULT_THEME}"' in palettes
    assert f'DEFAULT_MODE: ThemeMode = "{themes.DEFAULT_MODE}"' in palettes
    layout = _read("frontend/src/app/layout.tsx")
    assert "data-theme={DEFAULT_THEME}" in layout, "le <html> initial doit porter le thème par défaut (sinon flash d'un autre thème)"


def test_couleur_du_navigateur_et_ecran_de_chargement_android_reprennent_les_jetons_du_defaut():
    tokens = _default_light_tokens()
    assert {"--bg-main", "--text-main", "--accent-primary"} <= tokens.keys()
    layout = _read("frontend/src/app/layout.tsx")
    assert 'paletteOf(DEFAULT_THEME, "light").bg' in layout and 'paletteOf(DEFAULT_THEME, "dark").bg' in layout
    kotlin = _read("android/app/src/main/java/com/bobine/app/NativeBridge.kt")
    for const, token in (("DEFAULT_BACKGROUND", "--bg-main"), ("DEFAULT_TEXT", "--text-main"), ("DEFAULT_ACCENT", "--accent-primary")):
        match = re.search(rf'{const}\s*=\s*"(#[0-9a-fA-F]{{6}})"', kotlin)
        assert match and match.group(1).lower() == tokens[token], f"{const} doit valoir {token} du thème par défaut ({tokens[token]})"
    assert "UI_MODE_NIGHT" not in kotlin, "l'écran de chargement par défaut ne dépend pas du mode sombre du système"
