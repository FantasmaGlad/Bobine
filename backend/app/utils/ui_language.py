"""Langue de l'interface : un export statique par langue, celui de la langue enregistrée est servi (M27).

Chaque écran ne charge ainsi que ses textes. Changer de langue dans Réglages enregistre le choix ; il s'applique au
redémarrage suivant, après lequel les écrans ouverts se rechargent seuls (changement de `boot_id`).
"""
from __future__ import annotations

from pathlib import Path

from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

LANGUAGES = ("fr", "en")
DEFAULT_LANGUAGE = "fr"

_served: str = DEFAULT_LANGUAGE


def served() -> str:
    """Langue de l'export servi depuis le démarrage du processus."""
    return _served


def set_served(language: str | None) -> str:
    global _served
    _served = language if language in LANGUAGES else DEFAULT_LANGUAGE
    return _served


def build_dir(root: Path, language: str) -> Path:
    """Dossier de l'export de `language` ; à défaut, la racine (export unique d'une version antérieure)."""
    for name in (language, *(other for other in LANGUAGES if other != language)):
        if (root / name / "index.html").exists():
            return root / name  # export d'une autre langue plutôt qu'une page 404 (construction partielle)
    return root


SHARED_DIR = "_shared"


class LanguageFrontend:
    """Sert le frontend de la langue du démarrage ; chaque export a son propre `StaticFiles`.

    Les fichiers identiques dans les deux exports (JS et CSS hors dictionnaire, images, polices) ne sont stockés
    qu'une fois, dans `_shared` (frontend/scripts/share-assets.mjs) : ils sont cherchés après le dossier de la langue,
    sous le même chemin d'URL."""

    def __init__(self, root: Path, factory: type[StaticFiles]) -> None:
        self.root = root
        self.apps: dict[str, ASGIApp] = {}
        shared = root / SHARED_DIR
        for language in LANGUAGES:
            app = factory(directory=str(build_dir(root, language)), html=True)
            if shared.is_dir():
                app.all_directories.append(shared)  # type: ignore[attr-defined]
            self.apps[language] = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.apps[served()](scope, receive, send)
