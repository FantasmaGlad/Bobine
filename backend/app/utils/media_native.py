"""Activation du composant audio natif (`bobine-media`).

Deux sources, par ordre de priorité :

1. la variable d'environnement `BOBINE_MEDIA_NATIVE` : `1` force l'activation, `0` la
   désactive ; toute autre valeur (ou l'absence de variable) laisse la main au réglage ;
2. le réglage `media_native` (table `settings`, `"true"`/`"false"`, **désactivé par
   défaut**), modifiable depuis Réglages. C'est la seule voie possible sur Android, où
   l'on ne pose pas de variable d'environnement.

Le composant n'accélère que de nouveaux imports : il n'altère aucune donnée existante, et
tout échec (binaire absent, format hors périmètre, erreur de protocole, délai dépassé)
retombe sur le chemin historique ffprobe/ffmpeg + Pillow, sans perte de média.

L'état est tenu en mémoire (les importeurs tournent dans des threads qui ne disposent pas
d'une session de base de données) : il est chargé au démarrage et mis à jour à chaque
écriture du réglage.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

ENV_VARIABLE = "BOBINE_MEDIA_NATIVE"
SETTING_KEY = "media_native"
DEFAULT_VALUE = "false"

_lock = threading.Lock()
_setting_enabled = False


def parse_setting(value: Any) -> bool:
    """`"true"` seulement : toute autre valeur stockée vaut « désactivé »."""
    return isinstance(value, str) and value.strip().lower() == "true"


def configure(value: Any) -> None:
    """Reflète le réglage persisté (appelé au démarrage et à chaque écriture)."""
    global _setting_enabled
    enabled = value if isinstance(value, bool) else parse_setting(value)
    with _lock:
        previous, _setting_enabled = _setting_enabled, enabled
    if previous and not enabled:
        # Désactivé à chaud : le processus natif ne doit pas survivre inutilement. Import
        # différé : ce module est importé par l'adaptateur.
        from app.utils.media_sidecar import close_current_media_client

        close_current_media_client()


def load_from_database(db) -> None:
    """Lit le réglage dans la table `settings` (session SQLAlchemy ouverte par l'appelant)."""
    from app.models import Setting

    row = db.query(Setting).filter(Setting.key == SETTING_KEY).first()
    configure(row.value if row else DEFAULT_VALUE)


def env_override() -> bool | None:
    """`True` / `False` si l'environnement impose un choix, `None` s'il laisse le réglage décider."""
    value = os.environ.get(ENV_VARIABLE)
    if value == "1":
        return True
    if value == "0":
        return False
    return None


def setting_enabled() -> bool:
    with _lock:
        return _setting_enabled


def is_enabled() -> bool:
    override = env_override()
    return override if override is not None else setting_enabled()


def source() -> str:
    """`env` (forçage), `setting` (réglage explicitement activé) ou `default`."""
    if env_override() is not None:
        return "env"
    return "setting" if setting_enabled() else "default"


def status() -> dict[str, Any]:
    """État réel du composant, pour la page Paramètres.

    `state` :
    - `disabled` : non demandé (le processus n'est pas lancé pour le savoir) ;
    - `absent` : demandé, mais aucun exécutable joignable ;
    - `active` : demandé, lancé, et il répond à `hello` (protocole accepté) ;
    - `fallback` : demandé et présent mais inutilisable (échec de lancement, protocole
      refusé, délai) — les imports utilisent le chemin historique.
    Un format ou un fichier que le composant ne sait pas lire ne change pas cet état : il
    est traité par le chemin historique, fichier par fichier.
    """
    from app.utils.media_sidecar import find_binary, get_media_client

    enabled = is_enabled()
    binary = find_binary()
    result: dict[str, Any] = {
        "enabled": enabled,
        "setting": setting_enabled(),
        "source": source(),
        "forced_by_env": env_override(),
        "available": binary is not None,
        "state": "disabled",
        "binary_version": None,
        "formats": [],
        "reason": None,
    }
    if not enabled:
        return result
    if binary is None:
        result.update(state="absent", reason="missing")
        return result
    client = get_media_client()
    hello = client.check()
    if hello is None:
        result.update(state="fallback", reason=client.last_failure or "unavailable")
        return result
    result.update(state="active", binary_version=hello["binary_version"], formats=hello["formats"])
    return result
