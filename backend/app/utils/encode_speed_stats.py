"""Historique de vitesse d'encodage ffmpeg (réf. mission "estimation de la
durée d'importation et de réencodage") : mémorise, par couple (encodeur,
palier de résolution), la vitesse moyenne réellement observée (en multiple du
temps réel, ex. 2.5 = deux fois et demi plus vite que la durée de la vidéo)
sur les imports précédents. Permet d'afficher une estimation AVANT même que
ffmpeg n'ait démarré et n'émette sa propre progression en direct (laquelle
reste la source de vérité dès qu'elle est disponible, cf.
video_utils._run_ffmpeg_with_progress).

Persisté dans la table `settings` (clé/valeur déjà utilisée ailleurs dans le
backend) plutôt que dans un nouveau fichier ou une nouvelle table : pas de
migration Alembic nécessaire, et l'historique survit aux redémarrages.
"""

import json
import logging

from app.database import SessionLocal
from app.models import Setting

logger = logging.getLogger(__name__)

_SETTING_PREFIX = "encode_speed_stats:"
# Moyenne mobile exponentielle : réagit vite aux imports récents (changement
# de matériel, source différente) sans qu'un unique échantillon aberrant ne
# fausse durablement l'estimation.
_EMA_ALPHA = 0.3

# Repères de départ tant qu'aucun échantillon n'a encore été enregistré pour
# ce couple (encodeur, résolution) — ordres de grandeur prudents (plutôt sous-
# estimer la vitesse, donc sur-estimer le temps, qu'annoncer un temps trop
# court aux utilisateurs).
_DEFAULT_SPEED_BY_ENCODER = {
    "h264_mediacodec": 2.0,
    "h264_videotoolbox": 3.0,
    "h264_vaapi": 2.5,
    # Repère de départ identique à h264_vaapi : même matériel Intel
    # QuickSync sous-jacent, caractéristiques de performance comparables.
    # Sans cette entrée, `get_estimated_speed` retombait sur 1.0 (le repli
    # générique) — sous-estimant la vitesse réelle jusqu'au premier
    # échantillon enregistré.
    "h264_qsv": 2.5,
    "libx264": 1.0,
}


def resolution_bucket(width: int | None, height: int | None) -> str:
    """Même paliers que `_get_target_bitrate` (video_utils.py) : la vitesse
    d'encodage dépend avant tout de la résolution source, pas de sa valeur
    exacte en pixels."""
    w = width or 1920
    h = height or 1080
    pixels = w * h
    if pixels >= 3840 * 2160 * 0.8:
        return "4k"
    if pixels >= 2560 * 1440 * 0.8:
        return "2k"
    return "1080p"


def _key(encoder_name: str, bucket: str) -> str:
    return f"{_SETTING_PREFIX}{encoder_name}:{bucket}"


def get_estimated_speed(encoder_name: str, bucket: str) -> float:
    """Vitesse moyenne (x temps réel) observée pour ce couple (encodeur,
    résolution), ou un repère par défaut tant qu'aucun échantillon n'existe."""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == _key(encoder_name, bucket)).first()
        if row:
            try:
                speed = float(json.loads(row.value).get("avg_speed"))
                if speed > 0:
                    return speed
            except (ValueError, TypeError, AttributeError):
                pass
    finally:
        db.close()
    return _DEFAULT_SPEED_BY_ENCODER.get(encoder_name, 1.0)


def record_speed_sample(encoder_name: str, bucket: str, speed_factor: float) -> None:
    """Met à jour la moyenne mobile de vitesse d'encodage pour ce couple
    (encodeur, résolution) — appelé après chaque réencodage réussi."""
    if not speed_factor or speed_factor <= 0:
        return
    key = _key(encoder_name, bucket)
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            try:
                prev = float(json.loads(row.value).get("avg_speed", speed_factor))
            except (ValueError, TypeError, AttributeError):
                prev = speed_factor
            new_avg = prev + _EMA_ALPHA * (speed_factor - prev)
            row.value = json.dumps({"avg_speed": round(new_avg, 3)})
        else:
            db.add(Setting(key=key, value=json.dumps({"avg_speed": round(speed_factor, 3)})))
        db.commit()
    except Exception as e:
        logger.warning(f"Impossible d'enregistrer l'échantillon de vitesse d'encodage ({key}): {e}")
        db.rollback()
    finally:
        db.close()
