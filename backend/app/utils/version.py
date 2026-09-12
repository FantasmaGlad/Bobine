"""Source de vérité unique du numéro de version ET du commit courant de
l'application (réf. mission "canal Stable/Bêta").

Repose sur deux fichiers plats, `VERSION` et `COMMIT`, placés à la racine du
dépôt en développement — même racine que `config.toml`, bundlés de la même
façon dans chaque paquet packagé (`datas` des `bobine.spec`). `ROOT_DIR`
(`app.config`) résout déjà correctement cette racine en mode figé (frozen,
PyInstaller) COMME en développement, y compris la particularité macOS
(`Contents/Resources/` vs `Contents/MacOS/`) — le réutiliser ici évite de
dupliquer cette logique, qui échouerait silencieusement si on se basait sur
`__file__` (chemin sans rapport avec le système de fichiers réel une fois le
code Python gelé dans un PYZ, cf. commentaire d'app/config.py).

`COMMIT` n'existe que sur les builds construits par la CI (`ci.yml` l'écrit
juste avant PyInstaller) — absent en développement local et sur l'appliance
headless, qui a de toute façon `git` disponible pour une info plus précise
(cf. `_get_local_version_info()` dans updates.py)."""

import os
import sys
from functools import lru_cache
from pathlib import Path

from app.config import ROOT_DIR

_FALLBACK_VERSION = "3.0.5"
_FALLBACK_COMMIT = "unknown"


def _app_root() -> Path:
    # ROOT_DIR = backend/ en développement (racine du backend, pas du dépôt) ;
    # VERSION/COMMIT vivent à la racine du DÉPÔT — un niveau au-dessus. En
    # mode figé, ROOT_DIR pointe déjà là où le paquet bundle VERSION/COMMIT
    # (même `datas` que config.toml), donc pas de `.parent` en plus ici.
    if getattr(sys, "frozen", False):
        return ROOT_DIR
    return ROOT_DIR.parent


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Numéro de version nu (ex. "3.0.5", ou "3.0.5-beta" sur un build du
    canal Bêta), sans préfixe "V"."""
    # 1. Variable d'environnement injectée par la plateforme (ex: Android BuildConfig.VERSION_NAME)
    env_ver = os.environ.get("BOBINE_VERSION", "").strip()
    if env_ver:
        return env_ver.lstrip("vV")

    # 2. Emplacement standard racine du dépôt / paquet figé
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
    """Commit court (7 caractères) du build courant. Repli "unknown" en
    développement local (pas de fichier COMMIT généré par la CI) — sans
    incidence : `_get_local_version_info()` préfère `git rev-parse`
    directement quand un vrai checkout est disponible."""
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
    """Version préfixée "V" (convention de tag Git/GitHub Releases du projet
    pour le canal Stable, ex. "V3.0.1"), utilisée comme repli quand aucun tag
    Git réel n'est disponible (profils packagés sans checkout, cf.
    updates.py)."""
    return f"V{get_app_version()}"
