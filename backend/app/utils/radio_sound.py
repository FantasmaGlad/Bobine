"""Réglages de son d'une sortie radio (égaliseur 5 bandes, basses, loudness, limiteur).

Le TRAITEMENT du son est fait par le lecteur `/radio` (graphe Web Audio du
navigateur) : le serveur ne fait que valider, stocker et diffuser ces réglages,
dans l'état du moteur de la sortie (comme le volume). Aucune bibliothèque, aucun
traitement audio côté serveur.

Validation par BORNAGE et non par rejet : une valeur aberrante (client ancien, JSON
édité à la main) est ramenée dans sa plage plutôt que de faire échouer la commande
— un réglage de son ne doit jamais produire d'erreur serveur. Fonctions pures sur
des `dict`, donc sans dépendance à Pydantic v1/v2 (profil Android).
"""
import json
import logging
import math
from typing import Any

from sqlalchemy.orm import Session

from app.models import Setting

logger = logging.getLogger(__name__)

# 60 Hz (grave), 230 Hz, 910 Hz (médium), 3,6 kHz, 14 kHz (aigu) : fréquences
# appliquées par le lecteur; le serveur ne stocke que les gains (dB).
BAND_COUNT = 5
BAND_GAIN_MIN_DB = -12
BAND_GAIN_MAX_DB = 12
BASS_BOOST_MAX_DB = 12
PRESET_MAX_LENGTH = 40

DEFAULT_SOUND: dict[str, Any] = {
    "enabled": True,
    "bands": [0] * BAND_COUNT,
    "bass_boost": 0,
    "loudness": False,
    "limiter": True,
    # Aucun préréglage par défaut : le son neutre est le réglage « à plat », pas un préréglage.
    "preset": None,
}


def default_sound() -> dict[str, Any]:
    """Copie indépendante des réglages neutres (jamais l'objet partagé)."""
    return {**DEFAULT_SOUND, "bands": list(DEFAULT_SOUND["bands"])}


def _clamp_int(value: Any, low: int, high: int, fallback: int) -> int:
    # bool est un int en Python : True/False ne sont pas des gains valides.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    if value != value:  # NaN
        return fallback
    # floor(x + 0.5) = Math.round de JavaScript (le round() de Python arrondit .5 au pair : 2,5
    # donnerait 2 côté serveur et 3 côté lecteur pour la même valeur).
    return max(low, min(high, math.floor(value + 0.5)))


def _as_bool(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def sanitize_sound(raw: Any, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Réglages valides à partir d'une entrée quelconque. Les champs absents ou
    invalides gardent la valeur de `base` (réglages courants), sinon la valeur neutre."""
    current = base if isinstance(base, dict) else DEFAULT_SOUND
    if not isinstance(raw, dict):
        raw = {}

    bands_in = raw.get("bands")
    current_bands = current.get("bands") or DEFAULT_SOUND["bands"]
    bands: list[int] = []
    for i in range(BAND_COUNT):
        previous = current_bands[i] if i < len(current_bands) else 0
        previous = _clamp_int(previous, BAND_GAIN_MIN_DB, BAND_GAIN_MAX_DB, 0)
        if isinstance(bands_in, list) and i < len(bands_in):
            bands.append(_clamp_int(bands_in[i], BAND_GAIN_MIN_DB, BAND_GAIN_MAX_DB, previous))
        else:
            bands.append(previous)

    preset = raw["preset"] if "preset" in raw else current.get("preset")
    if preset is not None:
        preset = preset.strip()[:PRESET_MAX_LENGTH] if isinstance(preset, str) else None
        preset = preset or None

    return {
        "enabled": _as_bool(raw.get("enabled"), _as_bool(current.get("enabled"), True)),
        "bands": bands,
        "bass_boost": _clamp_int(
            raw.get("bass_boost"), 0, BASS_BOOST_MAX_DB,
            _clamp_int(current.get("bass_boost"), 0, BASS_BOOST_MAX_DB, 0),
        ),
        "loudness": _as_bool(raw.get("loudness"), _as_bool(current.get("loudness"), False)),
        "limiter": _as_bool(raw.get("limiter"), _as_bool(current.get("limiter"), True)),
        "preset": preset,
    }


def sound_setting_key(radio_channel: str) -> str:
    # Import local : radio_manager importe ce module pour les réglages neutres.
    from app.radio_manager import normalize_radio_channel

    return f"radio_sound_{normalize_radio_channel(radio_channel)}"


def load_sound(db: Session, radio_channel: str) -> dict[str, Any]:
    """Réglages persistés d'une sortie, ou réglages neutres si absents/illisibles
    (jamais d'exception : un JSON corrompu ne doit pas empêcher le démarrage)."""
    row = db.query(Setting).filter(Setting.key == sound_setting_key(radio_channel)).first()
    if row is None or not row.value:
        return default_sound()
    try:
        return sanitize_sound(json.loads(row.value))
    except (TypeError, ValueError):
        logger.warning(f"Réglage de son illisible pour {radio_channel}, réglages neutres utilisés")
        return default_sound()


def save_sound(db: Session, radio_channel: str, sound: dict[str, Any]) -> None:
    key = sound_setting_key(radio_channel)
    payload = json.dumps(sanitize_sound(sound))
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is not None:
        row.value = payload
    else:
        db.add(Setting(key=key, value=payload))
    db.commit()


def load_all_sounds_into_managers(db: Session) -> None:
    """Charge les réglages persistés dans l'état de chaque moteur radio (au démarrage)."""
    from app.radio_manager import RADIO_CHANNELS, get_all_radio_managers

    managers = get_all_radio_managers()
    for radio_channel in RADIO_CHANNELS:
        manager = managers.get(radio_channel)
        if manager is not None:
            manager.state["sound"] = load_sound(db, radio_channel)
