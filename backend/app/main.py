import asyncio
import hashlib
import logging
import platform
import sys
import time
import logging.handlers
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

import aiofiles
import psutil
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, StreamingResponse, JSONResponse, FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from starlette.staticfiles import NotModifiedResponse

from app.config import settings
from app.database import init_db, get_db, SessionLocal
from app.models import AudioTrack, Background, RadioAnnouncement, RadioTrack, Setting, Video
from app.playback_manager import get_all_playback_managers
from app.radio_manager import get_all_radio_managers
from app.routers import (
    videos, playback, schedule, playlists, backgrounds, audio, audio_playlists,
    radio, radio_playlists, radio_announcements, settings as settings_router, logs, import_jobs,
    updates, metrics, display, uploads, chapters, devices, diagnostics,
)
from app.utils.android_runtime import is_android
from app.utils.http_compression import (
    MIN_COMPRESSIBLE_SIZE,
    ApiCompressionMiddleware,
    add_vary_accept_encoding,
    gzip_compress,
    is_compressible_media_type,
    request_allows_gzip,
)
from app.utils.media_response import build_media_response
from app.utils.web_profile import choose_rendition, client_can_decode, parse_accept
from app.utils.web_rendition import request_web_rendition
from app.utils.radio_utils import content_type_for
from app.utils import media_native
from app.utils.media_sidecar import close_current_media_client
from app.utils.update_orchestrator import load_persisted_state_at_startup
from app.utils.version import get_app_version
from app.scheduler_manager import (
    autostart_default_radio_playlist,
    start_scheduler,
    stop_scheduler,
)
from app.utils.importer import reconcile_orphaned_media
from app.utils.mdns import start_mdns_responder, stop_mdns_responder
from app.utils.radio_announcement_scheduler import (
    start_radio_announcement_scheduler,
    stop_radio_announcement_scheduler,
)
from app.utils.radio_sound import load_all_sounds_into_managers
from app.utils.watcher import start_watcher, stop_watcher
from app.utils.ws_manager import manager as ws_manager
from app.devices.service import service as devices_service

# Profil Android : détecté une
# fois au chargement du module, réutilisé par `health()` et par chaque
# endpoint `stream_*` ci-dessous pour décider s'il faut sortir les appels
# SQLAlchemy synchrones de la boucle d'évènements. `hasattr(sys,
# "getandroidapilevel")` est le même test déjà utilisé plus bas dans ce
# fichier pour le montage du frontend statique — attribut du build CPython
# officiel pour Android, présent uniquement sous Chaquopy.
_IS_ANDROID = is_android()


# Log technique : mêmes messages que la console
# de dev, en plus écrits dans un fichier consultable/téléchargeable depuis
# l'interface. Rotation par taille : 5 Mo x 5 fichiers
# (25 Mo max sur disque) via RotatingFileHandler plutôt que logrotate système —
# autonome (aucune configuration OS à poser), identique en dev et en
# production, cohérent avec le reste de la config applicative centralisée.
# `/api/logs/technical*` (routers/logs.py) ne sert que le fichier courant
# (`technical.log`) ; les archives (`technical.log.1` etc.) restent accessibles
# directement sur le disque pour un diagnostic approfondi si besoin.
settings.technical_log_path.parent.mkdir(parents=True, exist_ok=True)

# Fichiers temporaires d'upload sur le MÊME disque que les médias (et non /tmp).
# Sur le Wyse, /tmp est un tmpfs en RAM (~3,8 Go) : un gros upload vidéo/audio le
# saturait ("OSError: [Errno 28] No space left on device", remonté côté client
# par Starlette en « There was an error parsing the body ») alors que le disque
# média a des dizaines de Go libres. Régler `tempfile.tempdir` couvre d'un coup
# le spool multipart de Starlette (SpooledTemporaryFile) ET les
# NamedTemporaryFile des routers d'upload (vidéos, cours audio, radio, fonds).
_upload_tmp_dir = Path(settings.media_dir).parent / "tmp"
_upload_tmp_dir.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(_upload_tmp_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            settings.technical_log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup : Initialisation de la BDD, démarrage du watcher et du scheduler
    # enregistre la
    # boucle principale pour ws_manager.broadcast_threadsafe() — doit être
    # posé avant que quoi que ce soit (watcher, endpoints) ne puisse tenter
    # de diffuser depuis un thread hors boucle.
    ws_manager.bind_loop(asyncio.get_running_loop())
    init_db()
    # Recharge l'issue de la dernière mise à jour AVANT toute autre
    # initialisation : un redémarrage déclenché par une mise à jour réussie
    # (ou un service qui a crashé en plein milieu) ne doit pas laisser
    # `GET /api/updates/status` retomber silencieusement à "idle" avant que
    # le frontend n'ait pu lire le résultat réel.
    load_persisted_state_at_startup()
    # Transferts par morceaux abandonnés depuis plus de 24 h (app/utils/staged_uploads.py)
    from app.utils.staged_uploads import purge_stale
    purge_stale()
    _reset_stale_web_rendition_status()
    # Avant le watcher : aucun import n'est possible tant que l'app n'a
    # pas fini de démarrer, donc tout fichier orphelin trouvé ici provient
    # forcément d'un arrêt brutal du service lors d'une exécution précédente.
    reconcile_orphaned_media()
    start_watcher()
    start_scheduler()
    # Best-effort, no-op sur l'appliance headless (avahi s'en charge déjà) —
    # cf. app/utils/mdns.py.
    start_mdns_responder(settings.port)
    # 24/7.
    # Réglages de son persistés des deux sorties radio, chargés avant tout
    # démarrage de lecture pour que le premier état diffusé les contienne.
    with SessionLocal() as sound_db:
        load_all_sounds_into_managers(sound_db)
        # Réglage du composant audio natif (désactivé par défaut) : lu avant tout import.
        media_native.load_from_database(sound_db)
    await autostart_default_radio_playlist()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.start_position_broadcast_loop()
    for radio_manager in get_all_radio_managers().values():
        radio_manager.start_position_broadcast_loop()
    # Règles temporelles des rappels : toutes les X
    # minutes / à heures fixes — la règle « toutes les N musiques » n'a rien
    # de temporel, elle est vérifiée à chaque fin de piste (routers/playback.py).
    start_radio_announcement_scheduler()
    # Surveillance des périphériques (audio, Bluetooth, Wi-Fi) : inerte tant que la fonction est désactivée
    # ou qu'aucun client n'écoute ; une panne du pilote n'affecte jamais la diffusion.
    await devices_service.start()
    yield
    # Shutdown : arrêt propre du scheduler et du watcher.
    stop_scheduler()
    stop_watcher()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.stop_position_broadcast_loop()
    for radio_manager in get_all_radio_managers().values():
        radio_manager.stop_position_broadcast_loop()
    await stop_radio_announcement_scheduler()
    await devices_service.stop()
    stop_mdns_responder()
    close_current_media_client()


app = FastAPI(title="Bobine", version=get_app_version(), lifespan=lifespan)

# Configuration CORS pour le développement
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
# gzip des seules réponses JSON/texte de /api/* (jamais /stream, miniatures,
# Range, WebSocket...) : voir app/utils/http_compression.py. Ajouté APRÈS le
# CORS pour envelopper aussi ses en-têtes ; le frontend statique négocie lui-même
# la compression (RevalidateStaticFiles) afin de garder son ETag par contenu.
app.add_middleware(ApiCompressionMiddleware)

# Enregistrement des routeurs
app.include_router(videos.router)
app.include_router(chapters.router)
app.include_router(playback.router)
app.include_router(playlists.router)
app.include_router(schedule.router)
app.include_router(backgrounds.router)
app.include_router(audio.router)
app.include_router(audio_playlists.router)
app.include_router(radio.router)
app.include_router(radio_playlists.router)
app.include_router(radio_announcements.router)
app.include_router(settings_router.router)
app.include_router(display.router)
app.include_router(logs.router)
app.include_router(import_jobs.router)
app.include_router(uploads.router)
app.include_router(diagnostics.router)
app.include_router(updates.router)
app.include_router(metrics.router)
app.include_router(devices.router)


_KIOSK_PROCESS_NAMES = ("chromium", "chromium-browser", "chrome", "msedge", "google chrome")


def _kiosk_process_alive() -> str:
    """Présence d'un processus de navigateur kiosque sur la machine (le
    backend tourne sur le même hôte). `psutil` (déjà une dépendance du
    projet) remplace `pgrep` — absent de Windows — ; fonctionne à l'identique sur
    Linux/Windows/macOS. Le nom de process macOS de Chrome est "Google
    Chrome" (avec espace) — `"google chrome"` couvre ce cas après le
    `.lower()` ci-dessous ; sans lui, aucun préfixe ne matchait "google
    chrome" et le kiosque macOS aurait toujours été rapporté "down". "unknown" si l'énumération des process échoue (rare — droits
    insuffisants)."""
    try:
        for proc in psutil.process_iter(["name"]):
            proc_name = (proc.info.get("name") or "").lower()
            if any(proc_name.startswith(name) for name in _KIOSK_PROCESS_NAMES):
                return "ok"
    except Exception:
        return "unknown"
    return "down"


@app.get("/api/health")
async def health():
    """Contrôle de santé lisible par machine, consommé par le chien de garde
    `bobine-watchdog` (redémarrage auto d'un composant mort) et par toute
    supervision externe. Vérifie la dépendance critique du backend — la base
    **SQLite** — plus, à titre indicatif, la présence du **kiosque Chromium**.
    Renvoie HTTP 200 si la base répond, sinon 503. L'état du kiosque n'influe
    PAS sur le code HTTP : c'est un composant séparé, que le chien de garde
    redémarre indépendamment du backend."""
    components: dict[str, str] = {}

    def _check_database() -> str:
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
            finally:
                db.close()
            return "ok"
        except Exception:
            return "down"

    # `SELECT 1` synchrone
    # sorti de la boucle d'évènements — appelé toutes les 30s par le
    # watchdog systemd sur les profils desktop, et potentiellement par une
    # supervision externe sur Android, il ne doit jamais retarder les autres
    # requêtes en vol.
    components["database"] = await run_in_threadpool(_check_database)

    # `_kiosk_process_alive()` énumère TOUS les processus du système
    # (`psutil.process_iter`) — non pertinent sur Android (aucun kiosque
    # Chromium à détecter, cf. `_kiosk_process_alive` ci-dessus) et
    # coûteux sous SELinux Android (chaque `/proc/<pid>` refusé lève une
    # exception interceptée)..
    components["kiosk"] = "n/a" if _IS_ANDROID else await run_in_threadpool(_kiosk_process_alive)

    healthy = components["database"] == "ok"
    payload = {"status": "ok" if healthy else "degraded", "components": components}
    if not healthy:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/api/time")
def get_server_time():
    """Retourne l'heure serveur en millisecondes Unix.

    Utilisé par les kiosks clients pour corriger la dérive d'horloge locale :
    le kiosk calcule delta = server_ts - Date.now() et applique ce décalage
    à tous ses affichages de l'heure.
    La précision réseau LAN (~0.5 ms) est largement suffisante pour un affichage
    à la seconde.
    """
    return {"server_ts": int(time.time() * 1000)}


async def _range_stream_response(file_path: Path, request: Request, content_type: str) -> Response:
    """Sert un fichier média avec support HTTP Range complet, en GET comme en
    HEAD — voir `app/utils/media_response.py` (RFC 9110 : plages, If-Range,
    ETag, 416). Partagé par tous les flux média (vidéos, fonds animés, pistes
    audio, pochettes)."""
    return await build_media_response(file_path, request.headers, request.method, content_type)


@app.api_route("/api/videos/{video_id}/stream", methods=["GET", "HEAD"])
async def stream_video(
    video_id: int,
    request: Request,
    profile: str | None = None,
    accept: str | None = None,
    db: Session = Depends(get_db),
):
    """Flux d'une vidéo, avec négociation de la version lisible.

    Sans paramètre : l'original, comme avant. `?accept=h264,hevc` : capacités
    de décodage annoncées par le navigateur (frontend/src/lib/
    clientCodecSupport.ts) — si l'original n'est pas décodable par ce client et
    qu'une version web existe, c'est elle qui est servie. `?profile=web|original`
    force le choix. L'en-tête `X-Bobine-Rendition` indique la version servie."""
    video = await run_in_threadpool(lambda: db.query(Video).filter(Video.id == video_id).first())
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    web_ready = bool(video.web_path) and video.web_status == "ready" and await run_in_threadpool(Path(video.web_path).exists)
    rendition = choose_rendition(
        issues=video.web_issues, web_ready=web_ready, profile=profile, accept=parse_accept(accept),
    )
    if rendition == "original" and not web_ready and accept is not None and video.web_status != "pending":
        # Client incapable de décoder l'original ET aucune version web : si
        # l'administrateur a activé la production automatique, on la lance
        # maintenant (ce premier essai échouera, les suivants seront servis).
        parsed = parse_accept(accept) or set()
        if not client_can_decode(video.web_issues, parsed) and await run_in_threadpool(_auto_web_rendition_enabled, db):
            await run_in_threadpool(request_web_rendition, video.id)

    path = Path(video.web_path) if rendition == "web" else Path(video.file_path)
    response = await _range_stream_response(path, request, "video/mp4")
    response.headers["X-Bobine-Rendition"] = rendition
    return response


def _reset_stale_web_rendition_status() -> None:
    """Une version web « en cours » trouvée au démarrage ne peut venir que d'un
    arrêt brutal du processus : on la ramène à « absente » plutôt que de laisser
    l'interface annoncer indéfiniment une production qui n'existe plus."""
    db = SessionLocal()
    try:
        db.query(Video).filter(Video.web_status == "pending").update({Video.web_status: None})
        db.commit()
    except Exception as e:
        logger.warning(f"Réinitialisation des versions web en attente impossible : {e}")
    finally:
        db.close()


def _auto_web_rendition_enabled(db: Session) -> bool:
    row = db.query(Setting).filter(Setting.key == "auto_web_rendition").first()
    return bool(row and row.value == "true")


_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@app.api_route("/api/backgrounds/{background_id}/stream", methods=["GET", "HEAD"])
async def stream_background(
    background_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    background = await run_in_threadpool(lambda: db.query(Background).filter(Background.id == background_id).first())
    if not background:
        raise HTTPException(status_code=404, detail="Fond animé non trouvé")
    suffix = Path(background.file_path).suffix.lower()
    # Fond figé : servi par le même
    # endpoint de streaming par plage que les vidéos — une image tient
    # largement en une seule plage, aucune adaptation du flux nécessaire.
    if suffix in _IMAGE_CONTENT_TYPES:
        return await _range_stream_response(Path(background.file_path), request, _IMAGE_CONTENT_TYPES[suffix])
    content_type = "video/webm" if suffix == ".webm" else "video/mp4"
    return await _range_stream_response(Path(background.file_path), request, content_type)


@app.api_route("/api/audio/tracks/{track_id}/stream", methods=["GET", "HEAD"])
async def stream_audio_track(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    track = await run_in_threadpool(lambda: db.query(AudioTrack).filter(AudioTrack.id == track_id).first())
    if not track:
        raise HTTPException(status_code=404, detail="Piste audio non trouvée")
    return await _range_stream_response(Path(track.file_path), request, "audio/mpeg")


@app.api_route("/api/radio/tracks/{track_id}/stream", methods=["GET", "HEAD"])
async def stream_radio_track(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Flux audio d'un morceau radio. Type MIME déduit de l'extension (tous
    formats web)."""
    track = await run_in_threadpool(lambda: db.query(RadioTrack).filter(RadioTrack.id == track_id).first())
    if not track:
        raise HTTPException(status_code=404, detail="Morceau non trouvé")
    return await _range_stream_response(Path(track.file_path), request, content_type_for(track.file_path))


@app.api_route("/api/radio/tracks/{track_id}/cover", methods=["GET", "HEAD"])
async def stream_radio_cover(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Pochette d'un morceau radio (JPEG normalisé, extrait ID3 ou uploadé)."""
    track = await run_in_threadpool(lambda: db.query(RadioTrack).filter(RadioTrack.id == track_id).first())
    if not track or not track.cover_path:
        raise HTTPException(status_code=404, detail="Pochette non trouvée")
    return await _range_stream_response(Path(track.cover_path), request, "image/jpeg")


@app.api_route("/api/radio/announcements/{announcement_id}/stream", methods=["GET", "HEAD"])
async def stream_radio_announcement(
    announcement_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Flux audio d'un rappel."""
    announcement = await run_in_threadpool(lambda: db.query(RadioAnnouncement).filter(RadioAnnouncement.id == announcement_id).first())
    if not announcement:
        raise HTTPException(status_code=404, detail="Rappel non trouvé")
    return await _range_stream_response(Path(announcement.file_path), request, content_type_for(announcement.file_path))


class _EnsuredDirStaticFiles(StaticFiles):
    """StaticFiles qui (re)crée son dossier avant de le contrôler : starlette lève sinon une RuntimeError
    (HTTP 500) quand le dossier n'existe pas à la première requête (stockage amovible absent au démarrage,
    remise à zéro, dossier purgé à la main). Une simple image ne doit jamais produire une 500."""

    async def check_config(self) -> None:
        try:
            Path(self.directory).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # stockage indisponible : traité ci-dessous

        try:
            await super().check_config()
        except RuntimeError:
            self.config_checked = False  # réessaiera à la requête suivante
            raise

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except RuntimeError as exc:
            if scope.get("type") != "http" or "does not exist" not in str(exc):
                raise
            from starlette.responses import PlainTextResponse

            await PlainTextResponse("Introuvable", status_code=404)(scope, receive, send)


# Montage des dossiers statiques requis
# Miniatures
thumbnails_path = Path(settings.thumbnails_dir)
thumbnails_path.mkdir(parents=True, exist_ok=True)
app.mount("/api/thumbnails", _EnsuredDirStaticFiles(directory=str(thumbnails_path)), name="thumbnails")

# Branding (logo personnalisé) : DOIT être
# monté avant le catch-all frontend ci-dessous, sinon la route serait masquée.
branding_path = Path(settings.branding_dir)
branding_path.mkdir(parents=True, exist_ok=True)
app.mount("/api/branding", StaticFiles(directory=str(branding_path)), name="branding")

# Frontend Next.js statique (si compilé et présent dans out/). `__file__`
# ne pointe plus vers un fichier du dépôt une fois figé par PyInstaller
# (BobineBackend.exe) : dans ce cas,
# `frontend/out/` est placé par l'installeur juste à côté de l'exécutable
# plutôt qu'à sa position relative dans le dépôt — SAUF sur macOS.
# `sys.getandroidapilevel` : attribut ajouté par le build CPython officiel
# pour Android (présent uniquement sous Chaquopy), moyen standard et fiable
# de détecter ce profil — cf. docs/ARCHITECTURE.md §3.1. Chaquopy
# place le code applicatif sous un dossier fixe `AssetFinder/app/` (pas la
# position relative réelle du dépôt) : `__file__` ne remonte donc pas à un
# `frontend/` sibling de `backend/` comme dans le cas "dépôt" ci-dessous —
# la tâche Gradle `stagePythonSources` (android/app/build.gradle.kts)
# place plutôt le frontend compilé en `frontend_out/`, sibling du paquet
# `app/` lui-même (donc 2 `.parent`, pas 3).
if _IS_ANDROID:
    frontend_out = Path(__file__).resolve().parent.parent / "frontend_out"
elif getattr(sys, "frozen", False):
    if platform.system() == "Darwin":
        frontend_out = Path(sys.executable).resolve().parent.parent / "Resources" / "frontend" / "out"
    else:
        frontend_out = Path(sys.executable).resolve().parent / "frontend" / "out"
else:
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
class RevalidateStaticFiles(StaticFiles):
    """StaticFiles standard, avec revalidation systématique des fichiers du
    frontend exporté (`frontend/out`).

    Deux pièges évités :

    - Les pipelines de paquetage (APK Android, PyInstaller…) normalisent le
      mtime des fichiers à une date fixe très ancienne (01/02/1980, build
      reproductible). Sans `Cache-Control` explicite, le calcul heuristique de
      fraîcheur (RFC 7234, ~10 % de l'âge depuis `Last-Modified`) rendrait la
      page et les bundles JS/CSS « frais » pendant des années : une WebView
      conserverait l'ancien code après une mise à jour. Chaque réponse porte
      donc `Cache-Control: no-cache`.
    - L'ETag par défaut de Starlette est `md5(mtime + "-" + taille)`, pas un
      hachage du contenu : avec un mtime figé, deux versions d'un même fichier
      de même taille partageraient le même ETag, et `If-Modified-Since` /
      `Last-Modified` (toujours 1980) répondraient « non modifié » à tort.
      L'ETag est donc recalculé sur le contenu réel (fichiers statiques
      légers uniquement — les médias passent par `app/utils/media_response.py`)
      et seule la comparaison `If-None-Match` est utilisée. Un client sans
      `If-None-Match` reçoit toujours le contenu complet (200).

    Compression : les fichiers texte (HTML, JS, CSS, JSON, SVG) sont servis en
    gzip quand le client l'accepte (2,7 Mo -> 0,76 Mo pour `frontend/out`). La
    version gzip est une autre représentation : son ETag est `"<md5>-gzip"`
    (jamais le même validateur que la version brute) et `Vary: Accept-Encoding`
    est posé sur tout fichier compressible. Un client qui a déjà en cache la
    version brute (`"<md5>"`) reçoit toujours un 304 tant que le contenu n'a pas
    changé : le contenu est le même, seul l'encodage diffère. Les octets gzip
    sont gardés en mémoire (clé = chemin + hash du contenu, donc invalidés par
    tout changement de fichier) dans une limite de `_GZIP_CACHE_MAX_BYTES`.
    Pas de gzip pour les requêtes `Range`, `HEAD` ou venant du bouclage
    (cf. `request_allows_gzip`).
    """

    _GZIP_CACHE_MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._gzip_cache: dict[tuple[str, str], bytes] = {}
        self._gzip_cache_bytes = 0

    def _gzipped(self, full_path, content_hash: str, data: bytes) -> bytes:
        key = (str(full_path), content_hash)
        compressed = self._gzip_cache.get(key)
        if compressed is None:
            compressed = gzip_compress(data)
            if self._gzip_cache_bytes + len(compressed) > self._GZIP_CACHE_MAX_BYTES:
                self._gzip_cache.clear()
                self._gzip_cache_bytes = 0
            self._gzip_cache[key] = compressed
            self._gzip_cache_bytes += len(compressed)
        return compressed

    async def get_response(self, path: str, scope):
        # Un chemin /api/* qui n'a trouvé aucune route (méthode non déclarée,
        # ressource absente) ne doit JAMAIS recevoir la page HTML 404 du
        # frontend : un client d'API (ou un `HEAD` de sonde) y verrait un
        # faux succès `text/html`. 404 JSON explicite à la place.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Ressource d'API introuvable")
        return await super().get_response(path, scope)

    def file_response(self, full_path, stat_result, scope, status_code: int = 200):
        request_headers = Headers(scope=scope)
        response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        data: bytes | None = None
        content_hash = ""
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            content_hash = hashlib.md5(data, usedforsecurity=False).hexdigest()
            response.headers["etag"] = f'"{content_hash}"'
        except OSError:
            # Repli sur l'ETag mtime+size par défaut de Starlette si le
            # fichier n'est plus lisible entre le stat() et cette lecture
            # (rare course, ex. suppression concurrente) — ne doit jamais
            # faire échouer la réponse (et pas de gzip dans ce cas : `data`
            # reste None).
            pass
        identity_etag = response.headers["etag"]

        gzip_etag: str | None = None
        if is_compressible_media_type(response.headers.get("content-type")):
            add_vary_accept_encoding(response.headers)
            if data is not None and len(data) >= MIN_COMPRESSIBLE_SIZE and request_allows_gzip(scope):
                gzip_etag = f'"{content_hash}-gzip"'

        # Comparaison ETag SEULE (pas `self.is_not_modified()`, qui retombe
        # sur If-Modified-Since/Last-Modified quand If-None-Match est
        # absent — cf. point 2 ci-dessus, c'est précisément ce repli qui
        # servait du contenu périmé). Absence d'If-None-Match == pas de
        # cache connu valide == contenu complet, jamais un 304 par défaut.
        if_none_match = request_headers.get("if-none-match")
        if if_none_match:
            client_tags = {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}
            matched = next((tag for tag in (gzip_etag, identity_etag) if tag and tag in client_tags), None)
            if matched:
                response.headers["etag"] = matched
                response = NotModifiedResponse(response.headers)
                gzip_etag = None
        if gzip_etag is not None:
            headers = {
                name: value
                for name, value in response.headers.items()
                # `accept-ranges` : la version gzip est servie d'un bloc.
                if name not in ("content-length", "etag", "accept-ranges")
            }
            headers["etag"] = gzip_etag
            headers["content-encoding"] = "gzip"
            response = Response(
                self._gzipped(full_path, content_hash, data),
                status_code=status_code,
                headers=headers,
            )
        response.headers["Cache-Control"] = "no-cache"
        return response


if frontend_out.exists():
    logger.info(f"Montage du frontend statique depuis {frontend_out}")
    app.mount("/", RevalidateStaticFiles(directory=str(frontend_out), html=True), name="frontend")
else:
    logger.warning("Dossier frontend/out introuvable. Le frontend ne sera pas servi par FastAPI (dev direct).")
