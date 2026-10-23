"""Table de mixage applicative d'une sortie radio (phase 3 des périphériques).

Comme pour le son (`radio_sound.py`), le TRAITEMENT est fait par le lecteur `/radio` (graphe Web Audio) : le serveur
valide, stocke et diffuse les réglages dans l'état du moteur de la sortie (champ `mix`). Aucun traitement audio côté serveur.

Trois tranches par sortie radio : « Musique » (son = `radio_sound`, déjà existant), « Rappels » (avec leur propre égaliseur,
neutre par défaut) et « Sortie » (gain et mute après les deux). Gain en dB par pas de 1, mute, solo.

Validation par BORNAGE et non par rejet (client ancien, JSON édité à la main) : un réglage de mixage ne produit jamais d'erreur
serveur. Fonctions pures sur des `dict` (profil Android : pas de dépendance à Pydantic v1/v2).
"""
import json
import logging
import math
from typing import Any

from sqlalchemy.orm import Session

from app.models import Setting
from app.utils.radio_sound import default_sound, sanitize_sound

logger = logging.getLogger(__name__)

GAIN_MIN_DB = -40
GAIN_MAX_DB = 6
STRIPS = ("music", "announcements")


def default_mix() -> dict[str, Any]:
    """Réglages neutres (jamais l'objet partagé)."""
    return {
        "master": {"gain_db": 0, "muted": False},
        "music": {"gain_db": 0, "muted": False, "solo": False},
        "announcements": {"gain_db": 0, "muted": False, "solo": False, "sound": default_sound()},
    }


def _gain(value: Any, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        return fallback
    # floor(x + 0.5) = Math.round de JavaScript (le round() de Python arrondit .5 au pair)
    return max(GAIN_MIN_DB, min(GAIN_MAX_DB, math.floor(value + 0.5)))


def _flag(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def sanitize_mix(raw: Any, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Réglages valides à partir d'une entrée quelconque ; champs absents ou invalides = valeur de `base` (réglages courants),
    sinon valeur neutre."""
    neutral = default_mix()
    current = base if isinstance(base, dict) else neutral
    data = raw if isinstance(raw, dict) else {}

    def section(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        incoming = data.get(name)
        previous = current.get(name)
        return (incoming if isinstance(incoming, dict) else {}), (previous if isinstance(previous, dict) else neutral[name])

    master_in, master_prev = section("master")
    result: dict[str, Any] = {
        "master": {
            "gain_db": _gain(master_in.get("gain_db"), _gain(master_prev.get("gain_db"), 0)),
            "muted": _flag(master_in.get("muted"), _flag(master_prev.get("muted"), False)),
        }
    }
    for strip in STRIPS:
        incoming, previous = section(strip)
        entry: dict[str, Any] = {
            "gain_db": _gain(incoming.get("gain_db"), _gain(previous.get("gain_db"), 0)),
            "muted": _flag(incoming.get("muted"), _flag(previous.get("muted"), False)),
            "solo": _flag(incoming.get("solo"), _flag(previous.get("solo"), False)),
        }
        if strip == "announcements":
            entry["sound"] = sanitize_sound(incoming.get("sound"), base=previous.get("sound") if isinstance(previous.get("sound"), dict) else None)
        result[strip] = entry
    return result


def mix_setting_key(radio_channel: str) -> str:
    # Import local : radio_manager importe ce module pour les réglages neutres.
    from app.radio_manager import normalize_radio_channel

    return f"radio_mix_{normalize_radio_channel(radio_channel)}"


def load_mix(db: Session, radio_channel: str) -> dict[str, Any]:
    """Réglages persistés d'une sortie, ou réglages neutres (jamais d'exception : un JSON corrompu ne bloque pas le démarrage)."""
    row = db.query(Setting).filter(Setting.key == mix_setting_key(radio_channel)).first()
    if row is None or not row.value:
        return default_mix()
    try:
        return sanitize_mix(json.loads(row.value))
    except (TypeError, ValueError):
        logger.warning("Réglage de mixage illisible pour %s, réglages neutres utilisés", radio_channel)
        return default_mix()


def save_mix(db: Session, radio_channel: str, mix: dict[str, Any]) -> None:
    key = mix_setting_key(radio_channel)
    payload = json.dumps(sanitize_mix(mix))
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is not None:
        row.value = payload
    else:
        db.add(Setting(key=key, value=payload))
    db.commit()


def load_all_mixes_into_managers(db: Session) -> None:
    """Charge les mixages persistés dans l'état de chaque moteur radio (au démarrage)."""
    from app.radio_manager import RADIO_CHANNELS, get_all_radio_managers

    managers = get_all_radio_managers()
    for radio_channel in RADIO_CHANNELS:
        manager = managers.get(radio_channel)
        if manager is not None:
            manager.state["mix"] = load_mix(db, radio_channel)


def sanitize_levels(raw: Any) -> dict[str, int]:
    """Niveaux du vumètre rapportés par le lecteur : `{tranche: 0..100}` pour les seules tranches connues."""
    if not isinstance(raw, dict):
        return {}
    levels: dict[str, int] = {}
    for name in ("music", "announcements", "master"):
        value = raw.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            continue
        levels[name] = max(0, min(100, int(round(value))))
    return levels
