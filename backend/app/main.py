import asyncio
import logging
import logging.handlers
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, SessionLocal
from app.playback_manager import get_all_playback_managers
from app.radio_manager import get_all_radio_managers
from app.api.routes import (
    videos, playback, schedule, playlists, backgrounds, audio, audio_playlists,
    radio, radio_playlists, radio_announcements, settings as settings_router, logs, import_jobs,
    updates, metrics, display, uploads, chapters, devices, diagnostics, storage, health, media_streams,
)
from app.api.routes.media_streams import reset_stale_web_rendition_status
from app.api.static_files import mount_static_files
from app.api.errors import install_error_handlers
from app.utils.android_runtime import is_android
from app.api.http_compression import (
    ApiCompressionMiddleware,
)
from app.utils import ui_language
from app.api.network_guard import LocalNetworkGuard
from app.api.origin_guard import SameOriginGuard, dev_origins
from app.utils.deployment import get_profile_handler
from app.utils.port import active_port
from app import config_files
from app.api.routes import config_files as config_files_router
from app.utils import media_native, port80, tor_proxy
from app.utils.media_sidecar import close_current_media_client
from app.utils.update_orchestrator import load_persisted_state_at_startup
from app.utils.version import get_app_version
from app.scheduling.jobs import start_scheduler, stop_scheduler
from app.scheduling.radio import autostart_default_radio_playlist
from app.scheduling.resume import cancel_pending_resume, resume_running_schedules
from app.utils.importer import reconcile_orphaned_media
from app.utils.mdns import start_mdns_responder, stop_mdns_responder
from app.utils.radio_announcement_scheduler import (
    start_radio_announcement_scheduler,
    stop_radio_announcement_scheduler,
)
from app.utils.radio_sound import load_all_sounds_into_managers
from app.utils.video_sound import load_all_video_sounds_into_managers
from app.utils.radio_mix import load_all_mixes_into_managers
from app.devices.routing import load_routes_into_managers
from app.utils.watcher import start_watcher, stop_watcher
from app.utils.ws_manager import manager as ws_manager
from app.devices.service import service as devices_service
from app.storage.service import service as storage_service

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
# `/api/logs/technical*` (api/routes/logs.py) ne sert que le fichier courant
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
    # Export statique de la langue enregistrée (changer de langue demande un redémarrage).
    with SessionLocal() as language_db:
        ui_language.set_served(settings_router.stored_language(language_db))
    # Recharge l'issue de la dernière mise à jour AVANT toute autre
    # initialisation : un redémarrage déclenché par une mise à jour réussie
    # (ou un service qui a crashé en plein milieu) ne doit pas laisser
    # `GET /api/updates/status` retomber silencieusement à "idle" avant que
    # le frontend n'ait pu lire le résultat réel.
    load_persisted_state_at_startup()
    # Transferts par morceaux abandonnés depuis plus de 24 h (app/utils/staged_uploads.py)
    from app.utils.staged_uploads import purge_stale
    purge_stale()
    reset_stale_web_rendition_status()
    # Avant le watcher : aucun import n'est possible tant que l'app n'a
    # pas fini de démarrer, donc tout fichier orphelin trouvé ici provient
    # forcément d'un arrêt brutal du service lors d'une exécution précédente.
    reconcile_orphaned_media()
    # Stockage externe : AVANT le watcher, le scheduler et la radio — tout média d'un support passe d'abord en
    # « indisponible » (chemins d'attente), puis le premier instantané remappe les supports présents (≤ 10 s).
    await storage_service.start()
    start_watcher()
    start_scheduler()
    # Best-effort, no-op sur l'appliance headless (avahi s'en charge déjà) —
    # cf. app/utils/mdns.py.
    start_mdns_responder(active_port())
    if get_profile_handler().tries_port80_redirect():
        await port80.start(active_port())
    # Copie lisible de la configuration (dossier `config/` des données), à jour dès le démarrage.
    config_files.schedule_mirror()
    # 24/7.
    # Réglages de son persistés des deux sorties radio, chargés avant tout
    # démarrage de lecture pour que le premier état diffusé les contienne.
    with SessionLocal() as sound_db:
        load_all_sounds_into_managers(sound_db)
        load_all_video_sounds_into_managers(sound_db)
        load_all_mixes_into_managers(sound_db)
        load_routes_into_managers(sound_db)
        # Réglage du composant audio natif (désactivé par défaut) : lu avant tout import.
        media_native.load_from_database(sound_db)
        tor_proxy.load_from_database(sound_db)
    await autostart_default_radio_playlist()
    # Cours programmé en cours avant l'arrêt, ou dont l'heure est passée serveur éteint : repris à sa position.
    await resume_running_schedules()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.start_position_broadcast_loop()
    for radio_manager in get_all_radio_managers().values():
        radio_manager.start_position_broadcast_loop()
    # Règles temporelles des rappels : toutes les X
    # minutes / à heures fixes — la règle « toutes les N musiques » n'a rien
    # de temporel, elle est vérifiée à chaque fin de piste (api/routes/playback.py).
    start_radio_announcement_scheduler()
    # Surveillance des périphériques (audio, Bluetooth, Wi-Fi) : inerte tant que la fonction est désactivée
    # ou qu'aucun client n'écoute ; une panne du pilote n'affecte jamais la diffusion.
    await devices_service.start()
    yield
    # Shutdown : arrêt propre du scheduler et du watcher.
    cancel_pending_resume()
    stop_scheduler()
    stop_watcher()
    for playback_manager in get_all_playback_managers().values():
        playback_manager.stop_position_broadcast_loop()
    for radio_manager in get_all_radio_managers().values():
        radio_manager.stop_position_broadcast_loop()
    await stop_radio_announcement_scheduler()
    await devices_service.stop()
    await storage_service.stop()
    stop_mdns_responder()
    await port80.stop()
    tor_proxy.shutdown()
    close_current_media_client()


app = FastAPI(title="Bobine", version=get_app_version(), lifespan=lifespan)
install_error_handlers(app)

# Le frontend est servi par ce même serveur : seul le serveur de développement est une origine tierce admise.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dev_origins()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(SameOriginGuard, allowed_origins=dev_origins())
app.add_middleware(config_files.ConfigMirrorTrigger)
# gzip des seules réponses JSON/texte de /api/* (jamais /stream, miniatures,
# Range, WebSocket...) : voir app/api/http_compression.py. Ajouté APRÈS le
# CORS pour envelopper aussi ses en-têtes ; le frontend statique négocie lui-même
# la compression (RevalidateStaticFiles) afin de garder son ETag par contenu.
app.add_middleware(ApiCompressionMiddleware)
# Ajoutée en dernier, donc exécutée en premier : un client venu d'Internet n'atteint rien.
app.add_middleware(LocalNetworkGuard)

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
app.include_router(storage.router)
app.include_router(config_files_router.router)
# En dernier : ses routes génériques `/api/radio/{output}/{action}` ne doivent masquer aucune route existante.
app.include_router(playback.command_router)
app.include_router(health.router)
app.include_router(media_streams.router)

mount_static_files(app)
