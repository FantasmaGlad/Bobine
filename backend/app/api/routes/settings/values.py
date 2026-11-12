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
from app.utils import media_native, themes, tor_proxy, ui_language
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


@router.get("")
def get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    # Ancien nom de thème (avant la 5.2) ou valeur inconnue : traduit en couleur + mode, sinon thème par défaut.
    theme, theme_mode = themes.resolve(_get_db_value(db, "theme"), _get_db_value(db, "theme_mode"))
    language = _get_db_value(db, "language") or _DEFAULTS["language"]
    has_custom = _logo_path().exists()
    active_logo = _get_db_value(db, "active_logo") or _DEFAULTS["active_logo"]
    if active_logo == "custom" and not has_custom:
        active_logo = "default"
    # Pas de ligne en base = aucun choix : on suit le canal d'installation (cf. app/release_channel.py).
    channel_choice = resolve_update_channel(_get_db_value(db, "update_channel"))
    display_mode_setting = get_display_mode_setting(db)
    wired_display_mode = get_effective_wired_display_mode(db)
    auto_update_enabled = _get_db_value(db, "auto_update_enabled") or _DEFAULTS["auto_update_enabled"]
    auto_update_time = _get_db_value(db, "auto_update_time") or _DEFAULTS["auto_update_time"]
    logs_retention_str = _get_db_value(db, "logs_retention_days") or _DEFAULTS["logs_retention_days"]
    try:
        logs_retention_days = int(logs_retention_str)
    except ValueError:
        logs_retention_days = 7
    default_bg_str = _get_db_value(db, "default_coach_background_id")
    default_coach_background_id = int(default_bg_str) if default_bg_str and default_bg_str.isdigit() else None
    return {
        "wait_time_between_courses": runtime_settings.wait_time_between_courses,
        "volume_default": runtime_settings.volume_default,
        "audio_chain_timer_seconds": runtime_settings.audio_chain_timer_seconds,
        "logs_retention_days": logs_retention_days,
        "default_coach_background_id": default_coach_background_id,
        # Profil de déploiement : le
        # frontend s'en sert pour adapter le texte/comportement de la zone
        # Désinstaller/Réinitialiser selon la plateforme, sans dupliquer la
        # logique de détection côté client.
        "deployment_profile": get_deployment_profile(),
        # Build Google Play : les mises à jour passent par la boutique (Réglages adapte la section Mises à jour).
        "store_managed": get_profile_handler().is_store_managed(),
        # Faux sur Android et macOS : la planification n'y est pas proposée, la mise à jour reste manuelle.
        "auto_update_supported": get_profile_handler().can_schedule_auto_apply(),
        # Faux sur l'appliance et en boutique : une partie du trafic de mise à jour ne passerait pas par Tor.
        "update_tor_supported": get_profile_handler().supports_update_over_tor(),
        "update_tor": "true" if _get_db_value(db, "update_tor") == "true" else "false",
        "update_tor_proxy": _get_db_value(db, "update_tor_proxy") or _DEFAULTS["update_tor_proxy"],
        "theme": theme,
        "theme_mode": theme_mode,
        "language": language,
        # Langue de l'export servi depuis le démarrage : si elle diffère de `language`, un redémarrage est requis.
        "ui_language": ui_language.served(),
        "language_restart_required": language != ui_language.served(),
        # Faux sur Android : le redémarrage y arrête l'application sans relance garantie.
        "restart_guaranteed": get_profile_handler().restart_is_guaranteed(),
        "simplified_ui": "true" if _get_db_value(db, "simplified_ui") == "true" else "false",
        "has_custom_logo": has_custom,
        "active_logo": active_logo,
        # Canal de mise à jour : "stable", "beta" ou "canary", consommé par
        # GET /api/updates/check pour choisir l'endpoint GitHub interrogé.
        "update_channel": channel_choice.effective,
        # Origine : "user" (choix explicite dans les Réglages) ou "install" (canal d'installation).
        "update_channel_source": channel_choice.source,
        "install_channel": channel_choice.install,
        # Mode d'affichage câblé :
        # "dual_screen" (pupitre tactile + vidéo HDMI) ou "headless" (cinéma autonome).
        "wired_display_mode": wired_display_mode,
        # Réglage administrateur : "auto" (dérivé du matériel) ou forçage ; et
        # nombre d'écrans externes réellement détectés (None = aucun rapport).
        "display_mode_setting": display_mode_setting,
        "display_external_count": get_hardware_state().external_count,
        # Mise à jour automatique planifiée (Réglages → Mises à jour) :
        # vérifiée et appliquée chaque jour à `auto_update_time` si
        # `auto_update_enabled` — cf. app.scheduling.jobs.sync_auto_update_job.
        "auto_update_enabled": auto_update_enabled,
        "auto_update_time": auto_update_time,
        "auto_web_rendition": _get_db_value(db, "auto_web_rendition") or _DEFAULTS["auto_web_rendition"],
        # Composant audio natif : réglage persisté ("true"/"false") ; l'état réel (actif, repli,
        # absent) et le forçage par l'environnement sont lus par GET /api/settings/media-native.
        "media_native": "true" if media_native.parse_setting(_get_db_value(db, "media_native")) else "false",
        # Aide à la découverte réseau, en complément de bobine.local (avahi, cf. install.sh).
        "network": {
            "local_ip": _get_local_ip(),
            "local_ips": [{"ip": a.ip, "interface": a.interface} for a in lan_addresses()],
            "port": active_port(),
            # Sans numéro de port seulement là où le port 80 renvoie réellement vers Bobine.
            "mdns_url": _mdns_url(),
            "port80_redirect": _port80_redirect(),
            # Liens d'accès complets, les mêmes pour Réglages, l'API et la CLI : boucle locale, chaque adresse du
            # réseau local et des VPN, puis bobine.local.
            "access": _access_links(),
            # État RÉEL du répondeur mDNS embarqué ("ok"/"failed"/"disabled"
            # [headless, avahi système]/"external" [desktop, avahi natif
            # détecté]/"unavailable"/"pending") — avant ce champ, `mdns_url`
            # ci-dessus était une chaîne figée affichée comme fonctionnelle
            # même après un échec de publication, cause confirmée de
            # "bobine.local ne se déclare pas bien, fallback IP obligatoire
            # sans que rien ne le signale à l'avance".
            "mdns_status": get_mdns_status().get("state"),
        },
        # Réglages du duck/fondu des rappels radio : consommés
        # par /radio pour le fondu musique pendant une annonce, ET pour le
        # fondu du rappel lui-même. radio_announcement_duck_level reste en lecture seule
        # pour l'instant (pas demandé) ; fade_ms est éditable (cf.
        # _WRITABLE_NUMERIC_FIELDS).
        "radio_announcement_duck_level": runtime_settings.radio_announcement_duck_level,
        "radio_announcement_fade_ms": runtime_settings.radio_announcement_fade_ms,
        # Chemins en lecture seule
        "paths": {
            "database_url": runtime_settings.database_url,
            "media_dir": runtime_settings.media_dir,
            "watch_dir": runtime_settings.watch_dir,
            "thumbnails_dir": runtime_settings.thumbnails_dir,
            "backgrounds_dir": runtime_settings.backgrounds_dir,
            "backgrounds_watch_dir": runtime_settings.backgrounds_watch_dir,
            "audio_dir": runtime_settings.audio_dir,
            "audio_watch_dir": runtime_settings.audio_watch_dir,
            "radio_dir": runtime_settings.radio_dir,
            "radio_watch_dir": runtime_settings.radio_watch_dir,
            "radio_covers_dir": runtime_settings.radio_covers_dir,
            "radio_announcements_dir": runtime_settings.radio_announcements_dir,
            "branding_dir": runtime_settings.branding_dir,
            "logs_dir": runtime_settings.logs_dir,
            "subtitles_dir": runtime_settings.subtitles_dir,
        },
    }


@router.get("/media-native")
async def get_media_native_status() -> dict[str, Any]:
    """État réel du composant audio natif : désactivé, actif, en repli ou absent.

    Le contrôle lance le composant s'il est activé et ne l'est pas encore (au plus un
    processus, celui que les imports utilisent) : il tourne hors de la boucle d'évènements.
    """
    return await run_in_threadpool(media_native.status)


@router.put("")
async def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    updates = settings_updates(payload)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun paramètre fourni")
    stage_settings(updates, db)
    db.commit()
    logger.info("Paramètres mis à jour : %s", ", ".join(sorted(updates)))
    return await after_settings_change(updates, db)


def settings_updates(payload: SettingsUpdate) -> dict[str, Any]:
    """Champs fournis, convertis par le modèle ; `wired_display_mode` (ancien client) vaut choix manuel du mode."""
    # `.model_dump` (Pydantic v2) sauf sur le profil Android où `.dict` (v1) est le seul disponible.
    dump = getattr(payload, "model_dump", None) or payload.dict
    updates = dump(exclude_unset=True)
    if updates.get("wired_display_mode") and "display_mode_setting" not in updates:
        updates["display_mode_setting"] = updates["wired_display_mode"]
    return updates


def stage_settings(updates: dict[str, Any], db: Session) -> None:
    """Valide puis écrit les réglages dans la session SANS valider la transaction (l'appelant le fait), pour que la
    route et l'application des fichiers de configuration partagent les mêmes règles. Lève `HTTPException`."""
    # Ancien nom de thème (client ou sauvegarde d'avant la 5.2) : accepté et enregistré comme couleur + mode.
    # Le mode enregistré compte quand la requête ne le fournit pas : un PUT partiel du seul `theme`
    # ne doit pas changer le mode déjà choisi (les noms chili/charbon/orchidee sont ambigus).
    stored_mode = _get_db_value(db, "theme_mode")
    mode = updates["theme_mode"] if "theme_mode" in updates else stored_mode
    legacy = themes.legacy_target(updates.get("theme"), mode)
    if legacy:
        # Client 5.2 qui ne change que la couleur : s'il omet le mode alors qu'un mode est enregistré,
        # garder ce mode plutôt que le mode fixe de l'ancien thème (le client envoie normalement les deux).
        if (
            updates.get("theme") in themes.THEMES
            and "theme_mode" not in updates
            and _get_db_value(db, "theme_mode") in themes.MODES
        ):
            legacy = None
        else:
            updates["theme"], updates["theme_mode"] = legacy
    if "theme_mode" in updates and "theme" not in updates:
        # Changement de mode seul : normaliser aussi le nom ancien stocké, sinon « auto » est relu avec
        # le mode fixe de cet ancien thème (resolve ne rend que light/dark pour un nom d'avant la 5.2).
        updates["theme"], _ = themes.resolve(_get_db_value(db, "theme"), _get_db_value(db, "theme_mode"))
    for key, value in updates.items():
        if value is None:
            if key == "default_coach_background_id":
                stored_value = ""
            else:
                raise HTTPException(status_code=400, detail=f"{key} ne peut pas être nul")
        else:
            stored_value = str(value)
        if key in _WRITABLE_NUMERIC_FIELDS and value is not None:
            if key == "logs_retention_days" and value < 1:
                raise HTTPException(status_code=400, detail="Le délai de rétention doit être d'au moins 1 jour")
            elif key == "default_coach_background_id":
                if value > 0:
                    from app.models import Background
                    if not db.query(Background).filter(Background.id == value).first():
                        raise HTTPException(status_code=400, detail=f"Fond d'ambiance {value} introuvable")
                elif value == 0:
                    stored_value = ""
            elif value < 0:
                raise HTTPException(status_code=400, detail=f"{key} doit être positif")
            elif key in SETTING_BOUNDS and not SETTING_BOUNDS[key][0] <= value <= SETTING_BOUNDS[key][1]:
                low, high = SETTING_BOUNDS[key]
                raise HTTPException(status_code=400, detail=f"{key} doit être compris entre {low} et {high}")
        elif key in _WRITABLE_STRING_FIELDS and value is not None:
            if key == "language" and value not in ("fr", "en"):
                raise HTTPException(status_code=400, detail="Langue invalide (attendu 'fr' ou 'en')")
            if key == "simplified_ui" and value not in ("true", "false"):
                raise HTTPException(status_code=400, detail="Interface simplifiée invalide (attendu 'true' ou 'false')")
            if key == "theme_mode" and value not in _VALID_THEME_MODES:
                raise HTTPException(status_code=400, detail=f"Mode de thème invalide (attendu l'un de : {', '.join(themes.MODES)})")
            if key == "theme" and value not in _VALID_THEMES:
                raise HTTPException(status_code=400, detail=f"Thème invalide (attendu l'un de : {', '.join(sorted(_VALID_THEMES))})")
            if key == "active_logo":
                if value not in _VALID_ACTIVE_LOGOS:
                    raise HTTPException(status_code=400, detail="Logo actif invalide (attendu 'default' ou 'custom')")
                if value == "custom" and not _logo_path().exists():
                    raise HTTPException(status_code=400, detail="Aucun logo personnalisé n'a été importé")
            if key == "update_channel" and get_profile_handler().is_store_managed() and value != release_channel.DEFAULT_CHANNEL:
                raise HTTPException(status_code=409, detail="Cette installation est gérée par une boutique : seul le canal Stable est disponible.")
            if key == "update_channel" and value not in release_channel.CHANNEL_IDS:
                expected = ", ".join(f"'{channel_id}'" for channel_id in release_channel.CHANNEL_IDS)
                raise HTTPException(status_code=400, detail=f"Canal de mise à jour invalide (attendu l'un de : {expected})")
            if key == "display_mode_setting" and value not in VALID_DISPLAY_MODE_SETTINGS:
                raise HTTPException(
                    status_code=400,
                    detail="Mode d'affichage invalide (attendu 'auto', 'dual_screen' ou 'headless')",
                )
            if key == "wired_display_mode" and value not in _VALID_WIRED_DISPLAY_MODES:
                raise HTTPException(
                    status_code=400,
                    detail="Mode d'affichage câblé invalide (attendu 'dual_screen' ou 'headless')",
                )
            if key == "auto_update_enabled" and value not in ("true", "false"):
                raise HTTPException(status_code=400, detail="auto_update_enabled invalide (attendu 'true' ou 'false')")
            if key == "auto_web_rendition" and value not in ("true", "false"):
                raise HTTPException(status_code=400, detail="auto_web_rendition invalide (attendu 'true' ou 'false')")
            if key == "media_native" and value not in ("true", "false"):
                raise HTTPException(status_code=400, detail="media_native invalide (attendu 'true' ou 'false')")
            if key == "update_tor" and value not in ("true", "false"):
                raise HTTPException(status_code=400, detail="update_tor invalide (attendu 'true' ou 'false')")
            if key == "update_tor" and value == "true" and not get_profile_handler().supports_update_over_tor():
                raise HTTPException(
                    status_code=409,
                    detail="Mises à jour par Tor indisponibles sur ce profil : une partie du téléchargement ne passerait pas par Tor.",
                )
            if key == "update_tor_proxy":
                try:
                    tor_proxy.parse_proxy(value)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
            if key == "auto_update_time" and not _AUTO_UPDATE_TIME_RE.match(value):
                raise HTTPException(status_code=400, detail="Heure de mise à jour automatique invalide (attendu 'HH:MM')")

        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = stored_value
        else:
            db.add(Setting(key=key, value=stored_value))


async def after_settings_change(updates: dict[str, Any], db: Session) -> dict[str, Any]:
    """Effets à chaud de réglages déjà enregistrés ; renvoie les réglages effectifs."""
    for key, value in updates.items():
        # Le singleton `runtime_settings` est partagé par tout le backend (playback_manager, scheduling...),
        # qui lit ses attributs à chaque usage, pas seulement au démarrage.
        if key in _WRITABLE_NUMERIC_FIELDS and hasattr(runtime_settings, key) and value is not None:
            setattr(runtime_settings, key, int(value))
    result = get_settings(db)

    if "media_native" in updates:
        # Effet immédiat sur les prochains imports ; les imports en cours finissent avec le mode
        # qu'ils ont commencé (aucun média n'est jamais perdu : repli sur ffprobe/ffmpeg).
        media_native.configure(result["media_native"])

    if "update_tor" in updates or "update_tor_proxy" in updates:
        tor_proxy.configure(result["update_tor"] == "true", result["update_tor_proxy"])

    if "auto_update_enabled" in updates or "auto_update_time" in updates:
        # Import différé : `scheduling` importe déjà plusieurs
        # modules utilitaires au chargement, et ce routeur est lui-même
        # importé tôt par `main.py` — même précaution que les autres
        # imports différés de ce fichier (cf. `Background` plus haut).
        from app.scheduling.jobs import sync_auto_update_job

        sync_auto_update_job(
            enabled=result["auto_update_enabled"] == "true",
            time_str=result["auto_update_time"],
        )

    # Diffusion temps réel (correctif "thème ne se synchronise pas sur
    # l'écran cinéma") : AppSettingsProvider ne chargeait le thème/langue
    # qu'une fois au montage — un changement décidé depuis l'admin pendant
    # que /cinema ou un autre écran était déjà ouvert n'y apparaissait donc
    # jamais sans rechargement manuel. Diffusé uniquement si l'un des deux a
    # effectivement changé (les kiosques tournent 24/7 sans rechargement),
    # pour ne pas générer de trafic WebSocket inutile à chaque réglage numérique (countdown, volume...).
    if (
        "theme" in updates
        or "theme_mode" in updates
        or "language" in updates
        or "active_logo" in updates
        or "wired_display_mode" in updates
        or "display_mode_setting" in updates
        or "update_channel" in updates
        or "simplified_ui" in updates
    ):
        await ws_manager.broadcast({
            "event": "settings_change",
            "theme": result["theme"],
            "theme_mode": result["theme_mode"],
            "language": result["language"],
            "ui_language": result["ui_language"],
            "simplified_ui": result["simplified_ui"],
            "has_custom_logo": result["has_custom_logo"],
            "active_logo": result["active_logo"],
            "wired_display_mode": result["wired_display_mode"],
            "update_channel": result["update_channel"],
        })

    # Diffusion dédiée display_mode_change sur canal "cable"
    if "wired_display_mode" in updates or "display_mode_setting" in updates:
        await ws_manager.broadcast({
            "event": "display_mode_change",
            "channel": "cable",
            "mode": result["wired_display_mode"],
        })

    return result


_LOGO_MAX_BYTES = 10 * 1024 * 1024


def _write_logo(raw: bytes) -> None:
    """Normalise l'image reçue en PNG de 800 px au plus. `ValueError` si elle est illisible : fichier tronqué
    ou résolution annoncée démesurée sont des refus, pas des pannes."""
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
    """Upload d'un logo personnalisé :
    normalisé en PNG sous un nom fixe (`_LOGO_FILENAME`) pour une URL stable
    (/api/branding/logo.png), remplace tout logo custom précédent.
    Active automatiquement `active_logo = "custom"` tout en permettant à l'utilisateur
    de basculer manuellement vers le logo Bobine à tout moment."""
    raw = await file.read()
    # Garde-fou taille : matériel modeste visé par ce
    # projet (Wyse), pas de limite avant lecture complète en mémoire sinon.
    if len(raw) > _LOGO_MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"Fichier trop volumineux ({_LOGO_MAX_BYTES // 1024**2} Mo max)")
    try:
        await run_in_threadpool(_write_logo, raw)
    except ValueError as e:
        logger.warning(f"Upload de logo rejeté : {e}")
        raise HTTPException(status_code=400, detail="Image illisible")

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
