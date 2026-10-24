import asyncio
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import (
    ROOT_DIR,
    _global_config_path,
    settings as runtime_settings,
)
from app.database import _IS_SQLITE, engine, get_db, init_db
from app.models import Setting
from app.playback_manager import get_playback_manager
from app.radio_manager import get_radio_manager
from app.scheduler_manager import activate_radio_output
from app import release_channel
from app.utils.activity_log import log_activity
from app.utils.android_runtime import is_android
from app.utils.display_state import (
    DEFAULT_DISPLAY_MODE_SETTING,
    VALID_DISPLAY_MODE_SETTINGS,
    effective_wired_display_mode,
    get_hardware_state,
)
from app.utils import media_native
from app.utils.hardware_info import (
    get_storage_model,
    get_system_telemetry_payload,
    purge_expired_logs_and_metrics,
)
from app.utils.deployment import (
    SUDOERS_FILE,
    UNINSTALL_WRAPPER,
    get_deployment_profile,
    get_profile_handler,
    resolve_update_channel,
)
from app.utils.mdns import get_status as get_mdns_status
from app.utils.network import lan_addresses, primary_lan_ip
from app.utils.version import get_app_version
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)


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
    "theme", "language", "active_logo", "update_channel", "wired_display_mode",
    "display_mode_setting", "auto_update_enabled", "auto_update_time",
    "auto_web_rendition", "media_native",
}
_DEFAULTS = {
    # "lavande" : thème clair par défaut (nacre irisée et améthyste profonde).
    "theme": "lavande",
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
    # Version web « lisible partout » : désactivée par
    # défaut — c'est un réencodage ffmpeg (plusieurs minutes sur un CPU
    # modeste) que l'administrateur choisit d'activer ; quand elle l'est, la
    # première lecture depuis un navigateur incapable de décoder l'original la
    # déclenche automatiquement (cf. main.py::stream_video).
    "auto_web_rendition": "false",
    # Composant audio natif (expérimental) : désactivé par défaut. Il n'accélère que de
    # nouveaux imports et n'altère aucune donnée existante ; tout échec retombe sur
    # ffprobe/ffmpeg. La variable d'environnement BOBINE_MEDIA_NATIVE (1/0) reste un
    # forçage prioritaire (cf. app/utils/media_native.py).
    "media_native": media_native.DEFAULT_VALUE,
}
_AUTO_UPDATE_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_LOGO_FILENAME = "logo.png"
# "les-mills-sombre" est la clé interne historique du thème "Sombre" — inchangée pour ne rien casser sur les
# installations existantes, seul son libellé affiché change côté frontend.
_VALID_THEMES = {
    "les-mills-sombre", "clair", "lune", "menthe", "automne", "hiver",
    "chili", "ciel", "orchidee", "taupe", "charbon", "charbon-sombre",
    "beige", "lavande", "miel", "coco",
}
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
_DISPLAY_OUTPUTS_BY_CHANNEL = {
    "cable": ("kiosk", "cinema", "radio"),
    "network": ("kiosk", "cinema"),
}
_DISPLAY_CHANNELS = ("cable", "network")


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


def _get_db_value(db: Session, key: str) -> str | None:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else None


def _logo_path() -> Path:
    return Path(runtime_settings.branding_dir) / _LOGO_FILENAME


_cached_local_ip: str | None = None
_cached_local_ip_time: float = 0.0
_LOCAL_IP_CACHE_TTL = 15.0  # Actualisation toutes les 15 secondes maximum


def _get_local_ip() -> str | None:
    """Adresse IPv4 du réseau local (Wi-Fi ou Ethernet) à afficher et à donner
    aux autres appareils ; jamais celle d'un VPN ou du réseau mobile (cf.
    `utils/network.py`). Équivalent de `hostname -I` sans sous-processus, en
    complément de la découverte mDNS (bobine.local, cf. install.sh).

    Mise en cache avec TTL court (15s) pour éviter des énumérations répétées
    tout en permettant à l'IP de s'actualiser automatiquement lors d'un
    changement de réseau ou d'attribution DHCP sans redémarrer le serveur."""
    global _cached_local_ip, _cached_local_ip_time
    now = time.time()
    if _cached_local_ip is not None and (now - _cached_local_ip_time) < _LOCAL_IP_CACHE_TTL:
        return _cached_local_ip

    detected = primary_lan_ip()
    if detected is not None:
        _cached_local_ip = detected
        _cached_local_ip_time = now
    else:
        _cached_local_ip = None
        _cached_local_ip_time = now - (_LOCAL_IP_CACHE_TTL - 3.0)
    return _cached_local_ip


def get_display_mode_setting(db: Session) -> str:
    value = _get_db_value(db, "display_mode_setting") or DEFAULT_DISPLAY_MODE_SETTING
    return value if value in VALID_DISPLAY_MODE_SETTINGS else DEFAULT_DISPLAY_MODE_SETTING


def get_effective_wired_display_mode(db: Session) -> str:
    """Mode d'affichage câblé effectif : forçage admin, sinon
    dérivé des écrans externes réellement connectés. Sans rapport matériel :
    `dual_screen` sur Android (tablette = pupitre tactile, comportement
    historique), `headless` ailleurs."""
    default = "dual_screen" if get_deployment_profile() == "android" else "headless"
    return effective_wired_display_mode(
        get_display_mode_setting(db), get_hardware_state().external_count, default
    )


async def broadcast_display_mode(db: Session) -> str:
    """Diffuse le mode effectif à tous les écrans (frontend : `settings_change`
    et `display_mode_change`, déjà consommés par AppSettingsContext)."""
    snapshot = get_settings(db)
    mode = snapshot["wired_display_mode"]
    await ws_manager.broadcast({
        "event": "settings_change",
        "theme": snapshot["theme"],
        "language": snapshot["language"],
        "has_custom_logo": snapshot["has_custom_logo"],
        "active_logo": snapshot["active_logo"],
        "wired_display_mode": mode,
    })
    await ws_manager.broadcast({"event": "display_mode_change", "channel": "cable", "mode": mode})
    return mode


@router.get("")
def get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    theme = _get_db_value(db, "theme") or _DEFAULTS["theme"]
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
        "theme": theme,
        "language": language,
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
        # `auto_update_enabled` — cf. app.scheduler_manager.sync_auto_update_job.
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
            "port": runtime_settings.port,
            "mdns_url": "http://bobine.local",
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


# Dossiers de médias dont on additionne l'empreinte disque pour l'indicateur
# de stockage : ce que l'application
# consomme réellement, cours + fonds + audio + vignettes + logs + dossiers
# surveillés. Les chemins sont déjà résolus en absolu par app.config.
_STORAGE_TRACKED_DIRS = (
    "media_dir",
    "watch_dir",
    "thumbnails_dir",
    "backgrounds_dir",
    "backgrounds_watch_dir",
    "audio_dir",
    "audio_watch_dir",
    "radio_dir",
    "radio_covers_dir",
    "radio_announcements_dir",
    "radio_watch_dir",
    "logs_dir",
)


def _dir_size(path: Path) -> int:
    """Taille cumulée d'un dossier (récursif), tolérante aux erreurs d'accès
    et aux liens symboliques (non suivis, pour ne pas compter deux fois ni
    boucler). Renvoie 0 si le dossier n'existe pas encore."""
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += _dir_size(Path(entry.path))
                except OSError:
                    continue
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return 0
    return total


@router.get("/storage")
def get_storage() -> dict[str, Any]:
    """
    Indicateur de capacité de stockage : espace disque du volume qui héberge les médias (total /
    utilisé / libre) et empreinte propre de l'application (somme des dossiers
    de médias). Permet à l'admin de voir combien de cours/fonds/audio il peut
    encore importer avant de saturer le disque du Wyse.
    """
    media_dir = Path(runtime_settings.media_dir)
    # Volume mesuré : le dossier des médias s'il existe, sinon son parent
    # (tout premier démarrage, avant le premier import) — jamais un chemin
    # inexistant qui ferait échouer shutil.disk_usage.
    probe = media_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        usage = shutil.disk_usage(probe)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Impossible de lire l'espace disque : {e}")

    app_bytes = 0
    seen: set[str] = set()
    for attr in _STORAGE_TRACKED_DIRS:
        raw = getattr(runtime_settings, attr, None)
        if not raw:
            continue
        # Dédoublonnage : plusieurs réglages peuvent pointer le même dossier
        # (ou un sous-dossier) — on ne compte chaque chemin racine qu'une fois.
        resolved = str(Path(raw))
        if resolved in seen:
            continue
        seen.add(resolved)
        app_bytes += _dir_size(Path(raw))

    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": round(usage.used / usage.total * 100, 1) if usage.total else 0.0,
        "app_bytes": app_bytes,
        "path": str(probe),
        "storage_model": get_storage_model(),
    }


@router.get("/system")
def get_system_usage() -> dict[str, Any]:
    """Charge CPU, GPU, RAM, Températures, Puissance (W), Modèles des composants et Runtime."""
    return get_system_telemetry_payload()


@router.post("/logs/purge")
def purge_logs_manual(retention_days: int | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Purge manuelle des journaux d'activité et historiques de métriques."""
    if retention_days is None:
        row = db.query(Setting).filter(Setting.key == "logs_retention_days").first()
        retention_days = int(row.value) if row and row.value and row.value.isdigit() else 7
    if retention_days < 1:
        retention_days = 1
    purged = purge_expired_logs_and_metrics(db, retention_days)
    log_activity(
        db,
        "logs_purged",
        f"Purge manuelle (rétention {retention_days}j) : {purged['purged_logs']} logs, {purged['purged_metrics']} métriques",
    )
    return {"message": "Purge effectuée avec succès", "details": purged, "retention_days": retention_days}



@router.get("/media-native")
async def get_media_native_status() -> dict[str, Any]:
    """État réel du composant audio natif : désactivé, actif, en repli ou absent.

    Le contrôle lance le composant s'il est activé et ne l'est pas encore (au plus un
    processus, celui que les imports utilisent) : il tourne hors de la boucle d'évènements.
    """
    return await run_in_threadpool(media_native.status)


@router.put("")
async def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    # `.model_dump` (Pydantic v2) sauf sur le profil Android où `.dict` (v1)
    # est le seul disponible.
    dump = getattr(payload, "model_dump", None) or payload.dict
    updates = dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun paramètre fourni")

    # Compatibilité : un ancien client qui écrit `wired_display_mode` exprime un
    # choix MANUEL de l'administrateur -> forçage du mode.
    if updates.get("wired_display_mode") and "display_mode_setting" not in updates:
        updates["display_mode_setting"] = updates["wired_display_mode"]

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
        elif key in _WRITABLE_STRING_FIELDS and value is not None:
            if key == "language" and value not in ("fr", "en"):
                raise HTTPException(status_code=400, detail="Langue invalide (attendu 'fr' ou 'en')")
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
            if key == "auto_update_time" and not _AUTO_UPDATE_TIME_RE.match(value):
                raise HTTPException(status_code=400, detail="Heure de mise à jour automatique invalide (attendu 'HH:MM')")

        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = stored_value
        else:
            db.add(Setting(key=key, value=stored_value))

        # Effet immédiat sur le process en cours pour les champs numériques
        # (le singleton `runtime_settings` est un objet mutable partagé par
        # tout le backend : playback_manager, scheduler_manager, etc. lisent
        # ses attributs directement à chaque usage, pas seulement au démarrage).
        if key in _WRITABLE_NUMERIC_FIELDS and hasattr(runtime_settings, key):
            setattr(runtime_settings, key, int(value))

    db.commit()
    logger.info(f"Paramètres mis à jour : {updates}")
    result = get_settings(db)

    if "media_native" in updates:
        # Effet immédiat sur les prochains imports ; les imports en cours finissent avec le mode
        # qu'ils ont commencé (aucun média n'est jamais perdu : repli sur ffprobe/ffmpeg).
        media_native.configure(result["media_native"])

    if "auto_update_enabled" in updates or "auto_update_time" in updates:
        # Import différé : `scheduler_manager` importe déjà plusieurs
        # modules utilitaires au chargement, et ce routeur est lui-même
        # importé tôt par `main.py` — même précaution que les autres
        # imports différés de ce fichier (cf. `Background` plus haut).
        from app.scheduler_manager import sync_auto_update_job

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
        or "language" in updates
        or "active_logo" in updates
        or "wired_display_mode" in updates
        or "display_mode_setting" in updates
        or "update_channel" in updates
    ):
        await ws_manager.broadcast({
            "event": "settings_change",
            "theme": result["theme"],
            "language": result["language"],
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


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Upload d'un logo personnalisé :
    normalisé en PNG sous un nom fixe (`_LOGO_FILENAME`) pour une URL stable
    (/api/branding/logo.png), remplace tout logo custom précédent.
    Active automatiquement `active_logo = "custom"` tout en permettant à l'utilisateur
    de basculer manuellement vers le logo Bobine à tout moment."""
    import io

    from PIL import Image, UnidentifiedImageError

    raw = await file.read()
    # Garde-fou taille : matériel modeste visé par ce
    # projet (Wyse), pas de limite avant lecture complète en mémoire sinon.
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (10 Mo max)")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGBA")
            img.thumbnail((800, 800))
            branding_dir = Path(runtime_settings.branding_dir)
            branding_dir.mkdir(parents=True, exist_ok=True)
            img.save(_logo_path(), "PNG")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        # Capture large (pas seulement UnidentifiedImageError) : un fichier tronqué (OSError) ou une bombe de décompression
        # (résolution annoncée énorme) sont aussi des cas de rejet propre en
        # 400, pas un 500 non géré.
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


def get_display_output_value(db: Session, channel: str = "cable") -> str:
    """Valeur de sortie active pour un canal, réutilisable hors endpoint
    (verrouillage cinéma dans routers/playback.py)."""
    value = _get_db_value(db, _DISPLAY_OUTPUT_KEYS[channel])
    # Une valeur explicitement stockée (y compris "radio" sur le câblé) l'emporte
    # toujours sur la sortie dérivée du matériel ci-dessous.
    if value in _DISPLAY_OUTPUTS_BY_CHANNEL[channel]:
        return value
    if channel == "cable":
        if get_deployment_profile() == "android" or get_effective_wired_display_mode(db) == "dual_screen":
            return "cinema"
    return "kiosk"


@router.get("/display-output")
def get_display_output(db: Session = Depends(get_db)) -> dict[str, str]:
    """Sortie active des deux canaux : câblé (écran du Wyse) et réseau (tout
    autre appareil du LAN)."""
    return {
        "cable": get_display_output_value(db, "cable"),
        "network": get_display_output_value(db, "network"),
    }


@router.put("/display-output")
async def set_display_output(payload: DisplayOutputUpdate, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Bascule un canal (câblé ou réseau) entre kiosk et cinéma, indépendamment
    de l'autre. Le canal câblé peut aussi être basculé sur la radio. L'application est instantanée : l'évènement est diffusé à
    tous les clients WebSocket, et la page concernée (l'écran câblé pour le
    canal "cable", tout autre /kiosk ou /cinema du réseau pour "network")
    navigue d'elle-même vers l'autre page en le recevant.
    """
    if payload.channel not in _DISPLAY_CHANNELS:
        raise HTTPException(status_code=400, detail="Canal invalide (attendu 'cable' ou 'network')")
    if payload.output not in _DISPLAY_OUTPUTS_BY_CHANNEL[payload.channel]:
        allowed = " ou ".join(f"'{o}'" for o in _DISPLAY_OUTPUTS_BY_CHANNEL[payload.channel])
        raise HTTPException(status_code=400, detail=f"Sortie invalide pour ce canal (attendu {allowed})")

    await apply_display_output(db, payload.channel, payload.output)
    return {
        "cable": get_display_output_value(db, "cable"),
        "network": get_display_output_value(db, "network"),
    }


async def apply_display_output(db: Session, channel: str, output: str, *, activate_radio: bool = True) -> None:
    """Applique une bascule de sortie DÉJÀ validée : persistance, arrêt de ce qui jouait sur le canal,
    reprise ou pause du moteur radio câblé, diffusion aux clients. Partagée par l'endpoint admin et par
    le planning (une programmation de la radio câblée ramène l'écran câblé sur Radio).
    `activate_radio=False` : ne démarre pas l'ambiance du moteur radio (l'appelant charge sa propre playlist)."""
    previous_output = get_display_output_value(db, channel)
    key = _DISPLAY_OUTPUT_KEYS[channel]
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = output
    else:
        db.add(Setting(key=key, value=output))
    db.commit()

    # Bascule vers cinéma : coupe ce qui jouait côté kiosk sur CE canal plutôt
    # que de le laisser tourner en arrière-plan sans écran pour l'afficher —
    # sans ça l'état serveur restait "en cours" (position qui continue
    # d'avancer, "En direct" affiché côté admin) et pouvait reprendre en
    # l'état si on rebasculait sur kiosk plus tard, en conflit avec ce que
    # l'utilisateur regarde alors en cinéma.
    if output in ("cinema", "radio"):
        manager = get_playback_manager(channel)
        current = manager.snapshot()
        if current["current_video"] or current["current_background"] or current["current_audio_course"]:
            title = (
                (current["current_video"] or {}).get("title")
                or (current["current_background"] or {}).get("title")
                or (current["current_audio_course"] or {}).get("title")
            )
            log_activity(db, "playback_stopped", title)
        await manager.stop()

    if channel == "cable":
        # Radio sur la sortie câblée : le moteur radio câblé reprend (ou démarre
        # l'ambiance s'il était à l'arrêt) à l'arrivée, et se met en PAUSE au
        # départ — sans perdre sa file, pour une reprise instantanée au retour.
        if output == "radio":
            if activate_radio:
                await activate_radio_output(db, "radio_cable")
        elif previous_output == "radio":
            await get_radio_manager("radio_cable").pause()

    await ws_manager.broadcast({"event": "display_output", "channel": channel, "output": output})
    logger.info(f"Sortie {channel} basculée sur /{output}")


async def _run_full_reset():
    """
    Diffuse un rechargement à tous les navigateurs connectés (PC/mobile/coach)
    puis redémarre les services via le handler du profil courant.
    Exécuté en tâche de fond APRÈS l'envoi de la réponse HTTP : le
    redémarrage du backend termine le processus courant, il ne peut donc pas
    avoir lieu pendant le traitement de la requête elle-même.

    Sur le profil headless hors de l'environnement cible (règle sudoers/
    unités systemd absentes, ex. poste de dev), les appels `systemctl`
    échouent proprement et sont juste loggés — seule la diffusion
    `force_reload` a un effet observable en dev.
    """
    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec de la diffusion force_reload : {e}")

    # Laisse le temps au message de partir avant de couper les connexions.
    await asyncio.sleep(1.0)

    get_profile_handler().restart_services()


@router.post("/system/reset")
async def reset_system(background_tasks: BackgroundTasks) -> dict[str, str]:
    """
    Réinitialisation complète :
    force le rechargement de tous les écrans connectés puis redémarre le
    kiosk et le backend. Action volontairement lourde/perturbatrice — le
    bouton correspondant côté UI doit demander confirmation avant d'appeler
    cet endpoint.
    """
    background_tasks.add_task(_run_full_reset)
    return {"message": "Synchronisation en cours : les écrans vident leur cache et rechargent les nouveaux assets."}


# ---------------------------------------------------------------------------
# Désinstallation complète (bouton « Désinstaller » — remise à zéro machine)
# ---------------------------------------------------------------------------


class UninstallRequest(BaseModel):
    confirm: str


async def _run_uninstall():
    """Laisse la réponse HTTP partir, puis déclenche la désinstallation via
    le handler du profil courant."""
    await asyncio.sleep(1.0)
    try:
        get_profile_handler().start_uninstall()
    except Exception as e:
        logger.error(f"Échec du lancement de la désinstallation : {e}")


@router.post("/system/uninstall")
async def uninstall_system(payload: UninstallRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Remise à zéro complète de la machine.
    Action IRRÉVERSIBLE sur les profils qui la supportent — l'UI exige une
    phrase de confirmation avant cet appel, quel que soit le profil.

    Sur le profil headless (appliance) : services systemd + config /etc +
    application + venv + TOUTES les données, via l'enveloppe
    `/usr/local/sbin/bobine-uninstall` (root sans mot de passe, règle
    sudoers dédiée posée par `install.sh`). Hors d'une installation cible
    (enveloppe/sudoers absents, ex. poste de dev), renvoie 400 avec la
    marche à suivre manuelle plutôt que d'échouer silencieusement.

    Sur les profils desktop (Windows et, plus tard, macOS/Linux de bureau) :
    aucune action n'est déclenchée depuis le backend (pas d'équivalent sûr à
    l'enveloppe systemd-run de l'appliance) — la réponse contient les instructions de désinstallation propres
    à la plateforme."""
    phrase = payload.confirm.strip().upper().replace("É", "E")
    if phrase != "DESINSTALLER":
        raise HTTPException(status_code=400, detail="Phrase de confirmation incorrecte.")

    handler = get_profile_handler()
    if not handler.can_self_uninstall():
        return {"message": handler.uninstall_instructions(), "self_uninstall": "false"}

    if handler.profile == "linux-headless" and (not UNINSTALL_WRAPPER.exists() or not SUDOERS_FILE.exists()):
        raise HTTPException(
            status_code=400,
            detail=(
                "Cette machine n'est pas une installation gérée (désinstalleur système absent). "
                "Depuis un poste de dev, lancez à la main : sudo ./install.sh --uninstall --purge --purge-data"
            ),
        )
    background_tasks.add_task(_run_uninstall)
    return {"message": "Désinstallation lancée : la procédure de suppression est en cours d'exécution."}


# ---------------------------------------------------------------------------
# Sauvegarde & Restauration universelle (Base SQLite + config)
# ---------------------------------------------------------------------------


def _sanitized_db_bytes(db_path: Path) -> bytes:
    """Copie cohérente de la base SANS les réglages secrets (empreinte du PIN « Périphériques ») :
    restaurer une sauvegarde sur une autre machine ne doit pas y importer un PIN inconnu."""
    from app.devices.security import SECRET_SETTING_KEYS

    with tempfile.TemporaryDirectory(prefix="bobine_backup_") as tmp_dir:
        copy_path = Path(tmp_dir) / "database.db"
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(copy_path))
        try:
            src.backup(dst)
            marks = ",".join("?" for _ in SECRET_SETTING_KEYS)
            try:
                dst.execute(f"DELETE FROM settings WHERE key IN ({marks})", SECRET_SETTING_KEYS)
                dst.commit()
            except sqlite3.OperationalError:  # table absente : base vierge, rien à retirer
                pass
            dst.execute("VACUUM")  # purge physique des pages libérées
        finally:
            dst.close()
            src.close()
        return copy_path.read_bytes()


@router.get("/backup/export")
def export_backup() -> Response:
    """
    Exporte une archive ZIP de sauvegarde contenant :
    - La base de données SQLite (après checkpoint WAL pour garantir sa consistance)
    - Le fichier de configuration config.toml (si présent)
    - Un manifest.json décrivant la version, la date et le profil.
    """
    if not _IS_SQLITE:
        raise HTTPException(status_code=400, detail="L'export de sauvegarde n'est supporté que pour SQLite.")

    db_path = _get_sqlite_db_path()
    if not db_path or not db_path.exists():
        raise HTTPException(status_code=404, detail="Fichier de base de données introuvable.")

    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
    except Exception as e:
        logger.warning(f"Avertissement lors du checkpoint WAL avant sauvegarde : {e}")

    manifest = {
        "app": "Bobine",
        "version": get_app_version(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deployment_profile": get_deployment_profile(),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("database.db", _sanitized_db_bytes(db_path))

        cfg_path = _global_config_path()
        if cfg_path.exists():
            zf.write(cfg_path, arcname="config.toml")
        elif (ROOT_DIR / "config.toml").exists():
            zf.write(ROOT_DIR / "config.toml", arcname="config.toml")

    buf.seek(0)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"bobine-backup-{timestamp_str}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _run_restore_restart():
    """Tâche d'arrière-plan après restauration : force reload puis redémarrage."""
    await asyncio.sleep(1.0)
    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec force_reload après restauration : {e}")
    await asyncio.sleep(1.0)
    get_profile_handler().restart_services()


@router.post("/backup/restore")
async def restore_backup(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Restaure une sauvegarde depuis une archive ZIP uploadée.
    Valide l'archive, vérifie l'en-tête et les tables SQLite, effectue une copie .bak,
    remplace la base de données et planifie le redémarrage.
    """
    if not _IS_SQLITE:
        raise HTTPException(status_code=400, detail="La restauration n'est supportée que pour SQLite.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier de sauvegarde vide.")

    buf = io.BytesIO(content)
    if not zipfile.is_zipfile(buf):
        raise HTTPException(status_code=400, detail="Le fichier fourni n'est pas une archive ZIP valide.")

    db_path = _get_sqlite_db_path()
    if not db_path:
        raise HTTPException(status_code=500, detail="Chemin de la base de données introuvable.")

    with zipfile.ZipFile(buf, "r") as zf:
        namelist = zf.namelist()
        if "database.db" not in namelist:
            raise HTTPException(status_code=400, detail="Archive invalide : database.db manquant.")

        db_bytes = zf.read("database.db")
        if not db_bytes.startswith(b"SQLite format 3\x00"):
            raise HTTPException(status_code=400, detail="Le fichier database.db n'est pas une base SQLite valide.")

        try:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp.write(db_bytes)
                tmp_path = Path(tmp.name)
            try:
                con = sqlite3.connect(tmp_path)
                cur = con.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in cur.fetchall()}
                con.close()
                if "videos" not in tables and "settings" not in tables:
                    raise HTTPException(status_code=400, detail="La base dans l'archive ne contient pas les tables Bobine.")
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Échec de validation de la base de données : {e}")

        config_bytes = zf.read("config.toml") if "config.toml" in namelist else None

    try:
        log_activity(db, "settings", "Restauration d'une sauvegarde de données")
    except Exception:
        pass

    try:
        from sqlalchemy import text
        try:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
        except Exception:
            pass
        engine.dispose()

        if db_path.exists():
            bak_path = db_path.with_suffix(".db.bak")
            shutil.copy2(db_path, bak_path)

        wal_file = Path(f"{db_path}-wal")
        shm_file = Path(f"{db_path}-shm")
        if wal_file.exists():
            try:
                wal_file.unlink()
            except Exception:
                pass
        if shm_file.exists():
            try:
                shm_file.unlink()
            except Exception:
                pass

        with open(db_path, "wb") as f:
            f.write(db_bytes)

        if config_bytes:
            cfg_path = _global_config_path()
            try:
                if cfg_path.parent.exists() and os.access(cfg_path.parent, os.W_OK):
                    with open(cfg_path, "wb") as f:
                        f.write(config_bytes)
            except Exception as e:
                logger.warning(f"Impossible d'écrire config.toml restauré : {e}")

        init_db()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur critique lors du remplacement de la base de données : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du remplacement de la base : {e}")

    background_tasks.add_task(_run_restore_restart)
    return {
        "status": "ok",
        "message": "Sauvegarde restaurée avec succès. L'application redémarre...",
    }


# ---------------------------------------------------------------------------
# Remise à zéro d'usine des données (DATA_ROOT)
# ---------------------------------------------------------------------------


class ResetDataRequest(BaseModel):
    confirm: str


def _clean_dir_contents(dir_path: Path) -> None:
    """Supprime tous les fichiers et sous-dossiers d'un répertoire sans supprimer le répertoire lui-même."""
    if not dir_path.exists() or not dir_path.is_dir():
        return
    for item in dir_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            logger.warning(f"Impossible de supprimer {item} lors du reset des données : {e}")


async def _run_reset_data_restart():
    """Tâche d'arrière-plan après réinitialisation d'usine des données."""
    await asyncio.sleep(1.0)
    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec force_reload après reset-data : {e}")
    await asyncio.sleep(1.0)
    get_profile_handler().restart_services()


@router.post("/system/reset-data")
async def reset_data_system(payload: ResetDataRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """
    Remise à zéro d'usine des données (DATA_ROOT) :
    - Purge tous les fichiers des dossiers de médias (vidéos, audio, radio, vignettes, fonds, logos, logs).
    - Réinitialise la base de données SQLite à zéro avec un schéma vierge.
    - Ne touche STRICTEMENT JAMAIS aux binaires applicatifs (/usr/lib/bobine, %ProgramFiles%, /Applications).
    - Redémarre les services.
    Action IRRÉVERSIBLE exigeant la saisie de 'REINITIALISER'.
    """
    phrase = payload.confirm.strip().upper().replace("É", "E")
    if phrase != "REINITIALISER":
        raise HTTPException(status_code=400, detail="Phrase de confirmation incorrecte. Saisissez REINITIALISER.")

    dirs_to_clean = [
        runtime_settings.media_dir,
        runtime_settings.watch_dir,
        runtime_settings.thumbnails_dir,
        runtime_settings.backgrounds_dir,
        runtime_settings.backgrounds_watch_dir,
        runtime_settings.audio_dir,
        runtime_settings.audio_watch_dir,
        runtime_settings.radio_dir,
        runtime_settings.radio_covers_dir,
        runtime_settings.radio_announcements_dir,
        runtime_settings.radio_watch_dir,
        runtime_settings.branding_dir,
        runtime_settings.logs_dir,
    ]
    for d in dirs_to_clean:
        try:
            _clean_dir_contents(Path(d))
        except Exception as e:
            logger.warning(f"Erreur lors du nettoyage du dossier {d} : {e}")

    if _IS_SQLITE:
        db_path = _get_sqlite_db_path()
        try:
            from sqlalchemy import text
            try:
                with engine.connect() as conn:
                    conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
            except Exception:
                pass
            engine.dispose()

            if db_path and db_path.exists():
                db_path.unlink()
            wal_file = Path(f"{db_path}-wal") if db_path else None
            shm_file = Path(f"{db_path}-shm") if db_path else None
            if wal_file and wal_file.exists():
                try:
                    wal_file.unlink()
                except Exception:
                    pass
            if shm_file and shm_file.exists():
                try:
                    shm_file.unlink()
                except Exception:
                    pass

            init_db()
        except Exception as e:
            logger.error(f"Erreur lors de la remise à zéro de la base de données : {e}")
            raise HTTPException(status_code=500, detail=f"Erreur lors du reset DB : {e}")

    background_tasks.add_task(_run_reset_data_restart)
    return {
        "message": "Remise à zéro des données effectuée. L'application redémarre avec une configuration vierge.",
    }


class LaptopLidPayload(BaseModel):
    prevent_sleep: bool


def _has_laptop_lid() -> bool:
    """Détecte si la machine dispose d'un capot (PC Portable)."""
    if sys.platform == "win32":
        try:
            return psutil.sensors_battery() is not None
        except Exception:
            return False
    # Sous Linux
    lid_proc = Path("/proc/acpi/button/lid")
    if lid_proc.exists():
        try:
            if any(lid_proc.iterdir()):
                return True
        except Exception:
            pass
    try:
        return psutil.sensors_battery() is not None
    except Exception:
        return False


def _get_lid_prevent_sleep() -> bool:
    """Lit si la mise en veille à la fermeture du capot est désactivée."""
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powercfg", "/query", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "0x00000000" in res.stdout or " 0 " in res.stdout
        except Exception as e:
            logger.debug(f"Erreur lecture powercfg capot Windows : {e}")
            return False

    # Sous Linux (GNOME / gsettings)
    if shutil.which("gsettings"):
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.settings-daemon.plugins.power", "lid-close-ac-action"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return "nothing" in res.stdout
        except Exception as e:
            logger.debug(f"Erreur lecture gsettings capot Linux : {e}")

    return False


def _set_lid_prevent_sleep(prevent: bool) -> bool:
    """Modifie le comportement à la fermeture du capot."""
    if sys.platform == "win32":
        try:
            val = "0" if prevent else "1"
            subprocess.run(
                ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION", val],
                check=False,
            )
            subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"], check=False)
            return True
        except Exception as e:
            logger.error(f"Erreur écriture powercfg capot Windows : {e}")
            return False

    # Sous Linux
    if shutil.which("gsettings"):
        try:
            action = "nothing" if prevent else "suspend"
            res = subprocess.run(
                ["gsettings", "set", "org.gnome.settings-daemon.plugins.power", "lid-close-ac-action", action],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception as e:
            logger.error(f"Erreur écriture gsettings capot Linux : {e}")
            return False

    return False


@router.get("/laptop-lid")
def get_laptop_lid():
    """Vérifie si la machine a un capot et renvoie le réglage actuel."""
    has_lid = _has_laptop_lid()
    prevent = _get_lid_prevent_sleep() if has_lid else False
    return {"has_lid": has_lid, "prevent_sleep": prevent}


@router.post("/laptop-lid")
def set_laptop_lid(payload: LaptopLidPayload):
    """Active ou désactive la mise en veille à la fermeture du capot."""
    if not _has_laptop_lid():
        raise HTTPException(status_code=400, detail="Aucun capot détecté sur cet appareil")
    success = _set_lid_prevent_sleep(payload.prevent_sleep)
    if not success:
        raise HTTPException(status_code=500, detail="Impossible d'appliquer le réglage du capot")
    return {"has_lid": True, "prevent_sleep": payload.prevent_sleep}


class OpenPathRequest(BaseModel):
    path: str


_OPENABLE_DIR_FIELDS = (
    "media_dir", "watch_dir", "thumbnails_dir", "backgrounds_dir", "backgrounds_watch_dir",
    "audio_dir", "audio_watch_dir", "radio_dir", "radio_watch_dir", "radio_covers_dir",
    "radio_announcements_dir", "branding_dir", "logs_dir", "subtitles_dir",
)


def _openable_roots() -> list[Path]:
    """Dossiers de données que l'interface propose d'ouvrir (cf. `paths` de
    `GET /api/settings`) : l'endpoint est joignable par tout appareil du
    réseau local, il ne doit pas servir à lancer un gestionnaire de fichiers
    ou à créer des dossiers n'importe où sur la machine."""
    roots = [Path(getattr(runtime_settings, field)).resolve() for field in _OPENABLE_DIR_FIELDS]
    db_url = runtime_settings.database_url
    if db_url.startswith("sqlite:///"):
        roots.append(Path(db_url[len("sqlite:///"):]).resolve().parent)
    return roots


@router.post("/open-path")
def open_path(payload: OpenPathRequest):
    """Ouvre un dossier de données Bobine dans le gestionnaire de fichiers natif de l'OS (xdg-open, explorer, open)."""
    raw_path = payload.path.strip()
    if raw_path.startswith("sqlite:///"):
        raw_path = raw_path[len("sqlite:///"):]
    target = Path(raw_path).expanduser().resolve()
    if target.is_file():
        target = target.parent

    if not any(target == root or root in target.parents for root in _openable_roots()):
        raise HTTPException(status_code=403, detail="Ce chemin n'est pas un dossier de données de Bobine")
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    if is_android():
        return {
            "status": "android",
            "path": str(target),
            "message": "Chemin système Android copié. Accessible via une application de gestion de fichiers ou connexion USB (MTP).",
        }

    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            os.startfile(str(target))
        return {"status": "ok", "path": str(target)}
    except Exception as e:
        logger.warning("Échec de l'ouverture du dossier %s : %s", target, e)
        raise HTTPException(status_code=500, detail=f"Impossible d'ouvrir le gestionnaire de fichiers : {e}")
