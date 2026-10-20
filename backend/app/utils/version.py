"""Source de vérité unique du numéro de version ET du commit courant de
l'application.

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
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from app.config import ROOT_DIR

_FALLBACK_VERSION = "5.1.1"
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
    """Numéro de version nu (ex. "3.0.5", ou "3.0.5-canary" sur un build
    d'un canal Bêta/Canary), sans préfixe "V"."""
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


def is_prerelease_version(version: str | None = None) -> bool:
    """Vrai si la version porte un suffixe de pré-release ("4.0.3-beta") —
    marque d'un build des canaux Bêta/Canary (la CI écrit `<base>-beta`/`<base>-canary` dans VERSION,
    cf. ci.yml, étape "Identifiants de build"). Sert à distinguer un build
    Bêta d'une Stable de MÊME numéro de base : sans ça, repasser en Stable
    depuis "4.0.2-beta" n'était jamais proposé (même base que la Stable)."""
    candidate = (version if version is not None else get_app_version()).strip().lstrip("vV")
    return "-" in candidate or "~" in candidate


def rolling_channel_of_version(version: str | None = None) -> str | None:
    """Canal rolling ("beta" ou "canary") dont un build packagé porte le
    suffixe de version ("5.0.0-canary", "5.0.0~beta"), ou None pour une
    Stable. Un suffixe inconnu n'est rattaché à aucun canal plutôt que
    deviné : l'appelant le traite alors comme une Stable."""
    candidate = (version if version is not None else get_app_version()).strip().lstrip("vV")
    suffix = candidate.replace("~", "-").partition("-")[2].lower()
    return suffix if suffix in ("beta", "canary") else None


def _git_head_short() -> str | None:
    """Commit HEAD court du checkout git qui contient l'application, ou None
    (profils packagés sans `.git`, git absent, délai dépassé). Jamais mis en
    cache : l'appelant veut la valeur du code RÉELLEMENT chargé à cet
    instant, c'est tout l'intérêt d'une empreinte comparée avant/après une
    mise à jour."""
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
    """Empreinte `version|commit` du code actuellement en cours d'exécution.

    Comparée avant/après une mise à jour par `update_orchestrator` pour
    déterminer si un redémarrage a réellement installé quelque chose : un
    service qui se relance en plein pipeline (cas NORMAL de toute mise à
    jour qui redémarre son propre processus) ne peut pas écrire lui-même
    l'état "terminé" — l'issue réelle se déduit donc au démarrage suivant.
    Sur l'appliance headless la version de base peut rester identique entre
    deux builds Bêta : le commit git est donc inclus quand il est lisible."""
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
