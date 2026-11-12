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
    db_url = runtime_settings.database_url
    if db_url.startswith("sqlite:///"):
        path_str = db_url[len("sqlite:///"):]
        return Path(path_str).resolve()
    return None


router = APIRouter(prefix="/api/settings", tags=["settings"])

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
    "simplified_ui": "false",
    "theme": themes.DEFAULT_THEME,
    "theme_mode": themes.DEFAULT_MODE,
    "language": "fr",
    "active_logo": "default",
    "update_channel": release_channel.DEFAULT_CHANNEL,
    "wired_display_mode": "headless",
    "logs_retention_days": "7",
    "auto_update_enabled": "false",
    "auto_update_time": "03:00",
    "update_tor": "false",
    "update_tor_proxy": tor_proxy.DEFAULT_PROXY,
    "auto_web_rendition": "false",
    "media_native": media_native.DEFAULT_VALUE,
}
_AUTO_UPDATE_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_LOGO_FILENAME = "logo.png"
_VALID_THEMES = set(themes.THEMES)
_VALID_THEME_MODES = set(themes.MODES)
_VALID_ACTIVE_LOGOS = {"default", "custom"}
_VALID_WIRED_DISPLAY_MODES = {"dual_screen", "headless"}

_DISPLAY_OUTPUT_KEYS = {"cable": "display_output_cable", "network": "display_output_network"}
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
