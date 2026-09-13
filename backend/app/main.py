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
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from starlette.staticfiles import NotModifiedResponse

from app.config import settings
from app.database import init_db, get_db, SessionLocal
from app.models import AudioTrack, Background, RadioAnnouncement, RadioTrack, Video
from app.playback_manager import get_all_playback_managers
from app.radio_manager import get_radio_manager
from app.routers import (
    videos, playback, schedule, playlists, backgrounds, audio, audio_playlists,
    radio, radio_playlists, radio_announcements, settings as settings_router, logs, import_jobs,
    updates, metrics,
)
from app.utils.radio_utils import content_type_for
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
from app.utils.watcher import start_watcher, stop_watcher
from app.utils.ws_manager import manager as ws_manager

# Profil Android (Lot 15, docs/audit-android-2026-09-11.md §C1) : détecté une
# fois au chargement du module, réutilisé par `health()` et par chaque
# endpoint `stream_*` ci-dessous pour décider s'il faut sortir les appels
# SQLAlchemy synchrones de la boucle d'évènements. `hasattr(sys,
# "getandroidapilevel")` est le même test déjà utilisé plus bas dans ce
# fichier pour le montage du frontend statique — attribut du build CPython
# officiel pour Android, présent uniquement sous Chaquopy.
_IS_ANDROID = hasattr(sys, "getandroidapilevel")


# Log technique (réf. F8.2, Lot 9.6/UX3.18) : mêmes messages que la console
# de dev, en plus écrits dans un fichier consultable/téléchargeable depuis
# l'interface. Rotation par taille (réf. F8.3, tâche 13.3) : 5 Mo x 5 fichiers
# (25 Mo max sur disque) via RotatingFileHandler plutôt que logrotate système —
# autonome (aucune configuration OS à poser au Lot 14), identique en dev et en
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
    # Lot 15 (docs/audit-android-2026-09-11.md §5 étape 15.6) : enregistre la
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
    # Avant le watcher (réf. correctif "déplacement de fichier et commit en
    # base pas atomiques") : aucun import n'est possible tant que l'app n'a
    # pas fini de démarrer, donc tout fichier orphelin trouvé ici provient
    # forcément d'un arrêt brutal du service lors d'une exécution précédente.
    reconcile_orphaned_media()
    start_watcher()
    start_scheduler()
    # Best-effort, no-op sur l'appliance headless (avahi s'en charge déjà) —
    # cf. app/utils/mdns.py.
    start_mdns_responder(settings.port)
    # 24/7 (réf. lot L7, D10).
    await autostart_default_radio_playlist()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.start_position_broadcast_loop()
    get_radio_manager().start_position_broadcast_loop()
    # Règles temporelles des rappels (réf. lot L6, D11) : toutes les X
    # minutes / à heures fixes — la règle « toutes les N musiques » n'a rien
    # de temporel, elle est vérifiée à chaque fin de piste (routers/playback.py).
    start_radio_announcement_scheduler()
    yield
    # Shutdown : arrêt propre du scheduler et du watcher.
    stop_scheduler()
    stop_watcher()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.stop_position_broadcast_loop()
    get_radio_manager().stop_position_broadcast_loop()
    await stop_radio_announcement_scheduler()
    stop_mdns_responder()


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

# Enregistrement des routeurs
app.include_router(videos.router)
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
app.include_router(logs.router)
app.include_router(import_jobs.router)
app.include_router(updates.router)
app.include_router(metrics.router)


_KIOSK_PROCESS_NAMES = ("chromium", "chromium-browser", "chrome", "msedge", "google chrome")


def _kiosk_process_alive() -> str:
    """Présence d'un processus de navigateur kiosque sur la machine (le
    backend tourne sur le même hôte). `psutil` (déjà une dépendance du
    projet) remplace `pgrep` — absent de Windows — depuis
    PortabiliteCrossPlatformX Lot 1 ; fonctionne à l'identique sur
    Linux/Windows/macOS. Le nom de process macOS de Chrome est "Google
    Chrome" (avec espace) — `"google chrome"` couvre ce cas après le
    `.lower()` ci-dessous ; sans lui, aucun préfixe ne matchait "google
    chrome" et le kiosque macOS aurait toujours été rapporté "down"
    (Lot 3). "unknown" si l'énumération des process échoue (rare — droits
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

    # Lot 15 (docs/audit-android-2026-09-11.md §C1) : `SELECT 1` synchrone
    # sorti de la boucle d'évènements — appelé toutes les 30s par le
    # watchdog systemd sur les profils desktop, et potentiellement par une
    # supervision externe sur Android, il ne doit jamais retarder les autres
    # requêtes en vol.
    components["database"] = await run_in_threadpool(_check_database)

    # `_kiosk_process_alive()` énumère TOUS les processus du système
    # (`psutil.process_iter`) — non pertinent sur Android (aucun kiosque
    # Chromium à détecter, cf. `_kiosk_process_alive` ci-dessus) et
    # coûteux sous SELinux Android (chaque `/proc/<pid>` refusé lève une
    # exception interceptée). Réf. audit §2 "écarts secondaires".
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
    à tous ses affichages de l'heure (réf. correctif horloge TV kiosk).
    La précision réseau LAN (~0.5 ms) est largement suffisante pour un affichage
    à la seconde.
    """
    return {"server_ts": int(time.time() * 1000)}


async def _range_stream_response(file_path: Path, range: str | None, content_type: str) -> StreamingResponse:
    """
    Sert un fichier avec support HTTP Range (nécessaire pour la lecture directe
    et le saut dans la timeline). Partagé par tous les flux média (vidéos,
    fonds animés, pistes audio) : même logique de découpage par octets quel
    que soit le type de contenu.

    Utilise aiofiles pour une lecture disque non-bloquante : le thread de
    l'event loop reste disponible pour les autres requêtes pendant le streaming.
    """
    # Lot 15 (docs/audit-android-2026-09-11.md §C1) : `exists()`/`stat()`
    # sortis de la boucle — sur le stockage externe Android (FUSE), même un
    # simple `stat` a un coût mesurable ; chaque requête Range (plusieurs
    # par seconde pendant une lecture) en fait un. Sans effet mesurable sur
    # les autres plateformes (appel déjà quasi instantané sur ext4/NTFS/APFS).
    exists = await run_in_threadpool(file_path.exists)
    if not exists:
        raise HTTPException(status_code=404, detail="Fichier manquant sur le disque")

    file_size = (await run_in_threadpool(file_path.stat)).st_size
    start, end = 0, file_size - 1

    if range:
        try:
            # format attendu: "bytes=0-1048576" ou "bytes=1000-" ou "bytes=-1000"
            range_str = range.replace("bytes=", "").strip()
            parts = range_str.split("-")
            if parts[0]:
                start = int(parts[0])
                if len(parts) > 1 and parts[1]:
                    end = int(parts[1])
            elif len(parts) > 1 and parts[1]:
                # Plage suffixée (ex: bytes=-500 pour les 500 derniers octets)
                suffix_len = int(parts[1])
                start = max(0, file_size - suffix_len)
                end = file_size - 1
        except Exception:
            raise HTTPException(status_code=400, detail="Header de Range invalide")

    # Clamping pour s'assurer que les index restent dans les limites du fichier
    start = max(0, min(start, file_size - 1))
    end = max(start, min(end, file_size - 1))
    chunk_size = end - start + 1

    # Taille de bloc de lecture : 1 Mo sur Android (Lot 15, réf. audit §5
    # étape 15.2) — moins d'allers-retours à travers le démon FUSE du
    # stockage externe qu'à 128 Ko, mesurable sur un flux 4K/60fps à haut
    # débit. 128 Ko ailleurs (inchangé), où le coût par appel est négligeable.
    read_block_size = 1024 * 1024 if _IS_ANDROID else 8192 * 16

    async def file_generator():
        async with aiofiles.open(file_path, "rb") as f:
            await f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                chunk = await f.read(min(read_block_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": content_type,
    }
    if range:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    return StreamingResponse(
        file_generator(), status_code=206 if range else 200, headers=headers
    )


@app.get("/api/videos/{video_id}/stream")
async def stream_video(
    video_id: int,
    range: str | None = Header(None),
    db: Session = Depends(get_db),
):
    video = await run_in_threadpool(lambda: db.query(Video).filter(Video.id == video_id).first())
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    return await _range_stream_response(Path(video.file_path), range, "video/mp4")


_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@app.get("/api/backgrounds/{background_id}/stream")
async def stream_background(
    background_id: int,
    range: str | None = Header(None),
    db: Session = Depends(get_db),
):
    background = await run_in_threadpool(lambda: db.query(Background).filter(Background.id == background_id).first())
    if not background:
        raise HTTPException(status_code=404, detail="Fond animé non trouvé")
    suffix = Path(background.file_path).suffix.lower()
    # Fond figé (réf. mission "fond figé ou animé") : servi par le même
    # endpoint de streaming par plage que les vidéos — une image tient
    # largement en une seule plage, aucune adaptation du flux nécessaire.
    if suffix in _IMAGE_CONTENT_TYPES:
        return await _range_stream_response(Path(background.file_path), range, _IMAGE_CONTENT_TYPES[suffix])
    content_type = "video/webm" if suffix == ".webm" else "video/mp4"
    return await _range_stream_response(Path(background.file_path), range, content_type)


@app.get("/api/audio/tracks/{track_id}/stream")
async def stream_audio_track(
    track_id: int,
    range: str | None = Header(None),
    db: Session = Depends(get_db),
):
    track = await run_in_threadpool(lambda: db.query(AudioTrack).filter(AudioTrack.id == track_id).first())
    if not track:
        raise HTTPException(status_code=404, detail="Piste audio non trouvée")
    return await _range_stream_response(Path(track.file_path), range, "audio/mpeg")


@app.get("/api/radio/tracks/{track_id}/stream")
async def stream_radio_track(
    track_id: int,
    range: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Flux audio d'un morceau radio. Type MIME déduit de l'extension (tous
    formats web, réf. A2 : les non-web sont transcodés en .m4a à l'import)."""
    track = await run_in_threadpool(lambda: db.query(RadioTrack).filter(RadioTrack.id == track_id).first())
    if not track:
        raise HTTPException(status_code=404, detail="Morceau non trouvé")
    return await _range_stream_response(Path(track.file_path), range, content_type_for(track.file_path))


@app.get("/api/radio/tracks/{track_id}/cover")
async def stream_radio_cover(
    track_id: int,
    range: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Pochette d'un morceau radio (JPEG normalisé, extrait ID3 ou uploadé)."""
    track = await run_in_threadpool(lambda: db.query(RadioTrack).filter(RadioTrack.id == track_id).first())
    if not track or not track.cover_path:
        raise HTTPException(status_code=404, detail="Pochette non trouvée")
    return await _range_stream_response(Path(track.cover_path), range, "image/jpeg")


@app.get("/api/radio/announcements/{announcement_id}/stream")
async def stream_radio_announcement(
    announcement_id: int,
    range: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Flux audio d'un rappel (réf. lot L6)."""
    announcement = await run_in_threadpool(lambda: db.query(RadioAnnouncement).filter(RadioAnnouncement.id == announcement_id).first())
    if not announcement:
        raise HTTPException(status_code=404, detail="Rappel non trouvé")
    return await _range_stream_response(Path(announcement.file_path), range, content_type_for(announcement.file_path))


# Montage des dossiers statiques requis
# Miniatures
thumbnails_path = Path(settings.thumbnails_dir)
thumbnails_path.mkdir(parents=True, exist_ok=True)
app.mount("/api/thumbnails", StaticFiles(directory=str(thumbnails_path)), name="thumbnails")

# Branding (logo personnalisé, réf. mission "customiser le logo") : DOIT être
# monté avant le catch-all frontend ci-dessous, sinon la route serait masquée.
branding_path = Path(settings.branding_dir)
branding_path.mkdir(parents=True, exist_ok=True)
app.mount("/api/branding", StaticFiles(directory=str(branding_path)), name="branding")

# Frontend Next.js statique (si compilé et présent dans out/). `__file__`
# ne pointe plus vers un fichier du dépôt une fois figé par PyInstaller
# (BobineBackend.exe, réf. PortabiliteCrossPlatformX Lot 1) : dans ce cas,
# `frontend/out/` est placé par l'installeur juste à côté de l'exécutable
# plutôt qu'à sa position relative dans le dépôt — SAUF sur macOS (Lot 3,
# même raison qu'`app/config.py::ROOT_DIR` : `BUNDLE()` place les `datas`
# sous `Contents/Resources/`, pas à côté de l'exécutable dans
# `Contents/MacOS/`).
# `sys.getandroidapilevel` : attribut ajouté par le build CPython officiel
# pour Android (présent uniquement sous Chaquopy), moyen standard et fiable
# de détecter ce profil — cf. docs/ARCHITECTURE.md §3.1. Chaquopy
# place le code applicatif sous un dossier fixe `AssetFinder/app/` (pas la
# position relative réelle du dépôt) : `__file__` ne remonte donc pas à un
# `frontend/` sibling de `backend/` comme dans le cas "dépôt" ci-dessous —
# la tâche Gradle `stagePythonSources` (android/app/build.gradle.kts, Lot 2)
# place plutôt le frontend compilé en `frontend_out/`, sibling du paquet
# `app/` lui-même (donc 2 `.parent`, pas 3).
if hasattr(sys, "getandroidapilevel"):
    frontend_out = Path(__file__).resolve().parent.parent / "frontend_out"
elif getattr(sys, "frozen", False):
    if platform.system() == "Darwin":
        frontend_out = Path(sys.executable).resolve().parent.parent / "Resources" / "frontend" / "out"
    else:
        frontend_out = Path(sys.executable).resolve().parent / "frontend" / "out"
else:
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
class RevalidateStaticFiles(StaticFiles):
    """StaticFiles standard, sauf `Cache-Control: no-cache` sur chaque
    réponse (réf. correctif "une mise à jour de l'app ne se voit pas tant
    qu'on n'a pas vidé le cache") : le dossier `frontend/out` exporté par
    Next.js/Turbopack a son horodatage normalisé à une date fixe très
    ancienne (01/02/1980, cf. étape de build reproductible) par tous les
    pipelines de paquetage (APK Android, PyInstaller...) — sans en-tête
    Cache-Control explicite, Starlette ne pose que `Last-Modified` d'après
    cette date, et un navigateur applique alors le calcul heuristique de
    fraîcheur de la RFC 7234 (fraîcheur ≈ 10 % de l'âge depuis
    Last-Modified) : avec ~46 ans d'écart, la page/les bundles JS/CSS sont
    alors considérés "frais" pendant des ANNÉES et ne sont plus jamais
    re-demandés au serveur, même après une réinstallation de l'app avec du
    code différent — reproduit concrètement sur la tablette Android (le
    cache HTTP de la WebView, distinct du Cache Storage API que vide déjà
    le bouton « Synchronisation des écrans », survit à un `adb install -r`).

    Lot 15, correction post-déploiement, DEUX bugs distincts trouvés en
    testant pour de vrai sur la tablette pilote Android (pas seulement en
    relisant le code) — cf. docs/audit-android-2026-09-11.md :

    1. Le paragraphe ci-dessus affirmait à tort que l'ETag de Starlette est
       "correctement basé sur le contenu". **Faux, vérifié dans la source**
       (`starlette.responses.FileResponse.set_stat_headers`) : l'ETag par
       défaut est `md5(mtime + "-" + taille)`, PAS un hachage des octets du
       fichier. Le mtime étant normalisé à une date fixe identique sur
       CHAQUE build, l'ETag ne dépendait en pratique que de la taille en
       octets — deux versions différentes d'un même fichier peuvent avoir
       la même taille par coïncidence et obtenir le même ETag.

    2. **Insuffisant à lui seul, deuxième bug trouvé après un premier
       correctif encore incomplet** : `StaticFiles.is_not_modified()`
       (appelée par le `file_response()` par défaut) vérifie `If-None-Match`
       PUIS, seulement si ABSENT de la requête, retombe sur une comparaison
       `If-Modified-Since` vs `Last-Modified` — et `Last-Modified` reste,
       lui, TOUJOURS calculé depuis le mtime figé (01/02/1980, cf.
       ci-dessus), jamais corrigé par le point 1. Un client qui envoie
       `If-Modified-Since` sans `If-None-Match` (constaté empiriquement :
       le cache HTTP natif de la WebView Android ne rejoue pas
       systématiquement l'ETag) obtient alors TOUJOURS "non modifié" —
       n'importe quelle date envoyée est postérieure à 1980. **Reproduit et
       confirmé par une requête directe** (`curl -H "If-Modified-Since:
       ..." → 304` même avec un ETag fraîchement recalculé et différent).

    Les deux corrigés ensemble : ETag recalculé depuis un hachage réel du
    contenu (coût négligeable, uniquement les petits fichiers statiques du
    frontend — les médias passent par `_range_stream_response`, jamais par
    cette classe), et la revalidation ne considère PLUS QUE cet ETag — plus
    aucun repli sur `If-Modified-Since`/`Last-Modified`, structurellement
    inutilisables tant que le mtime reste figé par le build reproductible.
    Un client sans `If-None-Match` du tout reçoit toujours le contenu
    complet (200), jamais un 304 dont la fraîcheur ne peut être garantie.
    """

    def file_response(self, full_path, stat_result, scope, status_code: int = 200):
        request_headers = Headers(scope=scope)
        response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        try:
            with open(full_path, "rb") as f:
                content_hash = hashlib.md5(f.read(), usedforsecurity=False).hexdigest()
            response.headers["etag"] = f'"{content_hash}"'
        except OSError:
            # Repli sur l'ETag mtime+size par défaut de Starlette si le
            # fichier n'est plus lisible entre le stat() et cette lecture
            # (rare course, ex. suppression concurrente) — ne doit jamais
            # faire échouer la réponse.
            pass

        # Comparaison ETag SEULE (pas `self.is_not_modified()`, qui retombe
        # sur If-Modified-Since/Last-Modified quand If-None-Match est
        # absent — cf. point 2 ci-dessus, c'est précisément ce repli qui
        # servait du contenu périmé). Absence d'If-None-Match == pas de
        # cache connu valide == contenu complet, jamais un 304 par défaut.
        if_none_match = request_headers.get("if-none-match")
        if if_none_match and response.headers["etag"] in (
            tag.strip().removeprefix("W/") for tag in if_none_match.split(",")
        ):
            response = NotModifiedResponse(response.headers)
        response.headers["Cache-Control"] = "no-cache"
        return response


if frontend_out.exists():
    logger.info(f"Montage du frontend statique depuis {frontend_out}")
    app.mount("/", RevalidateStaticFiles(directory=str(frontend_out), html=True), name="frontend")
else:
    logger.warning("Dossier frontend/out introuvable. Le frontend ne sera pas servi par FastAPI (dev direct).")
