"""Activation du composant audio natif (`bobine-media`)."""
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
    """État réel du composant, pour la page Paramètres."""
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
