"""Thèmes de l'interface : neuf couleurs, chacune en clair et en sombre."""
from __future__ import annotations

THEMES = ("ardoise", "chili", "canary", "rose-vif", "charbon", "orchidee", "foret", "ocean", "pumpkin")
MODES = ("auto", "light", "dark")
DEFAULT_THEME = "ardoise"
DEFAULT_MODE = "auto"

LEGACY_THEMES: dict[str, tuple[str, str]] = {
    "clair": ("chili", "light"), "charbon-sombre": ("charbon", "dark"), "charbon": ("charbon", "light"),
    "miel": ("pumpkin", "light"), "menthe": ("foret", "light"), "ciel": ("ocean", "light"),
    "lavande": ("orchidee", "light"), "beige": ("ardoise", "light"), "coco": ("pumpkin", "light"),
    "automne": ("pumpkin", "dark"), "hiver": ("ocean", "dark"), "lune": ("ardoise", "dark"),
    "chili": ("chili", "dark"), "orchidee": ("orchidee", "dark"), "taupe": ("canary", "dark"),
}


def legacy_target(theme: str | None, mode: str | None) -> tuple[str, str] | None:
    """Couleur et mode d'un ancien nom de thème, ou None si `theme` est un nom actuel."""
    if theme not in LEGACY_THEMES:
        return None
    legacy_theme, legacy_mode = LEGACY_THEMES[theme]
    if theme in THEMES:
        return None if mode in MODES else (legacy_theme, legacy_mode)
    return legacy_theme, (mode if mode in ("light", "dark") else legacy_mode)


def resolve(theme: str | None, mode: str | None) -> tuple[str, str]:
    """Couleur et mode effectifs d'après les valeurs stockées ; une valeur inconnue retombe sur le défaut."""
    legacy = legacy_target(theme, mode)
    if legacy:
        return legacy
    return (theme if theme in THEMES else DEFAULT_THEME), (mode if mode in MODES else DEFAULT_MODE)
