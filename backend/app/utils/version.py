"""Source de vérité unique du numéro de version de l'application (réf.
mission "canal Stable/Bêta") : lit le fichier VERSION à la racine du dépôt,
partagé avec install.sh et les scripts de packaging (build_deb.sh,
build_app.sh, bobine.iss) — évite que chaque profil garde sa propre copie
codée en dur, comme c'était le cas avant (main.py, updates.py, le manifeste
de sauvegarde de settings.py divergeaient chacun indépendamment)."""

from functools import lru_cache
from pathlib import Path

_FALLBACK_VERSION = "3.0.1"
_VERSION_FILE = Path(__file__).resolve().parent.parent.parent.parent / "VERSION"


@lru_cache(maxsize=1)
def get_app_version() -> str:
    """Numéro de version nu (ex. "3.0.1"), sans préfixe "V"."""
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip() or _FALLBACK_VERSION
    except OSError:
        return _FALLBACK_VERSION


def get_app_tag() -> str:
    """Version préfixée "V" (convention de tag Git/GitHub Releases du projet,
    ex. "V3.0.1"), utilisée comme repli quand aucun tag Git réel n'est
    disponible (profils packagés sans checkout, cf. updates.py)."""
    return f"V{get_app_version()}"
