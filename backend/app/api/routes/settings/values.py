"""Lecture et écriture des réglages, logo personnalisé, état du composant audio natif."""

import logging
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import release_channel
from app.api.contract import SETTING_BOUNDS
from app.config import (
    settings as runtime_settings,
)
from app.database import get_db
from app.models import Setting
from app.utils import media_native, themes, tor_proxy, tor_socks, ui_language
from app.utils.deployment import (
    get_deployment_profile,
    get_profile_handler,
    resolve_update_channel,
)
from app.utils.display_state import (
    VALID_DISPLAY_MODE_SETTINGS,
    get_hardware_state,
)
from app.utils.mdns import get_status as get_mdns_status
from app.utils.network import lan_addresses
from app.utils.port import active_port
from app.utils.ws_manager import manager as ws_manager

from .access import _access_links, _get_local_ip, _mdns_url, _port80_redirect
from .core import (
    _AUTO_UPDATE_TIME_RE,
    _DEFAULTS,
    _VALID_ACTIVE_LOGOS,
    _VALID_THEME_MODES,
    _VALID_THEMES,
    _VALID_WIRED_DISPLAY_MODES,
    _WRITABLE_NUMERIC_FIELDS,
    _WRITABLE_STRING_FIELDS,
    SettingsUpdate,
    _get_db_value,
    _logo_path,
    router,
)
from .wired_mode import get_display_mode_setting, get_effective_wired_display_mode

logger = logging.getLogger(__name__)


def _int_setting(db: Session, key: str, fallback: int) -> int:
    try:
        return int(_get_db_value(db, key) or _DEFAULTS[key])
    except ValueError:
        return fallback


def _flag(db: Session, key: str) -> str:
    return "true" if _get_db_value(db, key) == "true" else "false"


def _playback_settings(db: Session) -> dict[str, Any]:
    default_bg_str = _get_db_value(db, "default_coach_background_id")
    return {
        "wait_time_between_courses": runtime_settings.wait_time_between_courses,
        "volume_default": runtime_settings.volume_default,
        "audio_chain_timer_seconds": runtime_settings.audio_chain_timer_seconds,
        "logs_retention_days": _int_setting(db, "logs_retention_days", 7),
        "default_coach_background_id": int(default_bg_str) if default_bg_str and default_bg_str.isdigit() else None,
    }


def _profile_settings(db: Session) -> dict[str, Any]:
    profile = get_profile_handler()
    return {
        "deployment_profile": get_deployment_profile(),
        "store_managed": profile.is_store_managed(),
        "auto_update_supported": profile.can_schedule_auto_apply(),
        "update_tor_supported": profile.supports_update_over_tor(),
        "update_tor": _flag(db, "update_tor"),
        "update_tor_proxy": _get_db_value(db, "update_tor_proxy") or _DEFAULTS["update_tor_proxy"],
    }


def _appearance_settings(db: Session) -> dict[str, Any]:
    theme, theme_mode = themes.resolve(_get_db_value(db, "theme"), _get_db_value(db, "theme_mode"))
    language = _get_db_value(db, "language") or _DEFAULTS["language"]
    has_custom = _logo_path().exists()
    active_logo = _get_db_value(db, "active_logo") or _DEFAULTS["active_logo"]
    if active_logo == "custom" and not has_custom:
        active_logo = "default"
    return {
        "theme": theme,
        "theme_mode": theme_mode,
        "language": language,
        "ui_language": ui_language.served(),
        "language_restart_required": language != ui_language.served(),
        "restart_guaranteed": get_profile_handler().restart_is_guaranteed(),
        "simplified_ui": _flag(db, "simplified_ui"),
        "has_custom_logo": has_custom,
        "active_logo": active_logo,
    }


def _channel_and_display_settings(db: Session) -> dict[str, Any]:
    channel_choice = resolve_update_channel(_get_db_value(db, "update_channel"))
    return {
        "update_channel": channel_choice.effective,
        "update_channel_source": channel_choice.source,
        "install_channel": channel_choice.install,
        "wired_display_mode": get_effective_wired_display_mode(db),
        "display_mode_setting": get_display_mode_setting(db),
        "display_external_count": get_hardware_state().external_count,
        "auto_update_enabled": _get_db_value(db, "auto_update_enabled") or _DEFAULTS["auto_update_enabled"],
        "auto_update_time": _get_db_value(db, "auto_update_time") or _DEFAULTS["auto_update_time"],
        "auto_web_rendition": _get_db_value(db, "auto_web_rendition") or _DEFAULTS["auto_web_rendition"],
        "media_native": "true" if media_native.parse_setting(_get_db_value(db, "media_native")) else "false",
    }


def _network_settings() -> dict[str, Any]:
    return {
        "local_ip": _get_local_ip(),
        "local_ips": [{"ip": a.ip, "interface": a.interface} for a in lan_addresses()],
        "port": active_port(),
        "mdns_url": _mdns_url(),
        "port80_redirect": _port80_redirect(),
        "access": _access_links(),
        "mdns_status": get_mdns_status().get("state"),
    }


_PATH_SETTINGS = (
    "database_url", "media_dir", "watch_dir", "thumbnails_dir", "backgrounds_dir", "backgrounds_watch_dir", "audio_dir",
    "audio_watch_dir", "radio_dir", "radio_watch_dir", "radio_covers_dir", "radio_announcements_dir", "branding_dir",
    "logs_dir", "subtitles_dir",
)


@router.get("")
def get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        **_playback_settings(db),
        **_profile_settings(db),
        **_appearance_settings(db),
        **_channel_and_display_settings(db),
        "network": _network_settings(),
        "radio_announcement_duck_level": runtime_settings.radio_announcement_duck_level,
        "radio_announcement_fade_ms": runtime_settings.radio_announcement_fade_ms,
        "paths": {key: getattr(runtime_settings, key) for key in _PATH_SETTINGS},
    }


@router.get("/media-native")
async def get_media_native_status() -> dict[str, Any]:
    """État réel du composant audio natif : désactivé, actif, en repli ou absent."""
    return await run_in_threadpool(media_native.status)


@router.put("")
async def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    updates = settings_updates(payload)
    if not updates:
        raise HTTPException(status_code=422, detail="Aucun paramètre fourni")
    stage_settings(updates, db)
    db.commit()
    logger.info("Paramètres mis à jour : %s", ", ".join(sorted(updates)))
    return await after_settings_change(updates, db)


def settings_updates(payload: SettingsUpdate) -> dict[str, Any]:
    """Champs fournis, convertis par le modèle ; `wired_display_mode` (ancien client) vaut choix manuel du mode."""
    dump = getattr(payload, "model_dump", None) or payload.dict
    updates = dump(exclude_unset=True)
    if updates.get("wired_display_mode") and "display_mode_setting" not in updates:
        updates["display_mode_setting"] = updates["wired_display_mode"]
    return updates


_BOOLEAN_TEXT = ("true", "false")


def _string_choices() -> dict[str, tuple[Any, str]]:
    channels = ", ".join(f"'{channel_id}'" for channel_id in release_channel.CHANNEL_IDS)
    return {
        "language": (("fr", "en"), "Langue invalide (attendu 'fr' ou 'en')"),
        "simplified_ui": (_BOOLEAN_TEXT, "Interface simplifiée invalide (attendu 'true' ou 'false')"),
        "theme_mode": (_VALID_THEME_MODES, f"Mode de thème invalide (attendu l'un de : {', '.join(themes.MODES)})"),
        "theme": (_VALID_THEMES, f"Thème invalide (attendu l'un de : {', '.join(sorted(_VALID_THEMES))})"),
        "active_logo": (_VALID_ACTIVE_LOGOS, "Logo actif invalide (attendu 'default' ou 'custom')"),
        "update_channel": (release_channel.CHANNEL_IDS, f"Canal de mise à jour invalide (attendu l'un de : {channels})"),
        "display_mode_setting": (VALID_DISPLAY_MODE_SETTINGS, "Mode d'affichage invalide (attendu 'auto', 'dual_screen' ou 'headless')"),
        "wired_display_mode": (_VALID_WIRED_DISPLAY_MODES, "Mode d'affichage câblé invalide (attendu 'dual_screen' ou 'headless')"),
        **{key: (_BOOLEAN_TEXT, f"{key} invalide (attendu 'true' ou 'false')")
           for key in ("auto_update_enabled", "auto_web_rendition", "media_native", "update_tor")},
    }


def _refuse(status: int, detail: str) -> None:
    raise HTTPException(status_code=status, detail=detail)


def _check_string(key: str, value: str) -> None:
    if key == "update_channel" and get_profile_handler().is_store_managed() and value != release_channel.DEFAULT_CHANNEL:
        _refuse(409, "Cette installation est gérée par une boutique : seul le canal Stable est disponible.")
    allowed, message = _string_choices().get(key, (None, ""))
    if allowed is not None and value not in allowed:
        _refuse(422, message)
    if key == "active_logo" and value == "custom" and not _logo_path().exists():
        _refuse(409, "Aucun logo personnalisé n'a été importé")
    if key == "update_tor" and value == "true" and not get_profile_handler().supports_update_over_tor():
        _refuse(409, "Mises à jour par Tor indisponibles sur ce profil : une partie du téléchargement ne passerait pas par Tor.")
    if key == "update_tor_proxy":
        try:
            tor_socks.parse_proxy(value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if key == "auto_update_time" and not _AUTO_UPDATE_TIME_RE.match(value):
        _refuse(422, "Heure de mise à jour automatique invalide (attendu 'HH:MM')")


def _check_number(key: str, value: float, db: Session, stored: str) -> str:
    if key == "logs_retention_days" and value < 1:
        _refuse(422, "Le délai de rétention doit être d'au moins 1 jour")
    elif key == "default_coach_background_id":
        if value > 0:
            from app.models import Background
            if not db.query(Background).filter(Background.id == value).first():
                _refuse(404, f"Fond d'ambiance {value} introuvable")
        elif value == 0:
            return ""
    elif value < 0:
        _refuse(422, f"{key} doit être positif")
    elif key in SETTING_BOUNDS and not SETTING_BOUNDS[key][0] <= value <= SETTING_BOUNDS[key][1]:
        low, high = SETTING_BOUNDS[key]
        _refuse(422, f"{key} doit être compris entre {low} et {high}")
    return stored


def _resolve_theme(updates: dict[str, Any], db: Session) -> None:
    mode = updates["theme_mode"] if "theme_mode" in updates else _get_db_value(db, "theme_mode")
    legacy = themes.legacy_target(updates.get("theme"), mode)
    keeps_mode = updates.get("theme") in themes.THEMES and "theme_mode" not in updates and _get_db_value(db, "theme_mode") in themes.MODES
    if legacy and not keeps_mode:
        updates["theme"], updates["theme_mode"] = legacy
    if "theme_mode" in updates and "theme" not in updates:
        updates["theme"], _ = themes.resolve(_get_db_value(db, "theme"), _get_db_value(db, "theme_mode"))


def _stored_value(key: str, value: Any, db: Session) -> str:
    if value is None:
        if key != "default_coach_background_id":
            _refuse(422, f"{key} ne peut pas être nul")
        return ""
    if key in _WRITABLE_NUMERIC_FIELDS:
        return _check_number(key, value, db, str(value))
    if key in _WRITABLE_STRING_FIELDS:
        _check_string(key, value)
    return str(value)


def stage_settings(updates: dict[str, Any], db: Session) -> None:
    """Valide puis écrit les réglages dans la session SANS valider la transaction (l'appelant le fait), pour que la route et l'application des fichiers de configuration partagent les mêmes règles."""
    _resolve_theme(updates, db)
    for key, value in updates.items():
        stored = _stored_value(key, value, db)
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = stored
        else:
            db.add(Setting(key=key, value=stored))


_BROADCAST_KEYS = frozenset({
    "theme", "theme_mode", "language", "active_logo", "wired_display_mode", "display_mode_setting", "update_channel",
    "simplified_ui",
})
_BROADCAST_FIELDS = (
    "theme", "theme_mode", "language", "ui_language", "simplified_ui", "has_custom_logo", "active_logo",
    "wired_display_mode", "update_channel",
)


async def after_settings_change(updates: dict[str, Any], db: Session) -> dict[str, Any]:
    """Effets à chaud de réglages déjà enregistrés ; renvoie les réglages effectifs."""
    for key, value in updates.items():
        if key in _WRITABLE_NUMERIC_FIELDS and hasattr(runtime_settings, key) and value is not None:
            setattr(runtime_settings, key, int(value))
    result = get_settings(db)

    if "media_native" in updates:
        media_native.configure(result["media_native"])

    if "update_tor" in updates or "update_tor_proxy" in updates:
        tor_proxy.configure(result["update_tor"] == "true", result["update_tor_proxy"])

    if "auto_update_enabled" in updates or "auto_update_time" in updates:
        from app.scheduling.jobs import sync_auto_update_job

        sync_auto_update_job(
            enabled=result["auto_update_enabled"] == "true",
            time_str=result["auto_update_time"],
        )

    if _BROADCAST_KEYS.intersection(updates):
        await ws_manager.broadcast({"event": "settings_change", **{key: result[key] for key in _BROADCAST_FIELDS}})

    if "wired_display_mode" in updates or "display_mode_setting" in updates:
        await ws_manager.broadcast({
            "event": "display_mode_change",
            "channel": "cable",
            "mode": result["wired_display_mode"],
        })

    return result


_LOGO_MAX_BYTES = 10 * 1024 * 1024


def _write_logo(raw: bytes) -> None:
    import io

    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGBA")
            img.thumbnail((800, 800))
            Path(runtime_settings.branding_dir).mkdir(parents=True, exist_ok=True)
            img.save(_logo_path(), "PNG")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError(str(exc)) from exc


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Upload d'un logo personnalisé : normalisé en PNG sous un nom fixe (`_LOGO_FILENAME`) pour une URL stable (/api/branding/logo.png), remplace tout logo custom précédent."""
    raw = await file.read()
    if len(raw) > _LOGO_MAX_BYTES:
        raise HTTPException(status_code=422, detail=f"Fichier trop volumineux ({_LOGO_MAX_BYTES // 1024**2} Mo max)")
    try:
        await run_in_threadpool(_write_logo, raw)
    except ValueError as e:
        logger.warning(f"Upload de logo rejeté : {e}")
        raise HTTPException(status_code=422, detail="Image illisible")

    row = db.query(Setting).filter(Setting.key == "active_logo").first()
    if row:
        row.value = "custom"
    else:
        db.add(Setting(key="active_logo", value="custom"))
    db.commit()

    logger.info("Logo personnalisé mis à jour et activé")
    await ws_manager.broadcast({"event": "settings_change", "has_custom_logo": True, "active_logo": "custom"})
    return {"has_custom_logo": True, "active_logo": "custom"}


@router.delete("/logo")
async def delete_logo(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retire le logo personnalisé et repasse le réglage actif sur le logo par défaut."""
    _logo_path().unlink(missing_ok=True)
    row = db.query(Setting).filter(Setting.key == "active_logo").first()
    if row:
        row.value = "default"
        db.commit()
    logger.info("Logo personnalisé supprimé — retour au logo par défaut")
    await ws_manager.broadcast({"event": "settings_change", "has_custom_logo": False, "active_logo": "default"})
    return {"has_custom_logo": False, "active_logo": "default"}
