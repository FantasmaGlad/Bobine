"""Thèmes de l'interface : neuf couleurs, chacune en clair et en sombre (palettes de la refonte L7).

Le thème (`theme`) désigne la couleur, le mode (`theme_mode`) le clair, le sombre ou le réglage du système.
`frontend/src/lib/themePalettes.ts` en tient la liste côté interface ; `backend/tests/test_themes.py` vérifie qu'elles
sont identiques. Les anciens noms (15 thèmes d'avant la 5.2) sont traduits en couleur + mode à la lecture.
"""
from __future__ import annotations

THEMES = ("ardoise", "chili", "canary", "rose-vif", "charbon", "orchidee", "foret", "ocean", "pumpkin")
MODES = ("auto", "light", "dark")
DEFAULT_THEME = "ardoise"
DEFAULT_MODE = "auto"

# Ancien thème -> (couleur, mode) le plus proche : même famille de teinte et même clarté.
LEGACY_THEMES: dict[str, tuple[str, str]] = {
    "clair": ("chili", "light"), "charbon-sombre": ("charbon", "dark"), "charbon": ("charbon", "light"),
    "miel": ("pumpkin", "light"), "menthe": ("foret", "light"), "ciel": ("ocean", "light"),
    "lavande": ("orchidee", "light"), "beige": ("ardoise", "light"), "coco": ("pumpkin", "light"),
    "automne": ("pumpkin", "dark"), "hiver": ("ocean", "dark"), "lune": ("ardoise", "dark"),
    "chili": ("chili", "dark"), "orchidee": ("orchidee", "dark"), "taupe": ("canary", "dark"),
}


def resolve(theme: str | None, mode: str | None) -> tuple[str, str]:
    """Couleur et mode effectifs d'après les valeurs stockées : un ancien nom donne sa couleur et son mode, une valeur
    inconnue retombe sur le défaut. Un mode déjà choisi explicitement n'est pas écrasé par la traduction d'un ancien nom."""
    if theme in LEGACY_THEMES:
        legacy_theme, legacy_mode = LEGACY_THEMES[theme]
        return legacy_theme, mode if mode in MODES and mode != DEFAULT_MODE else legacy_mode
    return (theme if theme in THEMES else DEFAULT_THEME), (mode if mode in MODES else DEFAULT_MODE)
