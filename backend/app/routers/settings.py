import asyncio
import io
import json
import logging
import os
import shutil
import socket
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

from app.config import (
    ROOT_DIR,
    _global_config_path,
    settings as runtime_settings,
)
from app.database import _IS_SQLITE, engine, get_db, init_db
from app.models import Setting
from app.playback_manager import get_playback_manager
from app.utils.activity_log import log_activity
from app.utils.deployment import (
    SUDOERS_FILE,
    UNINSTALL_WRAPPER,
    get_deployment_profile,
    get_profile_handler,
)
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

# Réglages ajustables depuis l'interface (réf. UX3.17), persistés dans la
# table `settings` (clé/valeur) et reflétés immédiatement dans le singleton
# `runtime_settings` en mémoire — le fichier config.toml reste la valeur de
# secours au tout premier démarrage (avant toute modification via l'UI).
_WRITABLE_NUMERIC_FIELDS = {
    "wait_time_between_courses", "volume_default", "audio_chain_timer_seconds",
    "radio_announcement_fade_ms",
}
_WRITABLE_STRING_FIELDS = {"theme", "language", "active_logo", "update_channel", "wired_display_mode"}
# Animation de lancement (réf. mission "activer/désactiver l'animation mp4") :
# suit le pattern des champs STRING (theme/language) ci-dessus, PAS celui des
# champs numériques — ces derniers ne sont réappliqués à `runtime_settings`
# qu'au redémarrage via un cast `int()` en dur (app/config.py::_apply_db_overrides),
# inadapté à un booléen. Un champ bool relu directement depuis la DB à chaque
# `GET /api/settings` (comme theme/language) évite ce piège sans y toucher.
_WRITABLE_BOOL_FIELDS = {"intro_animation_enabled"}
_DEFAULTS = {
    # "clair" (réf. mission "thème par défaut") : version claire du thème
    # Les Mills par défaut — même accent rouge (#e4002b) que
    # "les-mills-sombre", premier écran vu à l'installation.
    "theme": "clair",
    "language": "fr",
    "intro_animation_enabled": "true",
    "active_logo": "default",
    # Canal de mise à jour (réf. mission "Programme Bobine Beta") : "stable"
    # par défaut pour tout le monde — rejoindre la bêta est un choix
    # explicite, jamais l'état de départ d'une installation.
    "update_channel": "stable",
    # Mode d'affichage câblé (réf. cahier des charges affichage hybride) :
    # "headless" par défaut (desktop/laptop/wyse), "dual_screen" pour tablette.
    "wired_display_mode": "headless",
}
_LOGO_FILENAME = "logo.png"
# "les-mills-sombre" est la clé interne historique du thème "Sombre" (réf.
# mission thèmes cinéma) — inchangée pour ne rien casser sur les
# installations existantes, seul son libellé affiché change côté frontend.
_VALID_THEMES = {
    "les-mills-sombre", "clair", "lune", "menthe", "automne", "hiver",
    "chili", "ciel", "orchidee", "taupe", "charbon", "charbon-sombre",
    "beige", "lavande", "miel", "coco",
}
_VALID_ACTIVE_LOGOS = {"default", "custom"}
_VALID_UPDATE_CHANNELS = {"stable", "beta"}
_VALID_WIRED_DISPLAY_MODES = {"dual_screen", "headless"}

# Sortie affichée par CANAL de diffusion (réf. mission "canaux de diffusion
# précis") : "câblé" (l'écran physiquement connecté au Wyse, en 127.0.0.1) et
# "réseau" (tout autre appareil du LAN qui ouvre /kiosk ou /cinema) sont
# désormais deux réglages INDÉPENDANTS — l'admin peut par exemple laisser le
# câblé en kiosk piloté pendant que le réseau bascule en libre-service
# cinéma, ou l'inverse. "kiosk" par défaut sur les deux canaux. Persisté en
# base sous deux clés distinctes : survit aux redémarrages.
_DISPLAY_OUTPUT_KEYS = {"cable": "display_output_cable", "network": "display_output_network"}
_DISPLAY_OUTPUTS = ("kiosk", "cinema")
_DISPLAY_CHANNELS = ("cable", "network")


class DisplayOutputUpdate(BaseModel):
    channel: str
    output: str


class SettingsUpdate(BaseModel):
    wait_time_between_courses: int | None = None
    volume_default: int | None = None
    audio_chain_timer_seconds: int | None = None
    radio_announcement_fade_ms: int | None = None
    theme: str | None = None
    language: str | None = None
    intro_animation_enabled: bool | None = None
    active_logo: str | None = None
    update_channel: str | None = None
    wired_display_mode: str | None = None


def _get_db_value(db: Session, key: str) -> str | None:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else None


def _logo_path() -> Path:
    return Path(runtime_settings.branding_dir) / _LOGO_FILENAME


_cached_local_ip: str | None = None
_cached_local_ip_time: float = 0.0
_LOCAL_IP_CACHE_TTL = 15.0  # Actualisation toutes les 15 secondes maximum


def _get_local_ip() -> str | None:
    """Astuce socket UDP classique (aucun paquet réellement envoyé) : IP de
    l'interface que le système utiliserait pour joindre le LAN — équivalent
    de `hostname -I` sans sous-processus ni dépendance externe. Aide à la
    découverte réseau (réf. mission "IP obtenue par l'appareil"), en
    complément de la découverte mDNS (bobine.local, cf. install.sh).

    Mise en cache avec TTL court (15s) pour éviter des appels socket répétés
    tout en permettant à l'IP de s'actualiser automatiquement lors d'un
    changement de réseau ou d'attribution DHCP sans redémarrer le serveur."""
    global _cached_local_ip, _cached_local_ip_time
    now = time.time()
    if _cached_local_ip is not None and (now - _cached_local_ip_time) < _LOCAL_IP_CACHE_TTL:
        return _cached_local_ip

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.2)
    try:
        s.connect(("8.8.8.8", 80))
        _cached_local_ip = s.getsockname()[0]
        _cached_local_ip_time = now
    except OSError:
        _cached_local_ip = None
        _cached_local_ip_time = now - (_LOCAL_IP_CACHE_TTL - 3.0)
    finally:
        s.close()
    return _cached_local_ip


@router.get("")
def get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    theme = _get_db_value(db, "theme") or _DEFAULTS["theme"]
    language = _get_db_value(db, "language") or _DEFAULTS["language"]
    intro_animation_enabled = (
        _get_db_value(db, "intro_animation_enabled") or _DEFAULTS["intro_animation_enabled"]
    ) == "true"
    has_custom = _logo_path().exists()
    active_logo = _get_db_value(db, "active_logo") or _DEFAULTS["active_logo"]
    if active_logo == "custom" and not has_custom:
        active_logo = "default"
    update_channel = _get_db_value(db, "update_channel") or _DEFAULTS["update_channel"]
    default_wired_mode = "dual_screen" if get_deployment_profile() == "android" else "headless"
    wired_display_mode = _get_db_value(db, "wired_display_mode") or default_wired_mode
    if wired_display_mode not in _VALID_WIRED_DISPLAY_MODES:
        wired_display_mode = default_wired_mode
    return {
        "wait_time_between_courses": runtime_settings.wait_time_between_courses,
        "volume_default": runtime_settings.volume_default,
        "audio_chain_timer_seconds": runtime_settings.audio_chain_timer_seconds,
        # Profil de déploiement (réf. PortabiliteCrossPlatformX §5.1) : le
        # frontend s'en sert pour adapter le texte/comportement de la zone
        # Désinstaller/Réinitialiser selon la plateforme, sans dupliquer la
        # logique de détection côté client.
        "deployment_profile": get_deployment_profile(),
        "theme": theme,
        "language": language,
        "intro_animation_enabled": intro_animation_enabled,
        "has_custom_logo": has_custom,
        "active_logo": active_logo,
        # Programme Bobine Beta (réf. mission "canal Stable/Bêta") : "stable"
        # ou "beta", consommé par GET /api/updates/check pour choisir
        # l'endpoint GitHub interrogé.
        "update_channel": update_channel,
        # Mode d'affichage câblé (réf. cahier des charges affichage hybride) :
        # "dual_screen" (pupitre tactile + vidéo HDMI) ou "headless" (cinéma autonome).
        "wired_display_mode": wired_display_mode,
        # Aide à la découverte réseau (réf. mission "IP obtenue par
        # l'appareil"), en complément de bobine.local (avahi, cf. install.sh).
        "network": {
            "local_ip": _get_local_ip(),
            "port": runtime_settings.port,
            "mdns_url": "http://bobine.local",
        },
        # Réglages du duck/fondu des rappels radio (réf. lot L6) : consommés
        # par /radio pour le fondu musique pendant une annonce, ET pour le
        # fondu du rappel lui-même (réf. correctif "vitesse du fade
        # réglable"). radio_announcement_duck_level reste en lecture seule
        # pour l'instant (pas demandé) ; fade_ms est éditable (cf.
        # _WRITABLE_NUMERIC_FIELDS).
        "radio_announcement_duck_level": runtime_settings.radio_announcement_duck_level,
        "radio_announcement_fade_ms": runtime_settings.radio_announcement_fade_ms,
        # Chemins en lecture seule (réf. UX3.17 "chemins d'information")
        "paths": {
            "database_url": runtime_settings.database_url,
            "media_dir": runtime_settings.media_dir,
            "watch_dir": runtime_settings.watch_dir,
            "thumbnails_dir": runtime_settings.thumbnails_dir,
            "backgrounds_dir": runtime_settings.backgrounds_dir,
            "backgrounds_watch_dir": runtime_settings.backgrounds_watch_dir,
            "audio_dir": runtime_settings.audio_dir,
            "audio_watch_dir": runtime_settings.audio_watch_dir,
        },
    }


# Dossiers de médias dont on additionne l'empreinte disque pour l'indicateur
# de stockage (réf. mission "un indicateur de la quantité de stockage restant
# pour monitorer la capacité de l'application") : ce que l'application
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
    Indicateur de capacité de stockage (réf. mission "monitorer la capacité de
    l'application") : espace disque du volume qui héberge les médias (total /
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
    }


_last_cpu_time: float = 0.0
_last_proc_ticks: int = 0


def _get_system_usage_values() -> tuple[float, int, int, float]:
    """Retourne (cpu_percent, memory_total_bytes, memory_used_bytes, memory_percent).
    Sous Android (API 34+), l'accès à /proc/stat est bloqué par SELinux pour les
    applications du domaine untrusted_app, faisant échouer psutil.cpu_percent
    avec PermissionError. Cette fonction utilise psutil en priorité, avec repli
    gracieux sur /proc/meminfo et la mesure CPU du processus (/proc/self/stat)."""
    global _last_cpu_time, _last_proc_ticks
    cpu_percent = 0.0
    mem_total = 0
    mem_used = 0
    mem_percent = 0.0

    # 1. CPU
    try:
        cpu_percent = float(psutil.cpu_percent(interval=0.1))
    except Exception:
        try:
            proc = psutil.Process()
            cpu_percent = float(proc.cpu_percent(interval=0.1))
        except Exception:
            try:
                with open("/proc/self/stat", "r") as f:
                    parts = f.read().split()
                    utime = int(parts[13])
                    stime = int(parts[14])
                    total_ticks = utime + stime
                now = datetime.now(timezone.utc).timestamp()
                clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 100)) if hasattr(os, "sysconf") else 100
                cpu_count = os.cpu_count() or 1
                if _last_cpu_time > 0 and now > _last_cpu_time:
                    delta_sec = now - _last_cpu_time
                    delta_ticks = total_ticks - _last_proc_ticks
                    if delta_sec > 0 and delta_ticks >= 0:
                        pct = (delta_ticks / clk_tck) / delta_sec / cpu_count * 100.0
                        cpu_percent = round(min(100.0, max(0.0, pct)), 1)
                _last_cpu_time = now
                _last_proc_ticks = total_ticks
            except Exception:
                cpu_percent = 0.0

    # 2. Mémoire
    try:
        memory = psutil.virtual_memory()
        mem_total = memory.total
        mem_used = memory.total - memory.available
        mem_percent = memory.percent
    except Exception:
        try:
            meminfo: dict[str, int] = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        meminfo[k] = int(v) * 1024
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            used = max(0, total - available)
            pct = round((used / total) * 100, 1) if total > 0 else 0.0
            mem_total = total
            mem_used = used
            mem_percent = pct
        except Exception:
            pass

    return cpu_percent, mem_total, mem_used, mem_percent


@router.get("/system")
def get_system_usage() -> dict[str, Any]:
    """Charge CPU et RAM (réf. mission "supervision cpu/ram en plus du
    stockage") : endpoint séparé de /storage (interval bloquant court pour
    une mesure CPU instantanée fiable). Robuste sous Android (SELinux)."""
    cpu_percent, mem_total, mem_used, mem_percent = _get_system_usage_values()
    return {
        "cpu_percent": cpu_percent,
        "memory_total_bytes": mem_total,
        "memory_used_bytes": mem_used,
        "memory_percent": mem_percent,
    }


@router.put("")
async def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    # `.model_dump` (Pydantic v2) sauf sur le profil Android où `.dict` (v1)
    # est le seul disponible (cf. docs/ARCHITECTURE.md §3.1).
    dump = getattr(payload, "model_dump", None) or payload.dict
    updates = dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun paramètre fourni")

    for key, value in updates.items():
        if value is None:
            # `exclude_unset=True` ne garde que les clés explicitement
            # envoyées — un `null` explicite (distinct d'une clé omise) n'a
            # de sens pour aucun de ces champs et serait sinon stocké tel
            # quel comme la chaîne littérale "None" (réf. revue de code :
            # `str(None)` puis relu `== "true"` → False silencieusement pour
            # un booléen, ou `int(None)` → crash pour un champ numérique).
            raise HTTPException(status_code=400, detail=f"{key} ne peut pas être nul")
        stored_value = str(value)
        if key in _WRITABLE_NUMERIC_FIELDS and value is not None:
            if value < 0:
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
            if key == "update_channel" and value not in _VALID_UPDATE_CHANNELS:
                raise HTTPException(status_code=400, detail="Canal de mise à jour invalide (attendu 'stable' ou 'beta')")
            if key == "wired_display_mode" and value not in _VALID_WIRED_DISPLAY_MODES:
                raise HTTPException(
                    status_code=400,
                    detail="Mode d'affichage câblé invalide (attendu 'dual_screen' ou 'headless')",
                )
        elif key in _WRITABLE_BOOL_FIELDS and value is not None:
            # "true"/"false" minuscule (pas str(bool(...)) => "True"/"False")
            # pour rester cohérent avec la lecture `== "true"` de get_settings().
            stored_value = "true" if value else "false"

        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = stored_value
        else:
            db.add(Setting(key=key, value=stored_value))

        # Effet immédiat sur le process en cours pour les champs numériques
        # (le singleton `runtime_settings` est un objet mutable partagé par
        # tout le backend : playback_manager, scheduler_manager, etc. lisent
        # ses attributs directement à chaque usage, pas seulement au démarrage).
        if key in _WRITABLE_NUMERIC_FIELDS:
            setattr(runtime_settings, key, int(value))

    db.commit()
    logger.info(f"Paramètres mis à jour : {updates}")
    result = get_settings(db)

    # Diffusion temps réel (correctif "thème ne se synchronise pas sur
    # l'écran cinéma") : AppSettingsProvider ne chargeait le thème/langue
    # qu'une fois au montage — un changement décidé depuis l'admin pendant
    # que /cinema ou un autre écran était déjà ouvert n'y apparaissait donc
    # jamais sans rechargement manuel. Diffusé uniquement si l'un des deux a
    # effectivement changé (ou l'animation de lancement, même besoin : les
    # kiosques tournent 24/7 sans rechargement), pour ne pas générer de
    # trafic WebSocket inutile à chaque réglage numérique (countdown, volume...).
    if (
        "theme" in updates
        or "language" in updates
        or "intro_animation_enabled" in updates
        or "active_logo" in updates
        or "wired_display_mode" in updates
    ):
        await ws_manager.broadcast({
            "event": "settings_change",
            "theme": result["theme"],
            "language": result["language"],
            "intro_animation_enabled": result["intro_animation_enabled"],
            "has_custom_logo": result["has_custom_logo"],
            "active_logo": result["active_logo"],
            "wired_display_mode": result["wired_display_mode"],
        })

    # Diffusion dédiée display_mode_change sur canal "cable" (CDC §4.1 affichage hybride)
    if "wired_display_mode" in updates:
        await ws_manager.broadcast({
            "event": "display_mode_change",
            "channel": "cable",
            "mode": result["wired_display_mode"],
        })

    return result


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Upload d'un logo personnalisé (réf. mission "customiser le logo") :
    normalisé en PNG sous un nom fixe (`_LOGO_FILENAME`) pour une URL stable
    (/api/branding/logo.png), remplace tout logo custom précédent.
    Active automatiquement `active_logo = "custom"` tout en permettant à l'utilisateur
    de basculer manuellement vers le logo Bobine à tout moment."""
    import io

    from PIL import Image, UnidentifiedImageError

    raw = await file.read()
    # Garde-fou taille (réf. revue de code) : matériel modeste visé par ce
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
        # Capture large (pas seulement UnidentifiedImageError, réf. revue de
        # code) : un fichier tronqué (OSError) ou une bombe de décompression
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
    (réf. verrouillage cinéma dans routers/playback.py)."""
    value = _get_db_value(db, _DISPLAY_OUTPUT_KEYS[channel])
    return value if value in _DISPLAY_OUTPUTS else "kiosk"


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
    de l'autre. L'application est instantanée : l'évènement est diffusé à
    tous les clients WebSocket, et la page concernée (l'écran câblé pour le
    canal "cable", tout autre /kiosk ou /cinema du réseau pour "network")
    navigue d'elle-même vers l'autre page en le recevant.
    """
    if payload.channel not in _DISPLAY_CHANNELS:
        raise HTTPException(status_code=400, detail="Canal invalide (attendu 'cable' ou 'network')")
    if payload.output not in _DISPLAY_OUTPUTS:
        raise HTTPException(status_code=400, detail="Sortie invalide (attendu 'kiosk' ou 'cinema')")

    key = _DISPLAY_OUTPUT_KEYS[payload.channel]
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = payload.output
    else:
        db.add(Setting(key=key, value=payload.output))
    db.commit()

    # Bascule vers cinéma : coupe ce qui jouait côté kiosk sur CE canal plutôt
    # que de le laisser tourner en arrière-plan sans écran pour l'afficher —
    # sans ça l'état serveur restait "en cours" (position qui continue
    # d'avancer, "En direct" affiché côté admin) et pouvait reprendre en
    # l'état si on rebasculait sur kiosk plus tard, en conflit avec ce que
    # l'utilisateur regarde alors en cinéma (réf. retour utilisateur
    # "couper et retirer la vidéo qui se jouait sur le kiosk").
    if payload.output == "cinema":
        manager = get_playback_manager(payload.channel)
        current = manager.snapshot()
        if current["current_video"] or current["current_background"] or current["current_audio_course"]:
            title = (
                (current["current_video"] or {}).get("title")
                or (current["current_background"] or {}).get("title")
                or (current["current_audio_course"] or {}).get("title")
            )
            log_activity(db, "playback_stopped", title)
        await manager.stop()

    await ws_manager.broadcast({"event": "display_output", "channel": payload.channel, "output": payload.output})
    logger.info(f"Sortie {payload.channel} basculée sur /{payload.output}")
    return {
        "cable": get_display_output_value(db, "cable"),
        "network": get_display_output_value(db, "network"),
    }


async def _run_full_reset():
    """
    Diffuse un rechargement à tous les navigateurs connectés (PC/mobile/coach)
    puis redémarre les services via le handler du profil courant (réf. audit
    plan-corrections-bugs, point 4 — bouton de réinitialisation complète, et
    PortabiliteCrossPlatformX §5.1/§5.2 pour le branchement par profil).
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
    Réinitialisation complète (réf. audit plan-corrections-bugs, point 4) :
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
    """Remise à zéro complète de la machine (réf. bouton « Désinstaller »).
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
    l'enveloppe systemd-run de l'appliance, cf. PortabiliteCrossPlatformX
    §5.3) — la réponse contient les instructions de désinstallation propres
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
        zf.write(db_path, arcname="database.db")

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

