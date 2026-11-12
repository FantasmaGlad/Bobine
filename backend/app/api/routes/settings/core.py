"""Socle des réglages : routeur, champs modifiables, valeurs par défaut, modèles de requête, lecture d'une valeur en base."""

import re
from pathlib import Path

from fastapi import (
    APIRouter,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import release_channel
from app.api.contract import CHANNELS, DISPLAY_OUTPUTS_BY_CHANNEL
from app.config import (
    settings as runtime_settings,
)
from app.models import Setting
from app.utils import media_native, themes, tor_proxy, ui_language


def _get_sqlite_db_path() -> Path | None:
    """Résout le chemin absolu du fichier SQLite à partir de database_url."""
    db_url = runtime_settings.database_url
    if db_url.startswith("sqlite:///"):
        path_str = db_url[len("sqlite:///"):]
        return Path(path_str).resolve()
    return None


router = APIRouter(prefix="/api/settings", tags=["settings"])

# Réglages ajustables depuis l'interface, persistés dans la
# table `settings` (clé/valeur) et reflétés immédiatement dans le singleton
# `runtime_settings` en mémoire — le fichier config.toml reste la valeur de
# secours au tout premier démarrage (avant toute modification via l'UI).
_WRITABLE_NUMERIC_FIELDS = {
    "wait_time_between_courses", "volume_default", "audio_chain_timer_seconds",
    "radio_announcement_fade_ms", "logs_retention_days", "default_coach_background_id",
}
_WRITABLE_STRING_FIELDS = {
    "theme", "theme_mode", "language", "active_logo", "update_channel", "wired_display_mode",
    "display_mode_setting", "auto_update_enabled", "auto_update_time",
    "auto_web_rendition", "media_native", "update_tor", "update_tor_proxy", "simplified_ui",
}
_DEFAULTS = {
    # Interface simplifiée : masque coach, métriques et journaux. Réglage portable de settings.json.
    "simplified_ui": "false",
    # « ardoise » en mode automatique (clair ou sombre selon le système) : thème par défaut.
    "theme": themes.DEFAULT_THEME,
    "theme_mode": themes.DEFAULT_MODE,
    "language": "fr",
    "active_logo": "default",
    # Canal de mise à jour : jamais lu d'ici. Sans choix explicite de l'utilisateur, le canal
    # effectif est celui de l'installation (release_channel.resolve) ; l'entrée n'existe que pour
    # l'ensemble des clés de réglages connues ci-dessus.
    "update_channel": release_channel.DEFAULT_CHANNEL,
    # Mode d'affichage câblé :
    # "headless" par défaut (desktop/laptop/wyse), "dual_screen" pour tablette.
    "wired_display_mode": "headless",
    # Rétention des logs d'activité et métriques système en jours
    "logs_retention_days": "7",
    # Mise à jour automatique (Réglages → Mises à jour) : désactivée par
    # défaut — contrairement à la purge de logs ou au relevé télémétrique
    # (jobs de maintenance sans risque), une mise à jour système reste un
    # choix explicite de l'administrateur, jamais l'état de départ d'une
    # installation. L'heure par défaut (3h) est en revanche pré-remplie dès
    # l'activation, cohérente avec les autres tâches de fond nocturnes déjà
    # planifiées à cette heure (cf. `_periodic_purge_logs`).
    "auto_update_enabled": "false",
    "auto_update_time": "03:00",
    "update_tor": "false",
    "update_tor_proxy": tor_proxy.DEFAULT_PROXY,
    # Version web « lisible partout » : désactivée par
    # défaut — c'est un réencodage ffmpeg (plusieurs minutes sur un CPU
    # modeste) que l'administrateur choisit d'activer ; quand elle l'est, la
    # première lecture depuis un navigateur incapable de décoder l'original la
    # déclenche automatiquement (cf. api/routes/media_streams.py::stream_video).
    "auto_web_rendition": "false",
    # Composant audio natif (expérimental) : désactivé par défaut. Il n'accélère que de
    # nouveaux imports et n'altère aucune donnée existante ; tout échec retombe sur
    # ffprobe/ffmpeg. La variable d'environnement BOBINE_MEDIA_NATIVE (1/0) reste un
    # forçage prioritaire (cf. app/utils/media_native.py).
    "media_native": media_native.DEFAULT_VALUE,
}
_AUTO_UPDATE_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_LOGO_FILENAME = "logo.png"
_VALID_THEMES = set(themes.THEMES)
_VALID_THEME_MODES = set(themes.MODES)
_VALID_ACTIVE_LOGOS = {"default", "custom"}
_VALID_WIRED_DISPLAY_MODES = {"dual_screen", "headless"}

# Sortie affichée par CANAL de diffusion : "câblé" (l'écran physiquement connecté au Wyse, en 127.0.0.1) et
# "réseau" (tout autre appareil du LAN qui ouvre /kiosk ou /cinema) sont
# désormais deux réglages INDÉPENDANTS — l'admin peut par exemple laisser le
# câblé en kiosk piloté pendant que le réseau bascule en libre-service
# cinéma, ou l'inverse. "kiosk" par défaut sur les deux canaux. Persisté en
# base sous deux clés distinctes : survit aux redémarrages.
_DISPLAY_OUTPUT_KEYS = {"cable": "display_output_cable", "network": "display_output_network"}
# Sorties acceptées PAR canal de diffusion : seule la sortie câblée peut être
# basculée sur la radio (l'écran physique devient un poste radio, à la demande) ;
# le réseau a déjà son poste radio par URL (/radio?channel=network).
_DISPLAY_OUTPUTS_BY_CHANNEL = DISPLAY_OUTPUTS_BY_CHANNEL
_DISPLAY_CHANNELS = CHANNELS


class DisplayOutputUpdate(BaseModel):
    channel: str
    output: str


class SettingsUpdate(BaseModel):
    wait_time_between_courses: int | None = None
    volume_default: int | None = None
    audio_chain_timer_seconds: int | None = None
    radio_announcement_fade_ms: int | None = None
    logs_retention_days: int | None = None
    default_coach_background_id: int | None = None
    theme: str | None = None
    theme_mode: str | None = None
    language: str | None = None
    active_logo: str | None = None
    update_channel: str | None = None
    wired_display_mode: str | None = None
    # "auto" (dérivé du matériel, défaut) ou forçage "dual_screen"/"headless". Une écriture de `wired_display_mode` par un ancien client
    # est traduite en forçage manuel (cf. update_settings).
    display_mode_setting: str | None = None
    auto_update_enabled: str | None = None
    auto_update_time: str | None = None
    auto_web_rendition: str | None = None
    media_native: str | None = None
    update_tor: str | None = None
    update_tor_proxy: str | None = Field(default=None, max_length=80)
    simplified_ui: str | None = None


def _get_db_value(db: Session, key: str) -> str | None:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else None


def stored_language(db: Session) -> str:
    """Langue enregistrée (valeur par défaut `fr`) ; l'export servi est celui de cette langue au démarrage."""
    value = _get_db_value(db, "language")
    return value if value in ui_language.LANGUAGES else ui_language.DEFAULT_LANGUAGE


def _logo_path() -> Path:
    return Path(runtime_settings.branding_dir) / _LOGO_FILENAME
